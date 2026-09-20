import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import async_session_factory
from app.main import app
from app.models.evidence import Evidence
from tests.test_candidates_applications import create_registered_client
from tests.test_evidence_summary import setup_summary_application


async def inject_provenance_evidence(
    application_id: str,
    capability_id: str,
    strength: str,
    provenance: str,
    content: str | None,
):
    async with async_session_factory() as session:
        ev = Evidence(
            application_id=uuid.UUID(application_id),
            capability_id=uuid.UUID(capability_id),
            source_type="RESUME",
            strength=strength,
            provenance=provenance,
            content=content,
        )
        session.add(ev)
        await session.commit()


@pytest.mark.asyncio
async def test_resume_evidence_has_claim_provenance():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_summary_application(
            client,
            auth,
            capabilities=[{"name": "Python", "description": "Language"}],
        )

        await inject_provenance_evidence(
            application_id=app_id,
            capability_id=caps[0]["id"],
            strength="STRONG",
            provenance="CLAIM",
            content="5 years Python experience",
        )

        response = await client.get(
            f"/api/v1/applications/{app_id}/evidence/summary",
            headers=auth["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        c0 = data["capabilities"][0]
        assert c0["name"] == "Python"
        assert c0["strength"] == "STRONG"
        assert c0["provenance"] == "CLAIM"
        assert c0["state"] == "KNOWN"


@pytest.mark.asyncio
async def test_summary_distinguishes_claim_from_demonstrated_evidence():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, caps = await setup_summary_application(
            client,
            auth,
            capabilities=[
                {"name": "Redis", "description": "Caching"},
                {"name": "FastAPI", "description": "Web Framework"},
            ],
        )

        await inject_provenance_evidence(
            application_id=app_id,
            capability_id=caps[0]["id"],
            strength="STRONG",
            provenance="CLAIM",
            content="Resume claims Redis expert",
        )
        await inject_provenance_evidence(
            application_id=app_id,
            capability_id=caps[1]["id"],
            strength="STRONG",
            provenance="DEMONSTRATED",
            content="Passed practical code assessment",
        )

        response = await client.get(
            f"/api/v1/applications/{app_id}/evidence/summary",
            headers=auth["headers"],
        )
        assert response.status_code == 200
        summary_caps = response.json()["capabilities"]

        redis_cap = next(c for c in summary_caps if c["name"] == "Redis")
        fastapi_cap = next(c for c in summary_caps if c["name"] == "FastAPI")

        assert redis_cap["provenance"] == "CLAIM"
        assert fastapi_cap["provenance"] == "DEMONSTRATED"
