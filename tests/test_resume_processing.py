import io
from pathlib import Path
import uuid

import fitz
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from tests.test_candidates_applications import (
    create_candidate_user,
    create_registered_client,
)
from tests.test_resume_upload import setup_test_application


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


def create_sample_pdf_bytes(page_texts: list[str]) -> bytes:
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        page.insert_text((50, 50), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.asyncio
async def test_successful_multipage_pdf_text_extraction():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id = await setup_test_application(client, auth)

        page1_text = "John Doe\nSenior Backend Engineer\nPython, FastAPI, Postgres"
        page2_text = "Experience:\nLead Engineer at Acme Corp (2020 - Present)"
        pdf_bytes = create_sample_pdf_bytes([page1_text, page2_text])

        files = {"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        upload_res = await client.post(
            f"/api/v1/applications/{app_id}/resume",
            headers=auth["headers"],
            files=files,
        )
        assert upload_res.status_code == 200

        process_res = await client.post(
            f"/api/v1/applications/{app_id}/resume/process",
            headers=auth["headers"],
        )
        assert process_res.status_code == 200
        data = process_res.json()
        assert data["id"] == app_id
        assert data["resume_text"] is not None
        assert "John Doe" in data["resume_text"]
        assert "Python, FastAPI, Postgres" in data["resume_text"]
        assert "Acme Corp" in data["resume_text"]


@pytest.mark.asyncio
async def test_process_no_resume_uploaded():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id = await setup_test_application(client, auth)

        process_res = await client.post(
            f"/api/v1/applications/{app_id}/resume/process",
            headers=auth["headers"],
        )
        assert process_res.status_code == 400
        assert "no resume" in process_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_process_empty_or_scanned_pdf_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id = await setup_test_application(client, auth)

        empty_pdf_bytes = create_sample_pdf_bytes([""])
        files = {"file": ("scanned.pdf", io.BytesIO(empty_pdf_bytes), "application/pdf")}

        upload_res = await client.post(
            f"/api/v1/applications/{app_id}/resume",
            headers=auth["headers"],
            files=files,
        )
        assert upload_res.status_code == 200

        process_res = await client.post(
            f"/api/v1/applications/{app_id}/resume/process",
            headers=auth["headers"],
        )
        assert process_res.status_code == 400
        assert "no extractable text" in process_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_process_missing_stored_file():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id = await setup_test_application(client, auth)

        pdf_bytes = create_sample_pdf_bytes(["Sample text for missing file test"])
        files = {"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        upload_res = await client.post(
            f"/api/v1/applications/{app_id}/resume",
            headers=auth["headers"],
            files=files,
        )
        resume_key = upload_res.json()["resume_path"]

        physical_file = Path(settings.storage_dir) / resume_key
        if physical_file.exists():
            physical_file.unlink()

        process_res = await client.post(
            f"/api/v1/applications/{app_id}/resume/process",
            headers=auth["headers"],
        )
        assert process_res.status_code == 404
        assert "not found" in process_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_process_unauthenticated_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.post(f"/api/v1/applications/{uuid.uuid4()}/resume/process")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_process_candidate_role_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id = await setup_test_application(client, auth)
        cand_auth = await create_candidate_user(auth["organization_id"])

        res = await client.post(
            f"/api/v1/applications/{app_id}/resume/process",
            headers=cand_auth["headers"],
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_process_cross_tenant_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth_company_1 = await create_registered_client(client)
        auth_company_2 = await create_registered_client(client)

        app_id = await setup_test_application(client, auth_company_1)

        res = await client.post(
            f"/api/v1/applications/{app_id}/resume/process",
            headers=auth_company_2["headers"],
        )
        assert res.status_code == 404
