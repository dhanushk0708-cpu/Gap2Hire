from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.agents.evidence_research.graph import (
    create_evidence_research_graph,
    evidence_research_app,
)
from app.agents.evidence_research.nodes import (
    act_node,
    identify_unresolved_node,
    load_context_node,
    observe_node,
    think_node,
    update_state_node,
)
from app.agents.evidence_research.prompts import (
    extract_evidence_from_source,
    generate_research_decision,
)
from app.agents.evidence_research.schemas import (
    EvidenceExtractionResult,
    ResearchDecision,
    ResearchRunResult,
)
from app.agents.evidence_research.service import run_evidence_research
from app.agents.evidence_research.state import EvidenceResearchState
from app.agents.evidence_research.tools import (
    discover_candidate_links_impl,
    inspect_candidate_source_impl,
)
from app.db.session import async_session_factory
from app.main import app
from app.models.candidate_source import CandidateSource
from app.models.evidence import Evidence
from app.models.research_capability import ResearchCapabilityState
from app.models.research_event import ResearchEvent
from app.models.research_session import ResearchSession
from app.schemas.source_inspection import InspectionResult
from app.services.research_state import (
    ResearchSessionNotFoundError,
    create_research_session,
    get_research_session,
)


async def setup_agent_test_context(client: AsyncClient):
    """Sets up an organization, recruiter token, job, 2 capabilities, candidate, application, and sources."""
    org_name = f"Agent Corp {uuid4()}"
    email = f"lead-{uuid4()}@agentcorp.com"
    password = "SecurePassword123!"

    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Agent Test Lead",
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
        json={"name": "LangGraph", "description": "Stateful graph orchestration"},
    )
    cap1_id = cap1_resp.json()["id"]

    cap2_resp = await client.post(
        f"/api/v1/jobs/{job_id}/capabilities",
        headers=headers,
        json={"name": "FastAPI", "description": "High performance async web framework"},
    )
    cap2_id = cap2_resp.json()["id"]

    cand_resp = await client.post(
        "/api/v1/candidates",
        headers=headers,
        json={"email": f"cand-{uuid4()}@test.com", "full_name": "Test Candidate"},
    )
    cand_id = cand_resp.json()["id"]

    app_resp = await client.post(
        "/api/v1/applications",
        headers=headers,
        json={"candidate_id": cand_id, "job_id": job_id},
    )
    app_id = app_resp.json()["id"]

    # Register candidate sources
    src1_resp = await client.post(
        f"/api/v1/applications/{app_id}/sources",
        headers=headers,
        json={"url": "https://github.com/candidate/langgraph-demo", "source_type": "GITHUB"},
    )
    assert src1_resp.status_code == 201
    src1_id = src1_resp.json()["id"]

    src2_resp = await client.post(
        f"/api/v1/applications/{app_id}/sources",
        headers=headers,
        json={"url": "https://portfolio.candidate.dev/projects", "source_type": "PORTFOLIO"},
    )
    assert src2_resp.status_code == 201
    src2_id = src2_resp.json()["id"]

    return {
        "headers": headers,
        "org_id": org_id,
        "job_id": job_id,
        "cap1_id": cap1_id,
        "cap2_id": cap2_id,
        "cand_id": cand_id,
        "app_id": app_id,
        "src1_id": src1_id,
        "src2_id": src2_id,
    }


# ============================================================================
# 1. Graph Initialization
# ============================================================================
def test_graph_initialization():
    """1. Test that the StateGraph compiles and all required nodes are registered."""
    graph = create_evidence_research_graph()
    app_compiled = graph.compile()
    assert app_compiled is not None
    assert "load_context" in app_compiled.nodes
    assert "identify_unresolved" in app_compiled.nodes
    assert "think" in app_compiled.nodes
    assert "act" in app_compiled.nodes
    assert "observe" in app_compiled.nodes
    assert "update_state" in app_compiled.nodes


