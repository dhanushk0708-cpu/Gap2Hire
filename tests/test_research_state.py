from uuid import uuid4
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import async_session_factory
from app.main import app
from app.models.application import Application
from app.models.candidate_source import CandidateSource
from app.models.research_capability import ResearchCapabilityState
from app.models.research_event import ResearchEvent
from app.models.research_session import ResearchSession
from app.schemas.research_state import ResearchSessionUpdate
from app.services.research_state import (
    ApplicationNotFoundError,
    InvalidSourceTenantError,
    ResearchCapabilityStateNotFoundError,
    ResearchSessionNotFoundError,
    create_research_event,
    create_research_session,
    get_capability_states,
    get_research_events,
    get_research_session,
    update_capability_state,
    update_research_session,
)


async def setup_test_context(client: AsyncClient):
    """Creates an organization, manager token, job with 2 capabilities, candidate, and application."""
    org_name = f"Research Corp {uuid4()}"
    email = f"lead-{uuid4()}@researchcorp.com"
    password = "SecurePassword123!"

    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Research Test Lead",
            "organization_name": org_name,
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    org_id = me_resp.json()["organization_id"]

    job_resp = await client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"title": "Senior AI Architect", "description": "LangGraph & Python APIs"},
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    cap1_resp = await client.post(
        f"/api/v1/jobs/{job_id}/capabilities",
        headers=headers,
        json={"name": "LangGraph", "description": "Multi-agent workflows"},
    )
    cap1_id = cap1_resp.json()["id"]

    cap2_resp = await client.post(
        f"/api/v1/jobs/{job_id}/capabilities",
        headers=headers,
        json={"name": "PostgreSQL", "description": "Relational data modeling"},
    )
    cap2_id = cap2_resp.json()["id"]

    cand_resp = await client.post(
        "/api/v1/candidates",
        headers=headers,
        json={"email": f"cand-{uuid4()}@research.com", "full_name": "Research Candidate"},
    )
    cand_id = cand_resp.json()["id"]

    app_resp = await client.post(
        "/api/v1/applications",
        headers=headers,
        json={"candidate_id": cand_id, "job_id": job_id},
    )
    app_id = app_resp.json()["id"]

    return {
        "headers": headers,
        "org_id": org_id,
        "job_id": job_id,
        "cap1_id": cap1_id,
        "cap2_id": cap2_id,
        "cand_id": cand_id,
        "app_id": app_id,
    }


@pytest.mark.asyncio
async def test_create_and_get_research_session():
    """1 & 2. Test creating and retrieving a research session with initial event and capability states."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/research-sessions",
            headers=ctx["headers"],
            json={"metadata": {"target_role": "AI Architect"}},
        )
        assert resp.status_code == 201
        sess_data = resp.json()
        sess_id = sess_data["id"]

        assert sess_data["application_id"] == ctx["app_id"]
        assert sess_data["status"] == "PENDING"
        assert sess_data["metadata"]["target_role"] == "AI Architect"

        # Get session detail
        get_resp = await client.get(
            f"/api/v1/research-sessions/{sess_id}",
            headers=ctx["headers"],
        )
        assert get_resp.status_code == 200
        detail = get_resp.json()
        assert detail["id"] == sess_id
        assert len(detail["capability_states"]) == 2
        assert len(detail["events"]) == 1
        assert detail["events"][0]["event_type"] == "SESSION_STARTED"


@pytest.mark.asyncio
async def test_all_capabilities_receive_unknown_initially():
    """4 & 5. Test that all job capabilities are initialized in UNKNOWN state."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        async with async_session_factory() as session:
            sess = await create_research_session(
                session=session,
                organization_id=ctx["org_id"],
                application_id=ctx["app_id"],
            )
            states = await get_capability_states(
                session=session,
                organization_id=ctx["org_id"],
                session_id=sess.id,
            )

            assert len(states) == 2
            cap_ids = {str(s.capability_id) for s in states}
            assert ctx["cap1_id"] in cap_ids
            assert ctx["cap2_id"] in cap_ids
            for s in states:
                assert s.state == "UNKNOWN"
                assert s.reason is None
                assert s.last_checked_at is None


