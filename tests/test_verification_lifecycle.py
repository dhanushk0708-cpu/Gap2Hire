import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import async_session_factory
from app.main import app
from app.models.evidence import Evidence
from tests.test_candidates_applications import (
    create_candidate_user,
    create_registered_client,
)
from tests.test_evidence import setup_application_with_capabilities_and_resume


async def setup_test_verification(
    client: AsyncClient,
    auth: dict,
) -> tuple[str, str, str]:
    app_id, caps = await setup_application_with_capabilities_and_resume(
        client,
        auth,
        capabilities=[{"name": "Redis", "description": "Caching layer", "importance": "HIGH"}],
        resume_text="Backend engineer with Python experience.",
    )
    cap_id = caps[0]["id"]

    res = await client.post(
        f"/api/v1/applications/{app_id}/verifications",
        headers=auth["headers"],
        json={
            "capability_id": cap_id,
            "type": "PRACTICAL_TASK",
            "instructions": "Build Redis caching layer",
        },
    )
    assert res.status_code == 201
    verif_id = res.json()["id"]
    return app_id, cap_id, verif_id


@pytest.mark.asyncio
async def test_start_requested_to_in_progress():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        _, _, verif_id = await setup_test_verification(client, auth)

        res = await client.patch(
            f"/api/v1/verifications/{verif_id}/start",
            headers=auth["headers"],
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "IN_PROGRESS"
        assert data["result"] is None
        assert data["completed_at"] is None


@pytest.mark.asyncio
async def test_submit_in_progress_to_submitted():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        _, _, verif_id = await setup_test_verification(client, auth)

        # Start first
        await client.patch(
            f"/api/v1/verifications/{verif_id}/start",
            headers=auth["headers"],
        )

        # Submit
        res = await client.patch(
            f"/api/v1/verifications/{verif_id}/submit",
            headers=auth["headers"],
            json={"submission_content": "https://github.com/candidate/redis-demo"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUBMITTED"
        assert data["submission_content"] == "https://github.com/candidate/redis-demo"
        assert data["result"] is None
        assert data["completed_at"] is None


@pytest.mark.asyncio
async def test_review_submitted_to_reviewed_pass():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        _, _, verif_id = await setup_test_verification(client, auth)

        # Start -> Submit -> Review
        await client.patch(f"/api/v1/verifications/{verif_id}/start", headers=auth["headers"])
        await client.patch(
            f"/api/v1/verifications/{verif_id}/submit",
            headers=auth["headers"],
            json={"submission_content": "Code submitted"},
        )

        res = await client.patch(
            f"/api/v1/verifications/{verif_id}/review",
            headers=auth["headers"],
            json={
                "result": "PASS",
                "review_notes": "Clean implementation with solid test coverage.",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "REVIEWED"
        assert data["result"] == "PASS"
        assert data["review_notes"] == "Clean implementation with solid test coverage."
        assert data["reviewed_by"] is not None
        assert data["completed_at"] is not None


@pytest.mark.asyncio
async def test_review_results_partial_and_fail():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        _, _, v1 = await setup_test_verification(client, auth)
        _, _, v2 = await setup_test_verification(client, auth)

        # PARTIAL review
        await client.patch(f"/api/v1/verifications/{v1}/start", headers=auth["headers"])
        await client.patch(f"/api/v1/verifications/{v1}/submit", headers=auth["headers"], json={"submission_content": "Partial solution"})
        res_partial = await client.patch(
            f"/api/v1/verifications/{v1}/review",
            headers=auth["headers"],
            json={"result": "PARTIAL", "review_notes": "Needs improvement"},
        )
        assert res_partial.status_code == 200
        assert res_partial.json()["result"] == "PARTIAL"

        # FAIL review
        await client.patch(f"/api/v1/verifications/{v2}/start", headers=auth["headers"])
        await client.patch(f"/api/v1/verifications/{v2}/submit", headers=auth["headers"], json={"submission_content": "Incorrect code"})
        res_fail = await client.patch(
            f"/api/v1/verifications/{v2}/review",
            headers=auth["headers"],
            json={"result": "FAIL", "review_notes": "Does not meet requirements"},
        )
        assert res_fail.status_code == 200
        assert res_fail.json()["result"] == "FAIL"


@pytest.mark.asyncio
async def test_cancel_from_requested_in_progress_and_submitted():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        _, _, v1 = await setup_test_verification(client, auth)
        _, _, v2 = await setup_test_verification(client, auth)
        _, _, v3 = await setup_test_verification(client, auth)

        # Cancel from REQUESTED
        res1 = await client.patch(f"/api/v1/verifications/{v1}/cancel", headers=auth["headers"])
        assert res1.status_code == 200
        assert res1.json()["status"] == "CANCELLED"

        # Cancel from IN_PROGRESS
        await client.patch(f"/api/v1/verifications/{v2}/start", headers=auth["headers"])
        res2 = await client.patch(f"/api/v1/verifications/{v2}/cancel", headers=auth["headers"])
        assert res2.status_code == 200
        assert res2.json()["status"] == "CANCELLED"

        # Cancel from SUBMITTED
        await client.patch(f"/api/v1/verifications/{v3}/start", headers=auth["headers"])
        await client.patch(f"/api/v1/verifications/{v3}/submit", headers=auth["headers"], json={"submission_content": "Draft"})
        res3 = await client.patch(f"/api/v1/verifications/{v3}/cancel", headers=auth["headers"])
        assert res3.status_code == 200
        assert res3.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_invalid_state_transitions():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        _, _, verif_id = await setup_test_verification(client, auth)

        # Direct submit from REQUESTED -> 400
        sub_res = await client.patch(
            f"/api/v1/verifications/{verif_id}/submit",
            headers=auth["headers"],
            json={"submission_content": "Content"},
        )
        assert sub_res.status_code == 400

        # Direct review from REQUESTED -> 400
        rev_res = await client.patch(
            f"/api/v1/verifications/{verif_id}/review",
            headers=auth["headers"],
            json={"result": "PASS"},
        )
        assert rev_res.status_code == 400

        # Direct review from IN_PROGRESS -> 400
        await client.patch(f"/api/v1/verifications/{verif_id}/start", headers=auth["headers"])
        rev_inp_res = await client.patch(
            f"/api/v1/verifications/{verif_id}/review",
            headers=auth["headers"],
            json={"result": "PASS"},
        )
        assert rev_inp_res.status_code == 400


@pytest.mark.asyncio
async def test_reviewed_and_cancelled_are_terminal():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        _, _, v_rev = await setup_test_verification(client, auth)
        _, _, v_can = await setup_test_verification(client, auth)

        # Complete v_rev to REVIEWED
        await client.patch(f"/api/v1/verifications/{v_rev}/start", headers=auth["headers"])
        await client.patch(f"/api/v1/verifications/{v_rev}/submit", headers=auth["headers"], json={"submission_content": "Code"})
        await client.patch(f"/api/v1/verifications/{v_rev}/review", headers=auth["headers"], json={"result": "PASS"})

        # Cancel v_can
        await client.patch(f"/api/v1/verifications/{v_can}/cancel", headers=auth["headers"])

        # REVIEWED terminal assertions
        assert (await client.patch(f"/api/v1/verifications/{v_rev}/start", headers=auth["headers"])).status_code == 400
        assert (await client.patch(f"/api/v1/verifications/{v_rev}/submit", headers=auth["headers"], json={"submission_content": "New"})).status_code == 400
        assert (await client.patch(f"/api/v1/verifications/{v_rev}/review", headers=auth["headers"], json={"result": "FAIL"})).status_code == 400
        assert (await client.patch(f"/api/v1/verifications/{v_rev}/cancel", headers=auth["headers"])).status_code == 400

        # CANCELLED terminal assertions
        assert (await client.patch(f"/api/v1/verifications/{v_can}/start", headers=auth["headers"])).status_code == 400
        assert (await client.patch(f"/api/v1/verifications/{v_can}/submit", headers=auth["headers"], json={"submission_content": "New"})).status_code == 400
        assert (await client.patch(f"/api/v1/verifications/{v_can}/review", headers=auth["headers"], json={"result": "PASS"})).status_code == 400
        assert (await client.patch(f"/api/v1/verifications/{v_can}/cancel", headers=auth["headers"])).status_code == 400


@pytest.mark.asyncio
async def test_submission_content_validation():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        _, _, verif_id = await setup_test_verification(client, auth)
        await client.patch(f"/api/v1/verifications/{verif_id}/start", headers=auth["headers"])

        # Empty string -> 422
        res = await client.patch(
            f"/api/v1/verifications/{verif_id}/submit",
            headers=auth["headers"],
            json={"submission_content": ""},
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_cross_tenant_isolation():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth_company_1 = await create_registered_client(client)
        auth_company_2 = await create_registered_client(client)
        _, _, verif_id = await setup_test_verification(client, auth_company_1)

        headers2 = auth_company_2["headers"]
        assert (await client.patch(f"/api/v1/verifications/{verif_id}/start", headers=headers2)).status_code == 404
        assert (await client.patch(f"/api/v1/verifications/{verif_id}/submit", headers=headers2, json={"submission_content": "Sub"})).status_code == 404
        assert (await client.patch(f"/api/v1/verifications/{verif_id}/review", headers=headers2, json={"result": "PASS"})).status_code == 404
        assert (await client.patch(f"/api/v1/verifications/{verif_id}/cancel", headers=headers2)).status_code == 404


@pytest.mark.asyncio
async def test_security_authorization_roles():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        verif_id = str(uuid.uuid4())

        # Candidate role -> 403
        cand_auth = await create_candidate_user(auth["organization_id"])
        cand_res = await client.patch(
            f"/api/v1/verifications/{verif_id}/start",
            headers=cand_auth["headers"],
        )
        assert cand_res.status_code == 403

        # Unauthenticated -> 401
        unauth_res = await client.patch(
            f"/api/v1/verifications/{verif_id}/start",
        )
        assert unauth_res.status_code == 401


@pytest.mark.asyncio
async def test_no_evidence_created_automatically():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        auth = await create_registered_client(client)
        app_id, _, verif_id = await setup_test_verification(client, auth)

        # Full lifecycle execution
        await client.patch(f"/api/v1/verifications/{verif_id}/start", headers=auth["headers"])
        await client.patch(f"/api/v1/verifications/{verif_id}/submit", headers=auth["headers"], json={"submission_content": "Completed task"})
        await client.patch(f"/api/v1/verifications/{verif_id}/review", headers=auth["headers"], json={"result": "PASS", "review_notes": "Great"})

        # Confirm evidence table remains empty for this application
        async with async_session_factory() as session:
            ev_list = (
                await session.scalars(
                    __import__("sqlalchemy", fromlist=["select"]).select(Evidence).where(Evidence.application_id == uuid.UUID(app_id))
                )
            ).all()
            assert len(ev_list) == 0