# ============================================================================
# 2. Context Loading Node
# ============================================================================
@pytest.mark.asyncio
async def test_load_context_node():
    """2. Test context loading populates graph state from persistent database."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_agent_test_context(client)

        async with async_session_factory() as session:
            sess = await create_research_session(
                session=session,
                organization_id=UUID(ctx["org_id"]),
                application_id=UUID(ctx["app_id"]),
            )
            sess_id = str(sess.id)

        initial_state: EvidenceResearchState = {
            "research_session_id": sess_id,
            "organization_id": ctx["org_id"],
            "max_iterations": 10,
        }

        updated_state = await load_context_node(initial_state)

        assert updated_state["application_id"] == ctx["app_id"]
        assert updated_state["job_id"] == ctx["job_id"]
        assert len(updated_state["capabilities"]) == 2
        assert len(updated_state["candidate_sources"]) == 2
        assert updated_state["capability_states"][ctx["cap1_id"]] == "UNKNOWN"
        assert updated_state["capability_states"][ctx["cap2_id"]] == "UNKNOWN"
        assert updated_state["status"] == "RUNNING"


# ============================================================================
# 3. Unresolved Capability Detection
# ============================================================================
@pytest.mark.asyncio
async def test_identify_unresolved_node():
    """3. Test identifying unresolved capabilities (UNKNOWN, INSUFFICIENT, etc.)."""
    state_unresolved: EvidenceResearchState = {
        "capability_states": {
            "cap-1": "UNKNOWN",
            "cap-2": "SUFFICIENT",
            "cap-3": "INSUFFICIENT",
        },
        "candidate_sources": [{"id": "src-1", "url": "https://github.com/test"}],
    }

    result = await identify_unresolved_node(state_unresolved)
    assert set(result["unresolved_capability_ids"]) == {"cap-1", "cap-3"}
    assert "stop_reason" not in result

    # When all resolved
    state_resolved: EvidenceResearchState = {
        "capability_states": {
            "cap-1": "SUFFICIENT",
            "cap-2": "SUFFICIENT",
        },
        "candidate_sources": [{"id": "src-1"}],
    }
    result_resolved = await identify_unresolved_node(state_resolved)
    assert len(result_resolved["unresolved_capability_ids"]) == 0
    assert "sufficient" in result_resolved["stop_reason"].lower()


# ============================================================================
# 4. Structured Research Decision
# ============================================================================
@pytest.mark.asyncio
async def test_structured_research_decision():
    """4. Test that ResearchDecision returns structured Pydantic model."""
    mock_decision_data = {
        "capability_id": str(uuid4()),
        "source_id": str(uuid4()),
        "reason": "GitHub repo contains Python code for evaluation",
        "evidence_target": "Practical implementation of LangGraph",
        "confidence": 0.85,
    }

    with patch(
        "app.agents.evidence_research.prompts.call_groq_json",
        new=AsyncMock(return_value=mock_decision_data),
    ):
        decision = await generate_research_decision(
            job_title="AI Engineer",
            job_description="LangGraph experience required",
            unresolved_capabilities=[{"id": mock_decision_data["capability_id"], "name": "LangGraph"}],
            available_sources=[{"id": mock_decision_data["source_id"], "url": "https://github.com/test"}],
            actions_taken=[],
        )

        assert isinstance(decision, ResearchDecision)
        assert str(decision.capability_id) == mock_decision_data["capability_id"]
        assert str(decision.source_id) == mock_decision_data["source_id"]
        assert decision.confidence == 0.85
        assert decision.reason == "GitHub repo contains Python code for evaluation"


# ============================================================================
# 5 & 6. Source Inspection Tool Uses Safe Inspector & Receives source_id
# ============================================================================
@pytest.mark.asyncio
async def test_inspect_candidate_source_tool_success():
    """5 & 6. Test that inspect_candidate_source_impl safe inspects registered CandidateSource."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_agent_test_context(client)

        inspection_val = InspectionResult(
            source_url="https://github.com/candidate/langgraph-demo",
            is_success=True,
            http_status=200,
            title="LangGraph Demo Repository",
            extracted_text="A demo demonstrating LangGraph stateful multi-agent workflows.",
            content_length=150,
        )

        with patch(
            "app.services.source_inspection.SourceInspector.inspect",
            new=AsyncMock(return_value=inspection_val),
        ):
            result = await inspect_candidate_source_impl(
                source_id=ctx["src1_id"],
                organization_id=ctx["org_id"],
                application_id=ctx["app_id"],
            )

            assert result["is_success"] is True
            assert result["title"] == "LangGraph Demo Repository"
            assert "LangGraph" in result["extracted_text"]
            assert result["source_id"] == ctx["src1_id"]

            # Verify database candidate source was updated
            async with async_session_factory() as session:
                source = await session.get(CandidateSource, UUID(ctx["src1_id"]))
                assert source.status == "INSPECTED"
                assert source.title == "LangGraph Demo Repository"


