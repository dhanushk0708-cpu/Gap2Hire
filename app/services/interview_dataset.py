import hashlib
import io
import logging
from typing import Any
from uuid import UUID, uuid4

import openpyxl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.interview_dataset import (
    InterviewDatasetFile,
    InterviewDatasetQuestion,
    InterviewQuestionDataset,
)
from app.models.job import Job

logger = logging.getLogger(__name__)

# Security & size limits
MAX_EXCEL_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXCEL_EXTENSIONS = (".xlsx", ".xls")
MAX_QUESTIONS_PER_FILE = 1000
MIN_QUESTION_LENGTH = 5


class DatasetParsingError(Exception):
    """Raised when an uploaded interview dataset file violates validation rules."""
    pass


class DatasetNotFoundError(Exception):
    """Raised when a requested dataset is not found or inaccessible."""
    pass


def parse_and_validate_interview_excel(
    file_bytes: bytes,
    filename: str,
) -> list[dict[str, Any]]:
    """
    Parses an uploaded Excel (.xlsx) file into structured question datasets.
    Supports:
    1. Multi-sheet workbooks: Each sheet represents a distinct dataset/concept (e.g. "Python", "FastAPI", "PostgreSQL").
    2. Single-sheet workbooks: Rows group by a 'Dataset' or 'Concept' column.

    Validates:
    - File size & extension
    - File corruption
    - Required columns ('question' or 'question_text')
    - Non-empty questions
    - In-dataset deduplication
    - Valid dataset structure
    """
    if len(file_bytes) > MAX_EXCEL_FILE_SIZE:
        raise DatasetParsingError(f"File size exceeds maximum allowed limit of {MAX_EXCEL_FILE_SIZE // (1024 * 1024)} MB.")

    if not any(filename.lower().endswith(ext) for ext in ALLOWED_EXCEL_EXTENSIONS):
        raise DatasetParsingError(f"Unsupported file format '{filename}'. Please upload a valid .xlsx spreadsheet.")

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as e:
        raise DatasetParsingError(f"Malformed or corrupted Excel file: {str(e)}") from e

    sheet_names = wb.sheetnames
    if not sheet_names:
        raise DatasetParsingError("Excel file contains no worksheets.")

    parsed_datasets: list[dict[str, Any]] = []
    total_parsed_questions = 0

    # Case 1: Multi-sheet workbook (where each sheet is a dataset/concept)
    # Check if there are multiple sheets or if single sheet doesn't have a dataset column
    is_multi_sheet = len(sheet_names) > 1

    if is_multi_sheet:
        for s_name in sheet_names:
            sheet = wb[s_name]
            clean_s_name = s_name.strip()
            # Ignore default empty sheets
            if sheet.max_row is None or sheet.max_row < 2:
                continue

            rows = list(sheet.iter_rows(values_only=True))
            if not rows or len(rows) < 2:
                continue

            header_row = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
            col_map = _map_headers(header_row)

            if "question" not in col_map:
                # If sheet doesn't have a question column, skip or check
                continue

            questions, seen_texts = _extract_questions_from_rows(
                rows=rows[1:],
                col_map=col_map,
                default_concept=clean_s_name,
                sheet_name=clean_s_name,
            )

            if questions:
                parsed_datasets.append({
                    "name": clean_s_name,
                    "concept": clean_s_name,
                    "description": f"Interview questions on {clean_s_name}",
                    "questions": questions,
                })
                total_parsed_questions += len(questions)

    # Case 2: Single sheet OR multi-sheet didn't yield enough datasets
    if not parsed_datasets:
        sheet = wb.active or wb[sheet_names[0]]
        rows = list(sheet.iter_rows(values_only=True))
        if not rows or len(rows) < 2:
            raise DatasetParsingError("Spreadsheet contains no data rows.")

        header_row = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
        col_map = _map_headers(header_row)

        if "question" not in col_map:
            raise DatasetParsingError(
                "Missing required column 'Question' or 'Question Text' in header row. "
                f"Found headers: {[h for h in header_row if h]}"
            )

        # Check if rows specify dataset or concept
        concept_col = col_map.get("concept") or col_map.get("dataset")
        grouped: dict[str, list[dict[str, Any]]] = {}
        seen_per_group: dict[str, set[str]] = {}

        for row_idx, r in enumerate(rows[1:], start=2):
            q_val = r[col_map["question"]] if col_map["question"] < len(r) else None
            if q_val is None or not str(q_val).strip():
                continue  # skip empty question row

            q_text = str(q_val).strip()
            if len(q_text) < MIN_QUESTION_LENGTH:
                continue

            grp_concept = "General"
            if concept_col is not None and concept_col < len(r) and r[concept_col]:
                grp_concept = str(r[concept_col]).strip()

            norm_q = q_text.lower()
            if grp_concept not in seen_per_group:
                seen_per_group[grp_concept] = set()
                grouped[grp_concept] = []

            if norm_q in seen_per_group[grp_concept]:
                continue  # Skip duplicate question within the same dataset
            seen_per_group[grp_concept].add(norm_q)

            diff = _extract_cell(r, col_map.get("difficulty"), "MEDIUM").upper()
            if diff not in {"EASY", "MEDIUM", "HARD"}:
                diff = "MEDIUM"

            q_type = _extract_cell(r, col_map.get("type"), "CONCEPTUAL").upper()
            topics_raw = _extract_cell(r, col_map.get("topics"), "")
            expected_topics = [t.strip() for t in topics_raw.split(",") if t.strip()] if topics_raw else None

            grouped[grp_concept].append({
                "question_text": q_text,
                "concept": grp_concept,
                "difficulty": diff,
                "question_type": q_type,
                "expected_topics": expected_topics,
                "metadata_": {"sheet": sheet.title, "row": row_idx},
            })

        for c_name, q_list in grouped.items():
            if q_list:
                parsed_datasets.append({
                    "name": c_name,
                    "concept": c_name,
                    "description": f"Interview questions on {c_name}",
                    "questions": q_list,
                })
                total_parsed_questions += len(q_list)

    if not parsed_datasets or total_parsed_questions == 0:
        raise DatasetParsingError("No valid interview questions could be parsed from the file.")

    if total_parsed_questions > MAX_QUESTIONS_PER_FILE:
        raise DatasetParsingError(f"Total questions ({total_parsed_questions}) exceeds file limit of {MAX_QUESTIONS_PER_FILE}.")

    return parsed_datasets


