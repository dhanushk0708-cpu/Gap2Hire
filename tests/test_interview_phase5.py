import io
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.roles import UserRole
from app.core.security import create_access_token
from app.db.session import async_session_factory
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.interview_dataset import (
    InterviewDatasetFile,
    InterviewDatasetQuestion,
    InterviewQuestionDataset,
)
from app.models.interview_plan import (
    InterviewPlan,
    InterviewPlanQuestion,
    InterviewPlanRound,
)
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User


async def setup_multi_round_approved_plan_and_session():
    """
    Sets up a 2-round interview plan:
    Round 1: 1 question on Python & FastAPI
    Round 2: 1 question on PostgreSQL & Redis
    """
    org_id = uuid4()
    user_id = uuid4()
    job_id = uuid4()
    cand_id = uuid4()
    app_id = uuid4()
    cap1_id = uuid4()
    cap2_id = uuid4()
    dataset_file_id = uuid4()
    dataset_id = uuid4()
    plan_id = uuid4()
    round1_id = uuid4()
    round2_id = uuid4()
    pq1_id = uuid4()
    pq2_id = uuid4()
    session_id = uuid4()

    async with async_session_factory() as session:
        org = Organization(id=org_id, name="Phase5 Org", slug=f"p5-{org_id.hex[:6]}")
        user = User(
            id=user_id,
            email=f"recruiter_{user_id.hex[:6]}@example.com",
            full_name="Phase5 Recruiter",
            role=UserRole.RECRQUITER.value if hasattr(UserRole, "RECRQUITER") else UserRole.RECRUITER.value,
            organization_id=org_id,
            password_hash="fakehash",
            is_active=True,
        )
        job = Job(
            id=job_id,
            organization_id=org_id,
            created_by=user_id,
            title="Senior Backend Engineer",
            description="Python, FastAPI, Postgres, Redis",
            status="PUBLISHED",
            shortlist_size=5,
        )
        cand = Candidate(
            id=cand_id,
            full_name="Bob Engineer",
            email=f"bob_{cand_id.hex[:6]}@example.com",
        )
        application = Application(
            id=app_id,
            job_id=job_id,
            candidate_id=cand_id,
            status="SHORTLISTED",
            shortlist_status="SHORTLISTED",
            resume_text="Senior engineer with FastAPI and Redis experience.",
        )
        cap1 = Capability(
            id=cap1_id,
            job_id=job_id,
            name="Python & FastAPI",
            description="REST APIs and async programming",
            importance="CRITICAL",
        )
        cap2 = Capability(
            id=cap2_id,
            job_id=job_id,
            name="PostgreSQL & Redis",
            description="Data persistence and distributed caching",
            importance="HIGH",
        )
        dataset_file = InterviewDatasetFile(
            id=dataset_file_id,
            organization_id=org_id,
            job_id=job_id,
            filename="phase5_questions.xlsx",
            file_hash="hash_p5_123",
            total_questions=2,
            created_by=user_id,
        )
        dataset = InterviewQuestionDataset(
            id=dataset_id,
            file_id=dataset_file_id,
            organization_id=org_id,
            name="Backend Multi-Round Dataset",
            concept="Backend Engineering",
            question_count=2,
        )
        dq1 = InterviewDatasetQuestion(
            id=uuid4(),
            dataset_id=dataset_id,
            organization_id=org_id,
            question_text="How does FastAPI manage dependency injection with async dependencies?",
            concept="Python & FastAPI",
            difficulty="MEDIUM",
            question_type="CONCEPTUAL",
        )
        dq2 = InterviewDatasetQuestion(
            id=uuid4(),
            dataset_id=dataset_id,
            organization_id=org_id,
            question_text="Explain Redis cluster sharding and cache invalidation strategies with PostgreSQL.",
            concept="PostgreSQL & Redis",
            difficulty="HARD",
            question_type="ARCHITECTURE",
        )

        plan = InterviewPlan(
            id=plan_id,
            organization_id=org_id,
            application_id=app_id,
            job_id=job_id,
            dataset_file_id=dataset_file_id,
            status="APPROVED",
            version=1,
            approved_by=user_id,
        )
        round1 = InterviewPlanRound(
            id=round1_id,
            plan_id=plan_id,
            round_number=1,
            title="Round 1: Python & FastAPI",
            objective="Evaluate core Python async and API architecture",
            concepts=["Python & FastAPI"],
            sequence=1,
        )
        round2 = InterviewPlanRound(
            id=round2_id,
            plan_id=plan_id,
            round_number=2,
            title="Round 2: PostgreSQL & Redis",
            objective="Evaluate database scaling and caching strategies",
            concepts=["PostgreSQL & Redis"],
            sequence=2,
        )
        pq1 = InterviewPlanQuestion(
            id=pq1_id,
            round_id=round1_id,
            dataset_question_id=dq1.id,
            question_text="How does FastAPI manage dependency injection with async dependencies?",
            concept="Python & FastAPI",
            difficulty="MEDIUM",
            question_type="CONCEPTUAL",
            sequence=1,
        )
        pq2 = InterviewPlanQuestion(
            id=pq2_id,
            round_id=round2_id,
            dataset_question_id=dq2.id,
            question_text="Explain Redis cluster sharding and cache invalidation strategies with PostgreSQL.",
            concept="PostgreSQL & Redis",
            difficulty="HARD",
            question_type="ARCHITECTURE",
            sequence=1,
        )

        interview_session = InterviewSession(
            id=session_id,
            application_id=app_id,
            status="IN_PROGRESS",
        )
        q1 = InterviewQuestion(
            id=uuid4(),
            session_id=session_id,
            capability_id=cap1_id,
            plan_question_id=pq1_id,
            question_type="PLANNED",
            concept="Python & FastAPI",
            question=pq1.question_text,
            sequence_number=1,
        )

        session.add(org)
        session.add(user)
        await session.flush()

        session.add(job)
        session.add(cand)
        await session.flush()

        session.add(cap1)
        session.add(cap2)
        session.add(application)
        session.add(dataset_file)
        await session.flush()

        session.add(dataset)
        session.add(dq1)
        session.add(dq2)
        session.add(plan)
        await session.flush()

        session.add(round1)
        session.add(round2)
        await session.flush()

        session.add(pq1)
        session.add(pq2)
        await session.flush()

        session.add(interview_session)
        session.add(q1)
        await session.commit()

    return {
        "org_id": org_id,
        "user_id": user_id,
        "job_id": job_id,
        "cand_id": cand_id,
        "app_id": app_id,
        "plan_id": plan_id,
        "round1_id": round1_id,
        "round2_id": round2_id,
        "session_id": session_id,
        "q1_id": q1.id,
        "pq1_id": pq1_id,
        "pq2_id": pq2_id,
        "q1_text": pq1.question_text,
        "q2_text": pq2.question_text,
    }


