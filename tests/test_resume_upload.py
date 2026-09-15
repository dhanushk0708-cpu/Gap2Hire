import io
from pathlib import Path
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from tests.test_candidates_applications import (
    create_candidate_user,
    create_registered_client,
)


@pytest.fixture(autouse=True)
def cleanup_uploaded_test_files():
    yield
    storage_path = Path(settings.storage_dir)
    if storage_path.exists():
        resumes_path = storage_path / "resumes"
        if resumes_path.exists():
            for file_path in resumes_path.glob("*"):
                if file_path.is_file():
                    try:
                        file_path.unlink()
                    except OSError:
                        pass


async def setup_test_application(client: AsyncClient, auth: dict):
    headers = auth["headers"]

    job_resp = await client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"title": "Software Engineer", "description": "Backend dev"},
    )
    job_id = job_resp.json()["id"]

    cand_resp = await client.post(
        "/api/v1/candidates",
        headers=headers,
        json={"full_name": "Applicant One", "email": f"applicant.{uuid.uuid4()}@example.com"},
    )
    candidate_id = cand_resp.json()["id"]

    app_resp = await client.post(
        "/api/v1/applications",
        headers=headers,
        json={"candidate_id": candidate_id, "job_id": job_id},
    )
    return app_resp.json()["id"]


@pytest.mark.asyncio
async def test_successful_pdf_resume_upload():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id = await setup_test_application(client, auth)

        pdf_content = b"%PDF-1.4 sample pdf content for resume test"
        files = {
            "file": ("sample_resume.pdf", io.BytesIO(pdf_content), "application/pdf")
        }

        response = await client.post(
            f"/api/v1/applications/{app_id}/resume",
            headers=auth["headers"],
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == app_id
        assert data["resume_path"] is not None
        assert data["resume_path"].startswith("resumes/")
        assert data["resume_path"].endswith(".pdf")
        assert "C:" not in data["resume_path"]
        assert "Users" not in data["resume_path"]

        physical_file = Path(settings.storage_dir) / data["resume_path"]
        assert physical_file.exists()
        assert physical_file.read_bytes() == pdf_content


@pytest.mark.asyncio
async def test_unauthenticated_resume_upload():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        pdf_content = b"%PDF-1.4 unauthenticated test"
        files = {"file": ("resume.pdf", io.BytesIO(pdf_content), "application/pdf")}

        response = await client.post(
            f"/api/v1/applications/{uuid.uuid4()}/resume",
            files=files,
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_candidate_role_resume_upload_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id = await setup_test_application(client, auth)
        cand_auth = await create_candidate_user(auth["organization_id"])

        pdf_content = b"%PDF-1.4 candidate test"
        files = {"file": ("resume.pdf", io.BytesIO(pdf_content), "application/pdf")}

        response = await client.post(
            f"/api/v1/applications/{app_id}/resume",
            headers=cand_auth["headers"],
            files=files,
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_resume_upload_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth_company_1 = await create_registered_client(client)
        auth_company_2 = await create_registered_client(client)

        app_id = await setup_test_application(client, auth_company_1)

        pdf_content = b"%PDF-1.4 cross tenant test"
        files = {"file": ("resume.pdf", io.BytesIO(pdf_content), "application/pdf")}

        response = await client.post(
            f"/api/v1/applications/{app_id}/resume",
            headers=auth_company_2["headers"],
            files=files,
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_file_type_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id = await setup_test_application(client, auth)

        # 1. Invalid extension (.txt)
        txt_files = {"file": ("resume.txt", io.BytesIO(b"%PDF-fake.txt"), "text/plain")}
        res1 = await client.post(
            f"/api/v1/applications/{app_id}/resume",
            headers=auth["headers"],
            files=txt_files,
        )
        assert res1.status_code == 400
        assert "only pdf" in res1.json()["detail"].lower()

        # 2. PDF extension but invalid magic bytes
        fake_pdf_files = {"file": ("resume.pdf", io.BytesIO(b"Not a real PDF file"), "application/pdf")}
        res2 = await client.post(
            f"/api/v1/applications/{app_id}/resume",
            headers=auth["headers"],
            files=fake_pdf_files,
        )
        assert res2.status_code == 400
        assert "invalid pdf" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_empty_and_oversized_file_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id = await setup_test_application(client, auth)

        # 1. Empty file
        empty_files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
        res1 = await client.post(
            f"/api/v1/applications/{app_id}/resume",
            headers=auth["headers"],
            files=empty_files,
        )
        assert res1.status_code == 400
        assert "empty" in res1.json()["detail"].lower()

        # 2. Oversized file
        oversized_content = b"%PDF-" + (b"0" * (settings.max_resume_size_bytes + 100))
        huge_files = {"file": ("huge.pdf", io.BytesIO(oversized_content), "application/pdf")}
        res2 = await client.post(
            f"/api/v1/applications/{app_id}/resume",
            headers=auth["headers"],
            files=huge_files,
        )
        assert res2.status_code == 413
        assert "exceeds" in res2.json()["detail"].lower()