# ============================================================================
# 7 & 8. Invalid and Cross-Application Source Rejection
# ============================================================================
@pytest.mark.asyncio
async def test_cross_application_source_rejected():
    """7 & 8. Test that cross-application sources are rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx1 = await setup_agent_test_context(client)
        ctx2 = await setup_agent_test_context(client)

        # Attempt to inspect app1's source using app2's application_id
        result = await inspect_candidate_source_impl(
            source_id=ctx1["src1_id"],
            organization_id=ctx1["org_id"],
            application_id=ctx2["app_id"],  # Cross-application mismatch
        )

        assert result["is_success"] is False
        assert "different application" in result["error"]


# ============================================================================
# 9. Grounded Evidence Extraction with Provenance
# ============================================================================
@pytest.mark.asyncio
async def test_grounded_evidence_with_provenance():
    """9. Test that supported evidence extracts factual claim and updates state."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_agent_test_context(client)

        async with async_session_factory() as session:
            sess = await create_research_session(
                session=session,
                organization_id=UUID(ctx["org_id"]),
                application_id=UUID(ctx["app_id"]),
            )
            sess_id = str(sess.id)

        # Mock observe extraction
        mock_extraction = {
            "capability_id": ctx["cap1_id"],
            "supported": True,
            "claim": "Candidate built LangGraph multi-agent systems in Python",
            "explanation": "Repository contains state graph implementations.",
            "source_excerpt": "import langgraph",
            "strength": "STRONG",
            "provenance": "DEMONSTRATED",
        }

        with patch(
            "app.agents.evidence_research.prompts.call_groq_json",
            new=AsyncMock(return_value=mock_extraction),
        ):
            state: EvidenceResearchState = {
                "research_session_id": sess_id,
                "organization_id": ctx["org_id"],
                "application_id": ctx["app_id"],
                "current_capability_id": ctx["cap1_id"],
                "current_source_id": ctx["src1_id"],
                "capabilities": [{"id": ctx["cap1_id"], "name": "LangGraph"}],
                "candidate_sources": [{"id": ctx["src1_id"], "url": "https://github.com/candidate/langgraph-demo", "source_type": "GITHUB"}],
                "last_observation": {
                    "is_success": True,
                    "extracted_text": "import langgraph\nworkflow = StateGraph()",
                },
                "capability_states": {ctx["cap1_id"]: "UNKNOWN", ctx["cap2_id"]: "UNKNOWN"},
                "iteration_count": 0,
                "max_iterations": 5,
            }

            observe_res = await observe_node(state)
            state.update(observe_res)

            update_res = await update_state_node(state)
            assert update_res["capability_states"][ctx["cap1_id"]] == "SUFFICIENT"

            # Check database for created Evidence record with provenance
            async with async_session_factory() as session:
                ev_stmt = select(Evidence).where(
                    Evidence.application_id == UUID(ctx["app_id"]),
                    Evidence.capability_id == UUID(ctx["cap1_id"]),
                )
                evidence = await session.scalar(ev_stmt)
                assert evidence is not None
                assert evidence.candidate_source_id == UUID(ctx["src1_id"])
                assert evidence.source_type == "GITHUB"
                assert evidence.strength == "STRONG"
                assert evidence.provenance == "DEMONSTRATED"
                assert "LangGraph" in evidence.content