def _map_headers(header_row: list[str]) -> dict[str, int]:
    col_map: dict[str, int] = {}
    for idx, h in enumerate(header_row):
        if not h:
            continue
        h_clean = h.strip().lower()
        if any(k in h_clean for k in ["question text", "question", "prompt"]):
            if "question" not in col_map:
                col_map["question"] = idx
        elif any(k in h_clean for k in ["expected topics", "expected_topics", "expected", "topics", "keywords"]):
            if "topics" not in col_map:
                col_map["topics"] = idx
        elif any(k in h_clean for k in ["concept", "skill", "category"]) or h_clean == "topic":
            if "concept" not in col_map:
                col_map["concept"] = idx
        elif "dataset" in h_clean:
            if "dataset" not in col_map:
                col_map["dataset"] = idx
        elif any(k in h_clean for k in ["difficulty", "level"]):
            if "difficulty" not in col_map:
                col_map["difficulty"] = idx
        elif any(k in h_clean for k in ["question type", "type", "format"]):
            if "type" not in col_map:
                col_map["type"] = idx
        elif "description" in h_clean:
            if "description" not in col_map:
                col_map["description"] = idx
    return col_map


def _extract_cell(row: tuple, col_idx: int | None, default: str = "") -> str:
    if col_idx is None or col_idx >= len(row):
        return default
    val = row[col_idx]
    if val is None:
        return default
    return str(val).strip()


