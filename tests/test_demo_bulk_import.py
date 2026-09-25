import io
import os
import zipfile
from uuid import UUID, uuid4
import fitz
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import async_session_factory
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.job import Job
from app.models.user import User, UserRole
from app.schemas.screening import JobCandidateListItem


def create_in_memory_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    return doc.tobytes()


def create_test_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


async def setup_test_recruiter_and_job(client: AsyncClient, shortlist_size: int = 5):
    org_name = f"Demo Corp {uuid4()}"
    email = f"recruiter-{uuid4()}@democorp.com"
    password = "SecurePassword123!"

    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Demo Recruiter",
            "organization_name": org_name,
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job_resp = await client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Backend Python Developer",
            "description": "Python, FastAPI, and PostgreSQL engineer",
            "shortlist_size": shortlist_size,
        },
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # Add 3 capabilities: 2 required, 1 preferred
    cap1 = await client.post(
        f"/api/v1/jobs/{job_id}/capabilities",
        headers=headers,
        json={"name": "Python", "importance": "CRITICAL", "description": "Python programming"},
    )
    assert cap1.status_code == 201

    cap2 = await client.post(
        f"/api/v1/jobs/{job_id}/capabilities",
        headers=headers,
        json={"name": "FastAPI", "importance": "HIGH", "description": "FastAPI web framework"},
    )
    assert cap2.status_code == 201

    cap3 = await client.post(
        f"/api/v1/jobs/{job_id}/capabilities",
        headers=headers,
        json={"name": "PostgreSQL", "importance": "MEDIUM", "description": "PostgreSQL database"},
    )
    assert cap3.status_code == 201

    return headers, job_id


@pytest.mark.asyncio
async def test_zip_upload_requires_hr_authorization():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # No auth header
        files = {"file": ("test.zip", b"fake", "application/zip")}
        resp = await client.post(
            "/api/v1/demo/import-resumes",
            data={"job_id": str(uuid4())},
            files=files,
        )
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_invalid_file_extension_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_test_recruiter_and_job(client)

        files = {"file": ("resumes.tar.gz", b"fakecontent", "application/gzip")}
        resp = await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers,
            data={"job_id": job_id},
            files=files,
        )
        assert resp.status_code == 400
        assert "must have a .zip extension" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_malformed_zip_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_test_recruiter_and_job(client)

        files = {"file": ("corrupt.zip", b"this is completely not a zip archive", "application/zip")}
        resp = await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers,
            data={"job_id": job_id},
            files=files,
        )
        assert resp.status_code == 400
        assert "not a valid ZIP archive" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_zip_path_traversal_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_test_recruiter_and_job(client)

        pdf_bytes = create_in_memory_pdf("Malicious Candidate\nPython developer")
        malicious_zip = create_test_zip({"../../evil.pdf": pdf_bytes})

        files = {"file": ("traversal.zip", malicious_zip, "application/zip")}
        resp = await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers,
            data={"job_id": job_id},
            files=files,
        )
        assert resp.status_code in (400, 403)
        assert "traversal" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_pdf_files_ignored_safely():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_test_recruiter_and_job(client)

        valid_pdf = create_in_memory_pdf("Aarav Sharma\nPython, FastAPI developer\nProjects with FastAPI.")
        mixed_zip = create_test_zip({
            "candidate_01_aarav.pdf": valid_pdf,
            "notes.txt": b"Random text notes",
            "image.png": b"\x89PNG\r\n\x1a\nfakeimage",
            "subfolder/": b"",
        })

        files = {"file": ("mixed.zip", mixed_zip, "application/zip")}
        resp = await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers,
            data={"job_id": job_id},
            files=files,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_found"] == 1
        assert data["created"] == 1
        assert data["failed"] == 0


@pytest.mark.asyncio
async def test_candidate_and_application_records_created_with_is_demo():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_test_recruiter_and_job(client)

        pdf1 = create_in_memory_pdf("Meera Nair\nPython, FastAPI\nBackend development experience.")
        zip_bytes = create_test_zip({"candidate_02_meera_nair.pdf": pdf1})

        resp = await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers,
            data={"job_id": job_id},
            files={"file": ("demo.zip", zip_bytes, "application/zip")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1

        # Verify DB records
        async with async_session_factory() as session:
            cand = await session.scalar(select(Candidate).where(Candidate.email == "demo.candidate02@demo.gap2hire.local"))
            assert cand is not None
            assert "Meera Nair" in cand.full_name

            app_obj = await session.scalar(select(Application).where(Application.candidate_id == cand.id, Application.job_id == UUID(job_id)))
            assert app_obj is not None
            assert app_obj.is_demo is True
            assert app_obj.status == "SCREENING"
            assert "Meera Nair" in app_obj.resume_text


@pytest.mark.asyncio
async def test_duplicate_demo_import_handled_safely():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_test_recruiter_and_job(client)

        pdf = create_in_memory_pdf("Rohan Kapoor\nPython, PostgreSQL developer")
        zip_bytes = create_test_zip({"candidate_03_rohan_kapoor.pdf": pdf})

        # First import
        resp1 = await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers,
            data={"job_id": job_id},
            files={"file": ("demo.zip", zip_bytes, "application/zip")},
        )
        assert resp1.status_code == 200
        assert resp1.json()["created"] == 1
        assert resp1.json()["skipped_duplicates"] == 0

        # Second import of same ZIP
        resp2 = await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers,
            data={"job_id": job_id},
            files={"file": ("demo.zip", zip_bytes, "application/zip")},
        )
        assert resp2.status_code == 200
        assert resp2.json()["created"] == 0
        assert resp2.json()["skipped_duplicates"] == 1