# ============================================================================
# 10. Unsupported Source Does Not Create Evidence (Semantic Rule)
# ============================================================================
@pytest.mark.asyncio
async def test_unsupported_source_does_not_create_evidence():
    """10. Test that unsupported source marks INSUFFICIENT without creating Evidence or concluding lack of skill."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_agent_test_context(client)

        async with async_session_factory() as session:
            sess = await create_research_session(
                session=session,
                organization_id=UUID(ctx["org_id"]),
                application_id=UUID(ctx["app_id"]),
            )
            sess_id = str(sess.id)

        mock_extraction = {
            "capability_id": ctx["cap2_id"],
            "supported": False,
            "claim": None,
            "explanation": "No mention or implementation of FastAPI in inspected repository.",
            "source_excerpt": None,
            "strength": "INSUFFICIENT",
            "provenance": "CLAIM",
        }

        with patch(
            "app.agents.evidence_research.prompts.call_groq_json",
            new=AsyncMock(return_value=mock_extraction),
        ):
            state: EvidenceResearchState = {
                "research_session_id": sess_id,
                "organization_id": ctx["org_id"],
                "application_id": ctx["app_id"],
                "current_capability_id": ctx["cap2_id"],
                "current_source_id": ctx["src1_id"],
                "capabilities": [{"id": ctx["cap2_id"], "name": "FastAPI"}],
                "candidate_sources": [{"id": ctx["src1_id"], "url": "https://github.com/candidate/langgraph-demo", "source_type": "GITHUB"}],
                "last_observation": {
                    "is_success": True,
                    "extracted_text": "Irrelevant repository content",
                },
                "capability_states": {ctx["cap1_id"]: "UNKNOWN", ctx["cap2_id"]: "UNKNOWN"},
                "iteration_count": 0,
                "max_iterations": 5,
            }

            observe_res = await observe_node(state)
            state.update(observe_res)

            update_res = await update_state_node(state)
            # Capability is marked INSUFFICIENT, not lacking skill
            assert update_res["capability_states"][ctx["cap2_id"]] == "INSUFFICIENT"

            # Verify NO Evidence was created in database
            async with async_session_factory() as session:
                ev_stmt = select(Evidence).where(
                    Evidence.application_id == UUID(ctx["app_id"]),
                    Evidence.capability_id == UUID(ctx["cap2_id"]),
                )
                evidence = await session.scalar(ev_stmt)
                assert evidence is None

                # Verify CapabilityState in DB is INSUFFICIENT
                cap_state_stmt = select(ResearchCapabilityState).where(
                    ResearchCapabilityState.research_session_id == UUID(sess_id),
                    ResearchCapabilityState.capability_id == UUID(ctx["cap2_id"]),
                )
                cap_state = await session.scalar(cap_state_stmt)
                assert cap_state.state == "INSUFFICIENT"


# ============================================================================
# 11 & 12. Research Events Created and Auditable
# ============================================================================
@pytest.mark.asyncio
async def test_research_events_logged_during_execution():
    """11 & 12. Test that auditable ResearchEvent records are persisted."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_agent_test_context(client)

        async with async_session_factory() as session:
            sess = await create_research_session(
                session=session,
                organization_id=UUID(ctx["org_id"]),
                application_id=UUID(ctx["app_id"]),
            )
            sess_id = str(sess.id)

        inspection_val = InspectionResult(
            source_url="https://github.com/candidate/langgraph-demo",
            is_success=True,
            http_status=200,
            title="LangGraph Repo",
            extracted_text="Demonstrates LangGraph pipelines.",
            content_length=100,
        )

        with patch(
            "app.services.source_inspection.SourceInspector.inspect",
            new=AsyncMock(return_value=inspection_val),
        ):
            state: EvidenceResearchState = {
                "research_session_id": sess_id,
                "organization_id": ctx["org_id"],
                "application_id": ctx["app_id"],
                "current_capability_id": ctx["cap1_id"],
                "current_source_id": ctx["src1_id"],
                "current_decision": {"reason": "Test inspection"},
                "candidate_sources": [{"id": ctx["src1_id"], "url": "https://github.com/candidate/langgraph-demo"}],
            }

            await act_node(state)

            # Check database events
            async with async_session_factory() as session:
                events_stmt = (
                    select(ResearchEvent)
                    .where(ResearchEvent.research_session_id == UUID(sess_id))
                    .order_by(ResearchEvent.created_at.asc())
                )
                events = (await session.scalars(events_stmt)).all()
                event_types = [e.event_type for e in events]
                assert "SOURCE_SELECTED" in event_types
                assert "SOURCE_INSPECTION_COMPLETED" in event_types


# ============================================================================
# 13. Max Iterations Stops Loop Deterministically
# ============================================================================
@pytest.mark.asyncio
async def test_max_iterations_stops_loop():
    """13. Test that exceeding max_iterations halts research loop deterministically."""
    state: EvidenceResearchState = {
        "research_session_id": str(uuid4()),
        "organization_id": str(uuid4()),
        "application_id": str(uuid4()),
        "current_capability_id": str(uuid4()),
        "current_source_id": str(uuid4()),
        "capabilities": [],
        "candidate_sources": [],
        "last_extraction": {"supported": False, "explanation": "Not found"},
        "capability_states": {"cap-1": "UNKNOWN"},
        "iteration_count": 9,
        "max_iterations": 10,
    }

    with patch("app.agents.evidence_research.nodes.async_session_factory"):
        with patch("app.agents.evidence_research.nodes.update_capability_state"):
            with patch("app.agents.evidence_research.nodes.create_research_event"):
                result = await update_state_node(state)
                assert result["iteration_count"] == 10
                assert "maximum research iteration limit" in result["stop_reason"]