@pytest.mark.asyncio
async def test_round_1_starts_correctly():
    """Verify that when the interview starts, Round 1's planned question is loaded."""
    setup = await setup_multi_round_approved_plan_and_session()
    token = create_access_token(str(setup["user_id"]))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            f"/api/v1/interviews/{setup['session_id']}/state",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["interview_status"] == "IN_PROGRESS"
        assert data["round_status"] == "IN_PROGRESS"
        assert data["current_round"]["round_number"] == 1
        assert "Python & FastAPI" in data["current_round"]["title"]
        assert data["current_question"] == setup["q1_text"]
        assert data["questions_completed"] == 0


@pytest.mark.asyncio
async def test_completing_round_1_moves_to_round_2():
    """Verify that answering Round 1's final question transitions the session to Round 2."""
    setup = await setup_multi_round_approved_plan_and_session()
    token = create_access_token(str(setup["user_id"]))

    mock_analysis = {
        "answer_quality": "SUFFICIENT",
        "evidence_state": "DEMONSTRATED",
        "key_findings": ["Clear explanation of async Depends and yield generators."],
        "missing_points": [],
        "follow_up_needed": False,
        "follow_up_reason": "",
    }

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                f"/api/v1/interviews/{setup['session_id']}/questions/{setup['q1_id']}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={"answer": "FastAPI uses Depends() with async def and AsyncExitStack to resolve and tear down dependencies gracefully."},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["action"] == "NEXT_QUESTION"
            assert data["round_number"] == 2
            assert "PostgreSQL & Redis" in data["round_title"]
            assert data["next_question"] is not None
            assert data["next_question"]["question"] == setup["q2_text"]
            assert data["next_question"]["round_number"] == 2


@pytest.mark.asyncio
async def test_follow_up_stays_inside_current_round():
    """Verify that an insufficient/partial answer in Round 1 triggers a follow-up question in Round 1."""
    setup = await setup_multi_round_approved_plan_and_session()
    token = create_access_token(str(setup["user_id"]))

    mock_analysis = {
        "answer_quality": "PARTIAL",
        "evidence_state": "VERIFICATION_NEEDED",
        "key_findings": ["Mentioned Depends but did not explain async lifecycle."],
        "missing_points": ["Async yield cleanup handling"],
        "follow_up_needed": True,
        "follow_up_reason": "Need clarification on yield generator lifecycle in FastAPI",
    }
    mock_followup = "Could you explain how FastAPI handles cleanup when using yield in dependencies?"

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)), \
         patch("app.services.interview.generate_targeted_follow_up", AsyncMock(return_value=mock_followup)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                f"/api/v1/interviews/{setup['session_id']}/questions/{setup['q1_id']}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={"answer": "FastAPI has a Depends function that injects parameters."},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["action"] == "FOLLOW_UP"
            assert data["round_number"] == 1
            assert "Python & FastAPI" in data["round_title"]
            assert data["next_question"]["question_type"] == "FOLLOW_UP"
            assert data["next_question"]["question"] == mock_followup
            assert data["next_question"]["round_number"] == 1


@pytest.mark.asyncio
async def test_round_2_starts_with_its_planned_question():
    """Verify Round 2 starts with the exact question defined in the approved plan for Round 2."""
    setup = await setup_multi_round_approved_plan_and_session()
    token = create_access_token(str(setup["user_id"]))

    mock_analysis = {
        "answer_quality": "SUFFICIENT",
        "evidence_state": "DEMONSTRATED",
        "key_findings": ["Understands async DI."],
        "missing_points": [],
        "follow_up_needed": False,
        "follow_up_reason": "",
    }

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                f"/api/v1/interviews/{setup['session_id']}/questions/{setup['q1_id']}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={"answer": "Comprehensive answer on FastAPI dependency injection."},
            )
            assert res.status_code == 200
            res_data = res.json()
            assert res_data["round_number"] == 2
            assert res_data["next_question"]["question"] == setup["q2_text"]
            assert res_data["next_question"]["plan_question_id"] == str(setup["pq2_id"])