def _extract_questions_from_rows(
    rows: list[tuple],
    col_map: dict[str, int],
    default_concept: str,
    sheet_name: str,
) -> tuple[list[dict[str, Any]], set[str]]:
    questions: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row_idx, r in enumerate(rows, start=2):
        q_idx = col_map["question"]
        if q_idx >= len(r) or r[q_idx] is None:
            continue

        q_text = str(r[q_idx]).strip()
        if len(q_text) < MIN_QUESTION_LENGTH:
            continue

        norm_q = q_text.lower()
        if norm_q in seen:
            continue  # Deduplicate within dataset
        seen.add(norm_q)

        concept = _extract_cell(r, col_map.get("concept"), default_concept) or default_concept
        diff = _extract_cell(r, col_map.get("difficulty"), "MEDIUM").upper()
        if diff not in {"EASY", "MEDIUM", "HARD"}:
            diff = "MEDIUM"

        q_type = _extract_cell(r, col_map.get("type"), "CONCEPTUAL").upper()
        topics_raw = _extract_cell(r, col_map.get("topics"), "")
        expected_topics = [t.strip() for t in topics_raw.split(",") if t.strip()] if topics_raw else None

        questions.append({
            "question_text": q_text,
            "concept": concept,
            "difficulty": diff,
            "question_type": q_type,
            "expected_topics": expected_topics,
            "metadata_": {"sheet": sheet_name, "row": row_idx},
        })

    return questions, seen


async def save_uploaded_interview_dataset(
    session: AsyncSession,
    organization_id: UUID,
    filename: str,
    file_bytes: bytes,
    job_id: UUID | None = None,
    created_by: UUID | None = None,
) -> InterviewDatasetFile:
    """
    Parses and persists an uploaded interview dataset file under strict tenant isolation.
    """
    # 1. Tenant job verification if job_id provided
    if job_id:
        job = await session.scalar(
            select(Job).where(Job.id == job_id, Job.organization_id == organization_id)
        )
        if not job:
            raise DatasetNotFoundError("Target job not found or does not belong to your organization.")

    # 2. Parse and validate Excel content
    parsed_datasets = parse_and_validate_interview_excel(file_bytes, filename)

    # 3. Calculate file hash for audit & deduplication tracking
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    total_questions = sum(len(d["questions"]) for d in parsed_datasets)

    dataset_file = InterviewDatasetFile(
        id=uuid4(),
        organization_id=organization_id,
        job_id=job_id,
        filename=filename,
        file_hash=file_hash,
        total_questions=total_questions,
        created_by=created_by,
    )
    session.add(dataset_file)

    for d_data in parsed_datasets:
        dataset = InterviewQuestionDataset(
            id=uuid4(),
            file_id=dataset_file.id,
            organization_id=organization_id,
            name=d_data["name"],
            concept=d_data["concept"],
            description=d_data.get("description"),
            question_count=len(d_data["questions"]),
        )
        session.add(dataset)

        for q_data in d_data["questions"]:
            question = InterviewDatasetQuestion(
                id=uuid4(),
                dataset_id=dataset.id,
                organization_id=organization_id,
                question_text=q_data["question_text"],
                concept=q_data["concept"],
                difficulty=q_data["difficulty"],
                question_type=q_data["question_type"],
                expected_topics=q_data["expected_topics"],
                metadata_=q_data.get("metadata_"),
            )
            session.add(question)

    await session.commit()
    return await get_interview_dataset_file(session, organization_id, dataset_file.id)


async def list_interview_dataset_files(
    session: AsyncSession,
    organization_id: UUID,
    job_id: UUID | None = None,
) -> list[InterviewDatasetFile]:
    """Lists interview dataset files belonging to the tenant organization."""
    stmt = (
        select(InterviewDatasetFile)
        .where(InterviewDatasetFile.organization_id == organization_id)
        .options(
            selectinload(InterviewDatasetFile.datasets).selectinload(InterviewQuestionDataset.questions)
        )
        .order_by(InterviewDatasetFile.created_at.desc())
    )
    if job_id:
        stmt = stmt.where((InterviewDatasetFile.job_id == job_id) | (InterviewDatasetFile.job_id.is_(None)))

    return list((await session.scalars(stmt)).all())


async def get_interview_dataset_file(
    session: AsyncSession,
    organization_id: UUID,
    file_id: UUID,
) -> InterviewDatasetFile:
    """Fetches a specific interview dataset file with its datasets and questions."""
    stmt = (
        select(InterviewDatasetFile)
        .where(
            InterviewDatasetFile.id == file_id,
            InterviewDatasetFile.organization_id == organization_id,
        )
        .options(
            selectinload(InterviewDatasetFile.datasets).selectinload(InterviewQuestionDataset.questions)
        )
    )
    file_record = await session.scalar(stmt)
    if not file_record:
        raise DatasetNotFoundError("Interview dataset file not found or inaccessible.")
    return file_record
