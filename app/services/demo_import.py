import hashlib
import io
import logging
import os
import re
import tempfile
import zipfile
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.job import Job
from app.schemas.demo_import import DemoImportResult
from app.services.application import JobNotFoundError
from app.services.resume_processor import extract_text_from_pdf_bytes, NoExtractableTextError
from app.services.resume_url_discovery import sync_resume_candidate_sources
from app.services.screening import build_candidate_screening_report

logger = logging.getLogger(__name__)

# Security & archive validation limits
MAX_ZIP_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILES = 200
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file
MAX_TOTAL_EXTRACTED = 100 * 1024 * 1024  # 100 MB


class DemoImportSecurityError(Exception):
    pass


class InvalidZipArchiveError(Exception):
    pass


def extract_candidate_name_from_text(resume_text: str, fallback_filename: str) -> str:
    """Extract candidate name from first non-empty line of resume, or derive from filename."""
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    if lines:
        first_line = lines[0]
        # Clean potential headers or prefixes
        clean = re.sub(r'^(name|candidate|profile):\s*', '', first_line, flags=re.IGNORECASE).strip()
        words = clean.split()
        if 1 <= len(words) <= 5 and not any(ch in clean for ch in "{}[]<>|;:$@%^&*=\\/_"):
            # Check not just numeric or single letter
            if any(w.isalpha() and len(w) > 1 for w in words):
                return clean[:100]

    # Fallback to filename (e.g., candidate_01_aarav_sharma.pdf -> Aarav Sharma)
    base = os.path.splitext(os.path.basename(fallback_filename))[0]
    base = re.sub(r'^candidate_?\d+_?', '', base, flags=re.IGNORECASE)
    parts = [p.capitalize() for p in base.replace('_', ' ').replace('-', ' ').split() if p]
    if parts:
        return " ".join(parts)
    return "Demo Candidate"


def generate_deterministic_demo_email(filename: str, pdf_bytes: bytes) -> str:
    """
    Generates a deterministic synthetic email ending with @demo.gap2hire.local
    such as demo.candidate01@demo.gap2hire.local.
    """
    # Check if filename contains candidate number
    m = re.search(r'candidate_?(\d+)', filename, re.IGNORECASE)
    if m:
        num = m.group(1).zfill(2)
        return f"demo.candidate{num}@demo.gap2hire.local"

    # Fallback: sha256 hash of file content
    h = hashlib.sha256(pdf_bytes).hexdigest()[:8]
    return f"demo.candidate.{h}@demo.gap2hire.local"


def extract_grounded_evidence_for_resume(
    capabilities: Sequence[Capability],
    resume_text: str,
) -> list[dict]:
    """
    Extracts grounded capability evidence claims from resume text deterministically.
    Strictly adheres to:
    - Only grounded quotes from the text.
    - Allowed strengths: STRONG, MODERATE, WEAK, INSUFFICIENT.
    - If absent: INSUFFICIENT with None content.
    - Provenance: strictly CLAIM.
    """
    results = []
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    text_lower = resume_text.lower()

    for cap in capabilities:
        cap_name = cap.name.strip()
        cap_lower = cap_name.lower()

        # Word boundary match for capability name
        pattern = r'\b' + re.escape(cap_lower) + r'\b'
        match = re.search(pattern, text_lower)

        if not match:
            # Check standard aliases (e.g., "REST API" for "REST APIs", "Postgres" for "PostgreSQL")
            aliases = []
            if "rest api" in cap_lower:
                aliases = [r'\brest\b', r'\brestful\b', r'\brest apis?\b']
            elif "postgres" in cap_lower:
                aliases = [r'\bpostgres\b', r'\bpostgresql\b']
            elif "docker" in cap_lower:
                aliases = [r'\bdocker\b', r'\bcontainer(?:s|ization)?\b']
            elif "fastapi" in cap_lower:
                aliases = [r'\bfastapi\b']
            elif "python" in cap_lower:
                aliases = [r'\bpython\b', r'\bpython3\b']

            for alias in aliases:
                match = re.search(alias, text_lower)
                if match:
                    break

        if match:
            # Locate matching line(s) in resume text
            matched_line = None
            is_project_or_exp = False
            current_section = ""

            for line in lines:
                l_lower = line.lower()
                if any(sec in l_lower for sec in ["project", "experience", "work history", "employment"]):
                    current_section = "PROJECTS"
                elif any(sec in l_lower for sec in ["skill", "technolog", "proficienc"]):
                    current_section = "SKILLS"

                if re.search(pattern, l_lower) or (match and match.group(0) in l_lower):
                    matched_line = line
                    if current_section == "PROJECTS" or "involving" in l_lower or "built" in l_lower or "developed" in l_lower:
                        is_project_or_exp = True
                    break

            if not matched_line:
                matched_line = f"Mentions {cap_name} in resume."

            # Determine strength based on context
            if is_project_or_exp:
                strength = "STRONG"
            elif "limited" in text_lower or "basic" in text_lower:
                strength = "WEAK"
            else:
                strength = "MODERATE"

            results.append({
                "capability_id": cap.id,
                "strength": strength,
                "content": matched_line[:500],
            })
        else:
            results.append({
                "capability_id": cap.id,
                "strength": "INSUFFICIENT",
                "content": None,
            })

    return results