@pytest.mark.asyncio
async def test_duplicate_prevention_across_rounds():
    """Verify that duplicate questions are prevented across rounds and cannot be served twice."""
    setup = await setup_multi_round_approved_plan_and_session()
    token = create_access_token(str(setup["user_id"]))

    mock_analysis = {
        "answer_quality": "SUFFICIENT",
        "evidence_state": "DEMONSTRATED",
        "key_findings": ["Good answer."],
        "missing_points": [],
        "follow_up_needed": False,
        "follow_up_reason": "",
    }

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                f"/api/v1/interviews/{setup['session_id']}/questions/{setup['q1_id']}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={"answer": "Detailed answer for Round 1 question."},
            )
            assert res.status_code == 200
            q2_info = res.json()["next_question"]
            assert q2_info["id"] is not None
            assert q2_info["question"] != setup["q1_text"]


@pytest.mark.asyncio
async def test_final_round_completion_marks_interview_completed():
    """Verify that completing the last planned question in the final round marks the interview session COMPLETED."""
    setup = await setup_multi_round_approved_plan_and_session()
    token = create_access_token(str(setup["user_id"]))

    mock_analysis = {
        "answer_quality": "SUFFICIENT",
        "evidence_state": "DEMONSTRATED",
        "key_findings": ["All concepts addressed."],
        "missing_points": [],
        "follow_up_needed": False,
        "follow_up_reason": "",
    }

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Answer Round 1 question
            res1 = await ac.post(
                f"/api/v1/interviews/{setup['session_id']}/questions/{setup['q1_id']}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={"answer": "Solid answer on FastAPI DI."},
            )
            assert res1.status_code == 200
            q2_id = res1.json()["next_question"]["id"]

            # 2. Answer Round 2 (final) question
            res2 = await ac.post(
                f"/api/v1/interviews/{setup['session_id']}/questions/{q2_id}/answer",
                headers={"Authorization": f"Bearer {token}"},
                json={"answer": "Redis sharding uses 16384 hash slots with write-through cache pattern to Postgres."},
            )
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["action"] == "ROUND_COMPLETE"
            assert data2["interview_status"] == "COMPLETED"
            assert data2["round_status"] == "COMPLETED"
            assert data2["next_question"] is None

            # 3. Check state endpoint confirms COMPLETED status
            state_res = await ac.get(
                f"/api/v1/interviews/{setup['session_id']}/state",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert state_res.status_code == 200
            state_data = state_res.json()
            assert state_data["interview_status"] == "COMPLETED"
            assert state_data["questions_completed"] == 2
            assert state_data["total_planned_questions"] == 2


@pytest.mark.asyncio
async def test_current_state_endpoint_response():
    """Verify that GET /api/v1/interviews/{session_id}/state returns the required fields."""
    setup = await setup_multi_round_approved_plan_and_session()
    token = create_access_token(str(setup["user_id"]))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            f"/api/v1/interviews/{setup['session_id']}/state",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        # Verify required keys
        assert "current_round" in data
        assert "current_question" in data
        assert "round_status" in data
        assert "interview_status" in data
        assert "questions_completed" in data
        assert "follow_up_count" in data
        assert data["total_rounds"] == 2
        assert len(data["rounds"]) == 2


@pytest.mark.asyncio
async def test_tenant_isolation_on_round_execution():
    """Verify another organization cannot inspect or answer questions of a tenant session."""
    setup = await setup_multi_round_approved_plan_and_session()

    # Create another tenant user
    other_org_id = uuid4()
    other_user_id = uuid4()
    async with async_session_factory() as session:
        other_org = Organization(id=other_org_id, name="Other Org", slug=f"oth-{other_org_id.hex[:6]}")
        other_user = User(
            id=other_user_id,
            email=f"intruder_{other_user_id.hex[:6]}@example.com",
            full_name="Other Recruiter",
            role=UserRole.RECRUITER.value,
            organization_id=other_org_id,
            password_hash="fakehash",
            is_active=True,
        )
        session.add(other_org)
        session.add(other_user)
        await session.commit()

    other_token = create_access_token(str(other_user_id))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # State inspection denied / not found
        res_state = await ac.get(
            f"/api/v1/interviews/{setup['session_id']}/state",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert res_state.status_code == 404

        # Answer submission denied / not found
        res_ans = await ac.post(
            f"/api/v1/interviews/{setup['session_id']}/questions/{setup['q1_id']}/answer",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"answer": "Malicious answer"},
        )
        assert res_ans.status_code == 404
