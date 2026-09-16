from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import async_session_factory
from app.main import app
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.schemas.evidence import AIEvidenceItem, EvidenceStrength
from app.services.ai_evidence import AIEvidenceServiceError
from tests.test_candidates_applications import (
    create_candidate_user,
    create_registered_client,
)
from tests.test_resume_upload import setup_test_application


async def setup_application_with_capabilities_and_resume(
    client: AsyncClient,
    auth: dict,
    capabilities: list[dict],
    resume_text: str = "Developed REST APIs using Python and FastAPI.",
) -> tuple[str, list[dict]]:
    headers = auth["headers"]

    job_resp = await client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"title": "Senior Backend Engineer", "description": "Python API role"},
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    created_caps = []
    for cap in capabilities:
        cap_resp = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json=cap,
        )
        assert cap_resp.status_code == 201
        created_caps.append(cap_resp.json())

    cand_resp = await client.post(
        "/api/v1/candidates",
        headers=headers,
        json={"full_name": "Test Candidate", "email": f"cand.{uuid.uuid4()}@example.com"},
    )
    assert cand_resp.status_code == 201
    candidate_id = cand_resp.json()["id"]

    app_resp = await client.post(
        "/api/v1/applications",
        headers=headers,
        json={"candidate_id": candidate_id, "job_id": job_id},
    )
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    async with async_session_factory() as session:
        application = await session.get(
            __import__("app.models.application", fromlist=["Application"]).Application,
            uuid.UUID(app_id),
        )
        assert application is not None
        application.resume_text = resume_text
        await session.commit()

    return app_id, created_caps


@pytest.mark.asyncio
async def test_successful_evidence_extraction():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_application_with_capabilities_and_resume(
            client,
            auth,
            capabilities=[
                {"name": "Python", "description": "Core language", "importance": "HIGH"},
                {"name": "FastAPI", "description": "Web framework", "importance": "HIGH"},
            ],
            resume_text="Developed REST APIs using Python and FastAPI.",
        )

        mock_ai_output = [
            AIEvidenceItem(
                capability_name="Python",
                strength=EvidenceStrength.STRONG,
                evidence="Developed REST APIs using Python",
            ),
            AIEvidenceItem(
                capability_name="FastAPI",
                strength=EvidenceStrength.MODERATE,
                evidence="Developed REST APIs using FastAPI",
            ),
        ]

        with patch(
            "app.services.evidence.extract_evidence_from_resume",
            new=AsyncMock(return_value=mock_ai_output),
        ):
            response = await client.post(
                f"/api/v1/applications/{app_id}/evidence/analyze",
                headers=auth["headers"],
            )

        assert response.status_code == 200
        ev_data = response.json()
        assert len(ev_data) == 2

        async with async_session_factory() as session:
            ev_list = (
                await session.scalars(
                    __import__("sqlalchemy", fromlist=["select"]).select(Evidence).where(Evidence.application_id == uuid.UUID(app_id))
                )
            ).all()
            assert len(ev_list) == 2
            for ev in ev_list:
                assert ev.source_type == "RESUME"
                assert ev.strength in ["STRONG", "MODERATE"]
                assert ev.content is not None


@pytest.mark.asyncio
async def test_insufficient_evidence():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_application_with_capabilities_and_resume(
            client,
            auth,
            capabilities=[
                {"name": "Redis", "description": "Caching layer", "importance": "HIGH"},
            ],
            resume_text="Worked on frontend HTML and CSS only.",
        )

        mock_ai_output = [
            AIEvidenceItem(
                capability_name="Redis",
                strength=EvidenceStrength.INSUFFICIENT,
                evidence=None,
            )
        ]

        with patch(
            "app.services.evidence.extract_evidence_from_resume",
            new=AsyncMock(return_value=mock_ai_output),
        ):
            response = await client.post(
                f"/api/v1/applications/{app_id}/evidence/analyze",
                headers=auth["headers"],
            )

        assert response.status_code == 200
        ev_data = response.json()
        assert len(ev_data) == 1
        assert ev_data[0]["strength"] == "INSUFFICIENT"
        assert ev_data[0]["content"] is None


@pytest.mark.asyncio
async def test_unknown_capability_ignored():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_application_with_capabilities_and_resume(
            client,
            auth,
            capabilities=[
                {"name": "Python", "description": "Core language", "importance": "HIGH"},
            ],
            resume_text="Python and Docker developer.",
        )

        mock_ai_output = [
            AIEvidenceItem(
                capability_name="Python",
                strength=EvidenceStrength.STRONG,
                evidence="Python developer.",
            ),
            AIEvidenceItem(
                capability_name="Docker",
                strength=EvidenceStrength.STRONG,
                evidence="Docker developer.",
            ),
        ]

        with patch(
            "app.services.evidence.extract_evidence_from_resume",
            new=AsyncMock(return_value=mock_ai_output),
        ):
            response = await client.post(
                f"/api/v1/applications/{app_id}/evidence/analyze",
                headers=auth["headers"],
            )

        assert response.status_code == 200
        ev_data = response.json()
        assert len(ev_data) == 1
        assert ev_data[0]["capability_id"] == caps[0]["id"]