@pytest.mark.asyncio
async def test_demo_candidates_tenant_isolated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Org 1
        headers1, job_id1 = await setup_test_recruiter_and_job(client)
        # Org 2
        headers2, job_id2 = await setup_test_recruiter_and_job(client)

        pdf = create_in_memory_pdf("Tenant Candidate\nPython developer")
        zip_bytes = create_test_zip({"candidate_04_tenant.pdf": pdf})

        # Org 2 tries to import into Org 1's job -> 404
        resp = await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers2,
            data={"job_id": job_id1},
            files={"file": ("demo.zip", zip_bytes, "application/zip")},
        )
        assert resp.status_code == 404

        # Org 1 can access their queue, Org 2 sees empty
        queue1 = await client.get(f"/api/v1/jobs/{job_id1}/candidates", headers=headers1)
        queue2 = await client.get(f"/api/v1/jobs/{job_id2}/candidates", headers=headers2)
        assert queue1.status_code == 200
        assert queue2.status_code == 200
        assert len(queue2.json()) == 0


@pytest.mark.asyncio
async def test_screening_evaluates_imported_demo_candidates_and_maintains_top_n():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_test_recruiter_and_job(client, shortlist_size=2)

        # 3 candidates:
        # Cand 1: Python, FastAPI, PostgreSQL (all 3 caps)
        pdf1 = create_in_memory_pdf("Strong Candidate\nProjects involving Python, FastAPI, and PostgreSQL.")
        # Cand 2: Python, FastAPI (2 caps)
        pdf2 = create_in_memory_pdf("Moderate Candidate\nProjects involving Python and FastAPI.")
        # Cand 3: No relevant caps
        pdf3 = create_in_memory_pdf("Unrelated Candidate\nExperience in Graphic Design and Photoshop.")

        zip_bytes = create_test_zip({
            "candidate_05_strong.pdf": pdf1,
            "candidate_06_moderate.pdf": pdf2,
            "candidate_07_unrelated.pdf": pdf3,
        })

        import_resp = await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers,
            data={"job_id": job_id},
            files={"file": ("demo.zip", zip_bytes, "application/zip")},
        )
        assert import_resp.status_code == 200
        assert import_resp.json()["created"] == 3

        # Run automated screening
        screen_resp = await client.post(
            f"/api/v1/jobs/{job_id}/screening/run",
            headers=headers,
        )
        assert screen_resp.status_code == 200
        data = screen_resp.json()
        assert data["total_candidates_evaluated"] == 3

        # Top-N should contain at most eligible candidates (shortlist size is 2, maximum not quota)
        top_candidates = data["top_n_candidates"]
        assert len(top_candidates) <= 2
        # Cand 1 must be top ranked
        assert top_candidates[0]["candidate_name"] == "Strong Candidate"

        # Cand 3 (unrelated) must be in excluded_candidates with structured reason
        excluded = data["excluded_candidates"]
        unrelated_excluded = [c for c in excluded if c["candidate_name"] == "Unrelated Candidate"]
        assert len(unrelated_excluded) == 1
        assert "missing required" in unrelated_excluded[0]["selection_reason"].lower() or "not shortlisted" in unrelated_excluded[0]["selection_reason"].lower()


@pytest.mark.asyncio
async def test_demo_candidates_marked_in_queue_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_test_recruiter_and_job(client)

        pdf = create_in_memory_pdf("Marked Candidate\nPython developer")
        zip_bytes = create_test_zip({"candidate_08_marked.pdf": pdf})

        await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers,
            data={"job_id": job_id},
            files={"file": ("demo.zip", zip_bytes, "application/zip")},
        )

        queue_resp = await client.get(f"/api/v1/jobs/{job_id}/candidates", headers=headers)
        assert queue_resp.status_code == 200
        items = queue_resp.json()
        assert len(items) == 1
        assert items[0]["is_demo"] is True


@pytest.mark.asyncio
async def test_real_50_fake_resumes_zip_smoke_test():
    """
    Integration smoke test: Ingests the actual Gap2Hire_50_Fake_Resumes.zip,
    asserts 50 candidates are found and created, runs screening, and verifies Top-N behavior.
    """
    zip_path = r"C:\Users\dhanu\Downloads\Gap2Hire_50_Fake_Resumes.zip"
    if not os.path.exists(zip_path):
        pytest.skip(f"ZIP file not found at {zip_path}")

    with open(zip_path, "rb") as f:
        real_zip_bytes = f.read()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_test_recruiter_and_job(client, shortlist_size=5)

        import_resp = await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers,
            data={"job_id": job_id},
            files={"file": ("Gap2Hire_50_Fake_Resumes.zip", real_zip_bytes, "application/zip")},
        )
        assert import_resp.status_code == 200
        data = import_resp.json()
        assert data["total_found"] == 50
        assert data["created"] == 50
        assert data["failed"] == 0
        assert data["skipped_duplicates"] == 0

        # Run automated screening across all 50 candidates
        screen_resp = await client.post(
            f"/api/v1/jobs/{job_id}/screening/run",
            headers=headers,
        )
        assert screen_resp.status_code == 200
        screen_data = screen_resp.json()
        assert screen_data["total_candidates_evaluated"] == 50
        assert len(screen_data["top_n_candidates"]) <= 5
        assert len(screen_data["excluded_candidates"]) >= 45

        # Verify duplicate re-import yields 0 created and 50 skipped
        reimport_resp = await client.post(
            "/api/v1/demo/import-resumes",
            headers=headers,
            data={"job_id": job_id},
            files={"file": ("Gap2Hire_50_Fake_Resumes.zip", real_zip_bytes, "application/zip")},
        )
        assert reimport_resp.status_code == 200
        reimport_data = reimport_resp.json()
        assert reimport_data["created"] == 0
        assert reimport_data["skipped_duplicates"] == 50