@pytest.mark.asyncio
async def test_update_research_session_status():
    """3. Test updating research session status and fields."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        create_resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/research-sessions",
            headers=ctx["headers"],
        )
        sess_id = create_resp.json()["id"]

        patch_resp = await client.patch(
            f"/api/v1/research-sessions/{sess_id}",
            headers=ctx["headers"],
            json={"status": "RUNNING"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["status"] == "RUNNING"

        # Complete session
        complete_resp = await client.patch(
            f"/api/v1/research-sessions/{sess_id}",
            headers=ctx["headers"],
            json={"status": "COMPLETED", "stop_reason": "All required capabilities corroborated"},
        )
        assert complete_resp.status_code == 200
        assert complete_resp.json()["status"] == "COMPLETED"
        assert complete_resp.json()["stop_reason"] == "All required capabilities corroborated"
        assert complete_resp.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_duplicate_capability_state_prevented():
    """6. Test unique constraint preventing duplicate capability states in the same session."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        async with async_session_factory() as session:
            sess = await create_research_session(
                session=session,
                organization_id=ctx["org_id"],
                application_id=ctx["app_id"],
            )

            # Attempt to manually insert a duplicate state for cap1
            dup_state = ResearchCapabilityState(
                research_session_id=sess.id,
                capability_id=ctx["cap1_id"],
                state="INVESTIGATING",
            )
            session.add(dup_state)
            with pytest.raises(IntegrityError):
                await session.commit()


@pytest.mark.asyncio
async def test_update_capability_state():
    """7. Test updating a capability state and reasoning via service and API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        create_resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/research-sessions",
            headers=ctx["headers"],
        )
        sess_id = create_resp.json()["id"]

        update_resp = await client.patch(
            f"/api/v1/research-sessions/{sess_id}/capabilities/{ctx['cap1_id']}",
            headers=ctx["headers"],
            json={
                "state": "SUFFICIENT",
                "reason": "Demonstrated open-source LangGraph multi-agent architecture in GitHub repo.",
            },
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["state"] == "SUFFICIENT"
        assert "LangGraph multi-agent" in data["reason"]
        assert data["last_checked_at"] is not None


@pytest.mark.asyncio
async def test_create_and_retrieve_research_events_chronological():
    """8 & 9. Test logging events and retrieving them in chronological order."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        # Create source
        src_resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/sources",
            headers=ctx["headers"],
            json={"url": "https://github.com/candidate/langgraph-demo", "source_type": "GITHUB"},
        )
        source_id = src_resp.json()["id"]

        create_resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/research-sessions",
            headers=ctx["headers"],
        )
        sess_id = create_resp.json()["id"]

        # Log event 1: SOURCE_SELECTED
        e1_resp = await client.post(
            f"/api/v1/research-sessions/{sess_id}/events",
            headers=ctx["headers"],
            json={
                "event_type": "SOURCE_SELECTED",
                "source_id": source_id,
                "message": "Selected candidate GitHub source for inspection.",
            },
        )
        assert e1_resp.status_code == 201

        # Log event 2: EVIDENCE_FOUND
        e2_resp = await client.post(
            f"/api/v1/research-sessions/{sess_id}/events",
            headers=ctx["headers"],
            json={
                "event_type": "EVIDENCE_FOUND",
                "source_id": source_id,
                "capability_id": ctx["cap1_id"],
                "message": "Found LangGraph graph orchestration code in repo.",
            },
        )
        assert e2_resp.status_code == 201

        # Retrieve events
        events_resp = await client.get(
            f"/api/v1/research-sessions/{sess_id}/events",
            headers=ctx["headers"],
        )
        assert events_resp.status_code == 200
        events = events_resp.json()

        assert len(events) == 3  # SESSION_STARTED, SOURCE_SELECTED, EVIDENCE_FOUND
        assert events[0]["event_type"] == "SESSION_STARTED"
        assert events[1]["event_type"] == "SOURCE_SELECTED"
        assert events[2]["event_type"] == "EVIDENCE_FOUND"
        assert events[2]["source_id"] == source_id
        assert events[2]["capability_id"] == ctx["cap1_id"]