# ============================================================================
# 14 & 15. End-to-End Service Run & Endpoint
# ============================================================================
@pytest.mark.asyncio
async def test_run_evidence_research_endpoint_full_cycle():
    """14 & 15. Test running evidence research via the POST endpoint completing successfully."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx = await setup_agent_test_context(client)

        # 1. Create a session
        sess_resp = await client.post(
            f"/api/v1/applications/{ctx['app_id']}/research-sessions",
            headers=ctx["headers"],
            json={"metadata": {"test": "run"}},
        )
        assert sess_resp.status_code == 201
        sess_id = sess_resp.json()["id"]

        inspection_val = InspectionResult(
            source_url="https://github.com/candidate/langgraph-demo",
            is_success=True,
            http_status=200,
            title="LangGraph Demo",
            extracted_text="LangGraph workflows and Python APIs",
            content_length=120,
        )

        async def dynamic_mock_groq(system_prompt: str, user_prompt: str, mock_response=None):
            if "Evidence Research Agent" in system_prompt or "unresolved capabilities" in user_prompt.lower():
                if ctx["cap2_id"] in user_prompt:
                    cap_id = ctx["cap2_id"]
                    src_id = ctx["src2_id"]
                else:
                    cap_id = ctx["cap1_id"]
                    src_id = ctx["src1_id"]

                return {
                    "capability_id": cap_id,
                    "source_id": src_id,
                    "reason": "Test inspection of source",
                    "evidence_target": "Skill implementation",
                    "confidence": 0.9,
                }
            else:
                cap_id = ctx["cap2_id"] if "FastAPI" in user_prompt else ctx["cap1_id"]
                return {
                    "capability_id": cap_id,
                    "supported": True,
                    "claim": "Candidate demonstrated required technical skills in source code",
                    "explanation": "Repository contains state graph implementations.",
                    "source_excerpt": "import langgraph",
                    "strength": "STRONG",
                    "provenance": "DEMONSTRATED",
                }

        with patch(
            "app.services.source_inspection.SourceInspector.inspect",
            new=AsyncMock(return_value=inspection_val),
        ):
            with patch(
                "app.agents.evidence_research.prompts.call_groq_json",
                side_effect=dynamic_mock_groq,
            ):
                run_resp = await client.post(
                    f"/api/v1/research-sessions/{sess_id}/run",
                    headers=ctx["headers"],
                )
                assert run_resp.status_code == 200
                data = run_resp.json()
                assert data["research_session_id"] == sess_id
                assert data["status"] == "COMPLETED"
                assert data["iterations_run"] >= 1
                assert data["sources_inspected"] >= 1

                # Check database status
                session_detail = await client.get(
                    f"/api/v1/research-sessions/{sess_id}",
                    headers=ctx["headers"],
                )
                assert session_detail.status_code == 200
                det = session_detail.json()
                assert det["status"] == "COMPLETED"
                assert det["completed_at"] is not None
                event_types = [e["event_type"] for e in det["events"]]
                assert "SESSION_STARTED" in event_types
                assert "RESEARCH_COMPLETED" in event_types


# ============================================================================
# 16. Tenant Isolation Enforcement
# ============================================================================
@pytest.mark.asyncio
async def test_tenant_isolation_on_run_endpoint():
    """16. Test that another tenant cannot trigger research on a foreign session."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ctx1 = await setup_agent_test_context(client)
        ctx2 = await setup_agent_test_context(client)

        # Create session in Org 1
        sess_resp = await client.post(
            f"/api/v1/applications/{ctx1['app_id']}/research-sessions",
            headers=ctx1["headers"],
        )
        assert sess_resp.status_code == 201
        sess1_id = sess_resp.json()["id"]

        # Attempt to run session from Org 2
        forbidden_run = await client.post(
            f"/api/v1/research-sessions/{sess1_id}/run",
            headers=ctx2["headers"],
        )
        assert forbidden_run.status_code == 404