@pytest.mark.asyncio
async def test_invalid_ai_response_handling():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, _ = await setup_application_with_capabilities_and_resume(
            client,
            auth,
            capabilities=[{"name": "Python", "description": "Core language"}],
        )

        with patch(
            "app.services.evidence.extract_evidence_from_resume",
            new=AsyncMock(side_effect=AIEvidenceServiceError("Malformed LLM response")),
        ):
            response = await client.post(
                f"/api/v1/applications/{app_id}/evidence/analyze",
                headers=auth["headers"],
            )

        assert response.status_code == 502
        assert "malformed" in response.json()["detail"].lower() or "ai" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_no_processed_resume():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id = await setup_test_application(client, auth)

        async with async_session_factory() as session:
            app_obj = await session.get(
                __import__("app.models.application", fromlist=["Application"]).Application,
                uuid.UUID(app_id),
            )
            cap = Capability(job_id=app_obj.job_id, name="Python", importance="HIGH")
            session.add(cap)
            await session.commit()

        response = await client.post(
            f"/api/v1/applications/{app_id}/evidence/analyze",
            headers=auth["headers"],
        )
        assert response.status_code == 400
        assert "no processed resume" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_no_approved_capabilities():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, _ = await setup_application_with_capabilities_and_resume(
            client,
            auth,
            capabilities=[],
            resume_text="Experienced developer.",
        )

        response = await client.post(
            f"/api/v1/applications/{app_id}/evidence/analyze",
            headers=auth["headers"],
        )
        assert response.status_code == 400
        assert "no approved capabilities" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unauthenticated_request():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/v1/applications/{uuid.uuid4()}/evidence/analyze"
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_candidate_role_rejection():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        cand_auth = await create_candidate_user(auth["organization_id"])

        response = await client.post(
            f"/api/v1/applications/{uuid.uuid4()}/evidence/analyze",
            headers=cand_auth["headers"],
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_application():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth_company_1 = await create_registered_client(client)
        auth_company_2 = await create_registered_client(client)

        app_id, _ = await setup_application_with_capabilities_and_resume(
            client,
            auth_company_1,
            capabilities=[{"name": "Python", "description": "Core"}],
        )

        response = await client.post(
            f"/api/v1/applications/{app_id}/evidence/analyze",
            headers=auth_company_2["headers"],
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_repeated_analysis_updates_existing_records():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_application_with_capabilities_and_resume(
            client,
            auth,
            capabilities=[{"name": "FastAPI", "description": "Framework"}],
        )

        mock_output_1 = [
            AIEvidenceItem(
                capability_name="FastAPI",
                strength=EvidenceStrength.MODERATE,
                evidence="Built basic FastAPI app.",
            )
        ]
        with patch(
            "app.services.evidence.extract_evidence_from_resume",
            new=AsyncMock(return_value=mock_output_1),
        ):
            res1 = await client.post(
                f"/api/v1/applications/{app_id}/evidence/analyze",
                headers=auth["headers"],
            )
        assert res1.status_code == 200
        assert res1.json()[0]["strength"] == "MODERATE"

        mock_output_2 = [
            AIEvidenceItem(
                capability_name="FastAPI",
                strength=EvidenceStrength.STRONG,
                evidence="Architected high-throughput FastAPI services.",
            )
        ]
        with patch(
            "app.services.evidence.extract_evidence_from_resume",
            new=AsyncMock(return_value=mock_output_2),
        ):
            res2 = await client.post(
                f"/api/v1/applications/{app_id}/evidence/analyze",
                headers=auth["headers"],
            )
        assert res2.status_code == 200
        ev_data = res2.json()
        assert len(ev_data) == 1
        assert ev_data[0]["strength"] == "STRONG"
        assert ev_data[0]["content"] == "Architected high-throughput FastAPI services."

        async with async_session_factory() as session:
            ev_list = (
                await session.scalars(
                    __import__("sqlalchemy", fromlist=["select"]).select(Evidence).where(Evidence.application_id == uuid.UUID(app_id))
                )
            ).all()
            assert len(ev_list) == 1


@pytest.mark.asyncio
async def test_capability_from_another_job_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps1 = await setup_application_with_capabilities_and_resume(
            client,
            auth,
            capabilities=[{"name": "Python", "description": "Lang"}],
        )

        job2_resp = await client.post(
            "/api/v1/jobs",
            headers=auth["headers"],
            json={"title": "Go Engineer", "description": "Golang role"},
        )
        job2_id = job2_resp.json()["id"]
        cap2_resp = await client.post(
            f"/api/v1/jobs/{job2_id}/capabilities",
            headers=auth["headers"],
            json={"name": "Golang", "description": "Go language"},
        )
        other_job_cap_id = cap2_resp.json()["id"]

        mock_output = [
            AIEvidenceItem(
                capability_name="Golang",
                strength=EvidenceStrength.STRONG,
                evidence="Go language experience.",
            )
        ]
        with patch(
            "app.services.evidence.extract_evidence_from_resume",
            new=AsyncMock(return_value=mock_output),
        ):
            res = await client.post(
                f"/api/v1/applications/{app_id}/evidence/analyze",
                headers=auth["headers"],
            )

        assert res.status_code == 200
        ev_data = res.json()
        assert len(ev_data) == 0


@pytest.mark.asyncio
async def test_evidence_content_grounding():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        resume_quote = "Designed PostgreSQL schemas and optimized SQL queries."
        app_id, _ = await setup_application_with_capabilities_and_resume(
            client,
            auth,
            capabilities=[{"name": "PostgreSQL", "description": "Relational DB"}],
            resume_text=resume_quote,
        )

        mock_output = [
            AIEvidenceItem(
                capability_name="PostgreSQL",
                strength=EvidenceStrength.STRONG,
                evidence=resume_quote,
            )
        ]

        with patch(
            "app.services.evidence.extract_evidence_from_resume",
            new=AsyncMock(return_value=mock_output),
        ):
            res = await client.post(
                f"/api/v1/applications/{app_id}/evidence/analyze",
                headers=auth["headers"],
            )

        assert res.status_code == 200
        assert res.json()[0]["content"] == resume_quote