@pytest.mark.asyncio
async def test_cross_tenant_access_denied():
    """10, 11, 12. Test cross-organization isolation for session access, capability update, and event creation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx_a = await setup_test_context(client)
        ctx_b = await setup_test_context(client)

        # Create session in Tenant A
        create_resp = await client.post(
            f"/api/v1/applications/{ctx_a['app_id']}/research-sessions",
            headers=ctx_a["headers"],
        )
        sess_a_id = create_resp.json()["id"]

        # Tenant B tries to GET Tenant A session -> 404
        get_resp = await client.get(
            f"/api/v1/research-sessions/{sess_a_id}",
            headers=ctx_b["headers"],
        )
        assert get_resp.status_code == 404

        # Tenant B tries to PATCH Tenant A capability -> 404
        cap_resp = await client.patch(
            f"/api/v1/research-sessions/{sess_a_id}/capabilities/{ctx_a['cap1_id']}",
            headers=ctx_b["headers"],
            json={"state": "SUFFICIENT"},
        )
        assert cap_resp.status_code == 404

        # Tenant B tries to create event on Tenant A session -> 404
        evt_resp = await client.post(
            f"/api/v1/research-sessions/{sess_a_id}/events",
            headers=ctx_b["headers"],
            json={"event_type": "SOURCE_SELECTED", "message": "Cross tenant event"},
        )
        assert evt_resp.status_code == 404


@pytest.mark.asyncio
async def test_cascading_delete_on_application():
    """13. Test that deleting Application cascades ResearchSession, capability states, and events."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        async with async_session_factory() as session:
            sess = await create_research_session(
                session=session,
                organization_id=ctx["org_id"],
                application_id=ctx["app_id"],
            )
            sess_id = sess.id

            await create_research_event(
                session=session,
                organization_id=ctx["org_id"],
                session_id=sess_id,
                event_type="RESEARCH_PAUSED",
            )

        # Delete Application
        async with async_session_factory() as session:
            app_stmt = select(Application).where(Application.id == ctx["app_id"])
            app_obj = await session.scalar(app_stmt)
            await session.delete(app_obj)
            await session.commit()

        # Check cascading deletion
        async with async_session_factory() as session:
            sess_stmt = select(ResearchSession).where(ResearchSession.id == sess_id)
            assert (await session.scalar(sess_stmt)) is None

            cap_stmt = select(ResearchCapabilityState).where(
                ResearchCapabilityState.research_session_id == sess_id
            )
            assert len((await session.scalars(cap_stmt)).all()) == 0

            evt_stmt = select(ResearchEvent).where(
                ResearchEvent.research_session_id == sess_id
            )
            assert len((await session.scalars(evt_stmt)).all()) == 0


@pytest.mark.asyncio
async def test_deleting_candidate_source_preserves_research_events():
    """14. Test ON DELETE SET NULL on source_id in ResearchSession and ResearchEvent."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_test_context(client)

        src_resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/sources",
            headers=ctx["headers"],
            json={"url": "https://github.com/temp/source", "source_type": "GITHUB"},
        )
        source_id = src_resp.json()["id"]

        async with async_session_factory() as session:
            sess = await create_research_session(
                session=session,
                organization_id=ctx["org_id"],
                application_id=ctx["app_id"],
            )
            sess_id = sess.id

            await update_research_session(
                session=session,
                organization_id=ctx["org_id"],
                session_id=sess_id,
                data=ResearchSessionUpdate(current_source_id=source_id),
            )

            evt = await create_research_event(
                session=session,
                organization_id=ctx["org_id"],
                session_id=sess_id,
                event_type="SOURCE_INSPECTION_COMPLETED",
                source_id=source_id,
                message="Inspected temporary source",
            )
            evt_id = evt.id

        # Delete CandidateSource
        async with async_session_factory() as session:
            src_stmt = select(CandidateSource).where(CandidateSource.id == source_id)
            src_obj = await session.scalar(src_stmt)
            await session.delete(src_obj)
            await session.commit()

        # Verify ResearchSession and ResearchEvent still exist with source_id = None
        async with async_session_factory() as session:
            sess_stmt = select(ResearchSession).where(ResearchSession.id == sess_id)
            preserved_sess = await session.scalar(sess_stmt)
            assert preserved_sess is not None
            assert preserved_sess.current_source_id is None

            evt_stmt = select(ResearchEvent).where(ResearchEvent.id == evt_id)
            preserved_evt = await session.scalar(evt_stmt)
            assert preserved_evt is not None
            assert preserved_evt.source_id is None
            assert preserved_evt.message == "Inspected temporary source"