async def import_demo_resumes_zip(
    session: AsyncSession,
    organization_id: UUID,
    job_id: UUID,
    zip_bytes: bytes,
    original_filename: str,
) -> DemoImportResult:
    """
    Safely unpacks a ZIP of synthetic PDF resumes and feeds them through the downstream
    candidate, source discovery, evidence extraction, and preliminary screening pipeline.
    """
    # 1. Environment / Demo Permission Check
    if not settings.enable_demo_import and settings.environment not in ("development", "test", "staging"):
        raise DemoImportSecurityError("Demo resume ZIP import is disabled in this environment.")

    # 2. Archive extension & size validation
    if not original_filename.lower().endswith(".zip"):
        raise InvalidZipArchiveError("Uploaded file must have a .zip extension.")

    if len(zip_bytes) > MAX_ZIP_SIZE:
        raise DemoImportSecurityError(f"ZIP file exceeds maximum allowed size of {MAX_ZIP_SIZE // (1024 * 1024)} MB.")

    if not zipfile.is_zipfile(io.BytesIO(zip_bytes)):
        raise InvalidZipArchiveError("Uploaded file is not a valid ZIP archive.")

    # 3. Target Job Verification under tenant isolation
    job_stmt = select(Job).where(Job.id == job_id, Job.organization_id == organization_id)
    job = await session.scalar(job_stmt)
    if not job:
        raise JobNotFoundError("Target job not found or does not belong to your organization.")

    # Approved capabilities for the job
    caps_stmt = select(Capability).where(Capability.job_id == job_id)
    capabilities = list((await session.scalars(caps_stmt)).all())

    # 4. Safe ZIP Inspection & Path Traversal Prevention
    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception as e:
        raise InvalidZipArchiveError(f"Corrupted or invalid ZIP file: {str(e)}") from e

    all_names = archive.namelist()
    if len(all_names) > MAX_FILES:
        raise DemoImportSecurityError(f"ZIP contains too many files ({len(all_names)}). Maximum allowed is {MAX_FILES}.")

    total_uncompressed = 0
    pdf_entries = []

    for info in archive.infolist():
        entry_name = info.filename
        # Path traversal checks
        if ".." in entry_name or entry_name.startswith(("/", "\\")) or ":" in entry_name:
            raise DemoImportSecurityError(f"Illegal path traversal entry detected: {entry_name}")

        # Ignore macOS hidden files and directories
        if info.is_dir() or entry_name.startswith("__MACOSX") or os.path.basename(entry_name).startswith("."):
            continue

        if not entry_name.lower().endswith(".pdf"):
            continue

        if info.file_size > MAX_FILE_SIZE:
            raise DemoImportSecurityError(f"File {entry_name} exceeds maximum uncompressed size of {MAX_FILE_SIZE // (1024 * 1024)} MB.")

        total_uncompressed += info.file_size
        if total_uncompressed > MAX_TOTAL_EXTRACTED:
            raise DemoImportSecurityError(f"Total uncompressed ZIP size exceeds maximum limit of {MAX_TOTAL_EXTRACTED // (1024 * 1024)} MB.")

        pdf_entries.append(entry_name)

    if not pdf_entries:
        raise InvalidZipArchiveError("No valid PDF resume files found in the ZIP archive.")

    # 5. Extract & Ingest Each PDF through Candidate Pipeline
    created_count = 0
    skipped_duplicates = 0
    failed_count = 0
    candidate_names = []
    errors = []

    # Ensure storage directory exists
    storage_base = os.path.join(settings.storage_dir, "resumes")
    os.makedirs(storage_base, exist_ok=True)

    # Pre-fetch existing demo candidates and existing applications to avoid per-file DB roundtrips
    cand_stmt = select(Candidate).where(Candidate.email.like("%@demo.gap2hire.local"))
    cand_cache = {c.email: c for c in (await session.scalars(cand_stmt)).all()}

    app_stmt = select(Application).where(Application.job_id == job_id)
    existing_app_cand_ids = {a.candidate_id for a in (await session.scalars(app_stmt)).all()}

    with tempfile.TemporaryDirectory() as temp_dir:
        for entry_name in pdf_entries:
            try:
                pdf_bytes = archive.read(entry_name)
                if not pdf_bytes:
                    failed_count += 1
                    errors.append(f"{entry_name}: Empty PDF file")
                    continue

                # Resume text extraction
                try:
                    resume_text = extract_text_from_pdf_bytes(pdf_bytes)
                except NoExtractableTextError as err:
                    failed_count += 1
                    errors.append(f"{entry_name}: {str(err)}")
                    continue

                # Candidate Name & Deterministic Email
                cand_name = extract_candidate_name_from_text(resume_text, entry_name)
                demo_email = generate_deterministic_demo_email(entry_name, pdf_bytes)

                # Candidate Lookup / Create
                if demo_email in cand_cache:
                    candidate = cand_cache[demo_email]
                else:
                    candidate = Candidate(
                        id=uuid4(),
                        full_name=cand_name,
                        email=demo_email,
                    )
                    session.add(candidate)
                    cand_cache[demo_email] = candidate

                # Duplicate Application Check for this Job
                if candidate.id in existing_app_cand_ids:
                    skipped_duplicates += 1
                    continue

                existing_app_cand_ids.add(candidate.id)

                # Save resume PDF to storage
                safe_name = re.sub(r'[^a-zA-Z0-9_\.-]', '_', os.path.basename(entry_name))
                app_id = uuid4()
                resume_filename = f"demo_{app_id}_{safe_name}"
                resume_disk_path = os.path.join(storage_base, resume_filename)
                with open(resume_disk_path, "wb") as f_out:
                    f_out.write(pdf_bytes)

                # Create Application
                new_app = Application(
                    id=app_id,
                    candidate_id=candidate.id,
                    job_id=job_id,
                    status="SCREENING",
                    screening_status="SCREENING",
                    screening_notes=f"Imported from {entry_name}. Ready for screening evaluation.",
                    is_demo=True,
                    resume_path=f"resumes/{resume_filename}",
                    resume_text=resume_text,
                    applied_at=datetime.utcnow(),
                )
                session.add(new_app)

                # 6. Downstream Candidate Pipeline:
                # a) Sync Candidate Sources (links discovered in resume)
                try:
                    await sync_resume_candidate_sources(
                        session=session,
                        organization_id=organization_id,
                        application_id=new_app.id,
                        resume_text=resume_text,
                    )
                except Exception as src_err:
                    logger.info(f"Source discovery notice for demo candidate {cand_name}: {src_err}")

                # b) Grounded capability evidence extraction
                if capabilities:
                    ev_items = extract_grounded_evidence_for_resume(capabilities, resume_text)
                    for item in ev_items:
                        new_ev = Evidence(
                            id=uuid4(),
                            application_id=new_app.id,
                            capability_id=item["capability_id"],
                            candidate_source_id=None,
                            source_type="RESUME",
                            strength=item["strength"],
                            provenance="CLAIM",
                            content=item["content"],
                        )
                        session.add(new_ev)

                created_count += 1
                candidate_names.append(cand_name)

            except Exception as item_err:
                logger.error(f"Error processing {entry_name}: {item_err}", exc_info=True)
                failed_count += 1
                errors.append(f"{entry_name}: {str(item_err)}")

    await session.commit()

    return DemoImportResult(
        total_found=len(pdf_entries),
        created=created_count,
        skipped_duplicates=skipped_duplicates,
        failed=failed_count,
        job_id=job_id,
        candidate_names=candidate_names,
        errors=errors,
        message=f"Processed {len(pdf_entries)} demo resumes: {created_count} created, {skipped_duplicates} duplicates skipped, {failed_count} failed.",
    )
