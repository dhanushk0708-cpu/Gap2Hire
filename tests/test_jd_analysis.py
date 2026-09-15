import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.roles import UserRole
from app.core.security import create_access_token, hash_password
from app.db.session import async_session_factory
from app.main import app
from app.models.user import User
from app.schemas.capability import CapabilityImportance
from app.schemas.jd_analysis import SuggestedCapability
from app.services.ai_jd import AIServiceError
from tests.test_jobs import create_registered_client


@pytest.mark.asyncio
async def test_jd_analysis_success_mocked():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        # Create Job
        job_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={
                "title": "Backend Architect",
                "description": "Design Python microservices with PostgreSQL and Docker.",
            },
        )
        assert job_resp.status_code == 201
        job_id = job_resp.json()["id"]

        mock_capabilities = [
            SuggestedCapability(
                name="Python",
                description="Core language requirement for microservices",
                importance=CapabilityImportance.HIGH,
            ),
            SuggestedCapability(
                name="PostgreSQL",
                description="Primary relational database management",
                importance=CapabilityImportance.HIGH,
            ),
            SuggestedCapability(
                name="Docker",
                description="Containerization for deployment",
                importance=CapabilityImportance.MEDIUM,
            ),
        ]

        with patch(
            "app.api.jd_analysis.extract_capabilities_from_jd",
            new_callable=AsyncMock,
            return_value=mock_capabilities,
        ) as mock_extract:
            resp = await client.post(
                f"/api/v1/jobs/{job_id}/analyze",
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()

            assert data["job_id"] == job_id
            assert len(data["suggested_capabilities"]) == 3
            assert data["suggested_capabilities"][0]["name"] == "Python"
            assert data["suggested_capabilities"][0]["importance"] == "HIGH"

            mock_extract.assert_called_once_with(
                title="Backend Architect",
                description="Design Python microservices with PostgreSQL and Docker.",
            )

        # Confirm job's actual capabilities table was NOT automatically populated
        caps_resp = await client.get(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
        )
        assert caps_resp.status_code == 200
        assert len(caps_resp.json()) == 0


@pytest.mark.asyncio
async def test_jd_analysis_unauthenticated_rejected():
    fake_job_id = str(uuid.uuid4())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(f"/api/v1/jobs/{fake_job_id}/analyze")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_jd_analysis_candidate_forbidden():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        org_id = uuid.UUID(auth["organization_id"])

        # Insert a candidate user
        candidate_user = User(
            organization_id=org_id,
            email=f"candidate-{uuid.uuid4()}@gap2hire.com",
            password_hash=hash_password("Pass123!"),
            full_name="Candidate",
            role=UserRole.CANDIDATE.value,
        )
        async with async_session_factory() as session:
            session.add(candidate_user)
            await session.commit()
            await session.refresh(candidate_user)

        candidate_headers = {
            "Authorization": f"Bearer {create_access_token(str(candidate_user.id))}"
        }
        fake_job_id = str(uuid.uuid4())

        resp = await client.post(
            f"/api/v1/jobs/{fake_job_id}/analyze",
            headers=candidate_headers,
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_jd_analysis_cross_tenant_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth_a = await create_registered_client(client)
        auth_b = await create_registered_client(client)

        # Org A creates a job
        job_a_resp = await client.post(
            "/api/v1/jobs",
            headers=auth_a["headers"],
            json={"title": "Org A Job", "description": "Secret Job"},
        )
        job_a_id = job_a_resp.json()["id"]

        # Org B attempts to analyze Org A's job -> 404 Not Found
        resp = await client.post(
            f"/api/v1/jobs/{job_a_id}/analyze",
            headers=auth_b["headers"],
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_jd_analysis_ai_error_handled():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        headers = auth["headers"]

        job_resp = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": "Data Engineer", "description": "ETL pipelines"},
        )
        job_id = job_resp.json()["id"]

        with patch(
            "app.api.jd_analysis.extract_capabilities_from_jd",
            side_effect=AIServiceError("Groq API returned error status 500"),
        ):
            resp = await client.post(
                f"/api/v1/jobs/{job_id}/analyze",
                headers=headers,
            )
            assert resp.status_code == 502
            assert "Groq API returned error status 500" in resp.json()["detail"]
