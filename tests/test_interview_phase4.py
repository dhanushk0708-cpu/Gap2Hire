import io
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.roles import UserRole
from app.core.security import create_access_token
from app.db.session import async_session_factory
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.interview_answer_analysis import InterviewAnswerAnalysis
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


async def setup_approved_plan_and_session():
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
    round_id = uuid4()
    pq1_id = uuid4()
    pq2_id = uuid4()
    session_id = uuid4()

    async with async_session_factory() as session:
        org = Organization(id=org_id, name="Phase4 Org", slug=f"p4-{org_id.hex[:6]}")
        user = User(
            id=user_id,
            email=f"recruiter_{user_id.hex[:6]}@example.com",
            full_name="Phase4 Recruiter",
            role=UserRole.RECRUITER.value,
            organization_id=org_id,
            password_hash="fakehash",
            is_active=True,
        )
        job = Job(
            id=job_id,
            organization_id=org_id,
            created_by=user_id,
            title="Backend Engineer",
            description="Python & Distributed Systems",
            status="PUBLISHED",
            shortlist_size=5,
        )
        cand = Candidate(
            id=cand_id,
            full_name="Alice Candidate",
            email=f"alice_{cand_id.hex[:6]}@example.com",
        )
        application = Application(
            id=app_id,
            job_id=job_id,
            candidate_id=cand_id,
            status="SHORTLISTED",
            shortlist_status="SHORTLISTED",
            resume_text="Experienced in Python concurrency and async IO.",
        )
        cap1 = Capability(
            id=cap1_id,
            job_id=job_id,
            name="Python AsyncIO",
            description="Understanding event loop and coroutines",
            importance="CRITICAL",
        )
        cap2 = Capability(
            id=cap2_id,
            job_id=job_id,
            name="PostgreSQL Optimization",
            description="Query optimization and indexes",
            importance="HIGH",
        )
        dataset_file = InterviewDatasetFile(
            id=dataset_file_id,
            organization_id=org_id,
            job_id=job_id,
            filename="questions.xlsx",
            file_hash="hash123",
            total_questions=2,
            created_by=user_id,
        )
        dataset = InterviewQuestionDataset(
            id=dataset_id,
            file_id=dataset_file_id,
            organization_id=org_id,
            name="Backend Technical",
            concept="Python AsyncIO",
            question_count=2,
        )
        dq1 = InterviewDatasetQuestion(
            id=uuid4(),
            dataset_id=dataset_id,
            organization_id=org_id,
            question_text="How does the Python event loop handle non-blocking IO?",
            concept="Python AsyncIO",
            difficulty="MEDIUM",
            question_type="CONCEPTUAL",
        )
        dq2 = InterviewDatasetQuestion(
            id=uuid4(),
            dataset_id=dataset_id,
            organization_id=org_id,
            question_text="Explain EXPLAIN ANALYZE in PostgreSQL and index scans.",
            concept="PostgreSQL Optimization",
            difficulty="HARD",
            question_type="CONCEPTUAL",
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
        round_obj = InterviewPlanRound(
            id=round_id,
            plan_id=plan_id,
            round_number=1,
            title="Technical Core",
            objective="Evaluate Python and DB internals",
            concepts=["Python AsyncIO", "PostgreSQL Optimization"],
            sequence=1,
        )
        pq1 = InterviewPlanQuestion(
            id=pq1_id,
            round_id=round_id,
            dataset_question_id=dq1.id,
            question_text="How does the Python event loop handle non-blocking IO?",
            concept="Python AsyncIO",
            difficulty="MEDIUM",
            question_type="CONCEPTUAL",
            sequence=1,
        )
        pq2 = InterviewPlanQuestion(
            id=pq2_id,
            round_id=round_id,
            dataset_question_id=dq2.id,
            question_text="Explain EXPLAIN ANALYZE in PostgreSQL and index scans.",
            concept="PostgreSQL Optimization",
            difficulty="HARD",
            question_type="CONCEPTUAL",
            sequence=2,
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
            concept="Python AsyncIO",
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
        await session.flush()

        session.add_all([dq1, dq2, plan])
        await session.flush()

        session.add(round_obj)
        await session.flush()

        session.add_all([pq1, pq2])
        await session.flush()

        session.add_all([interview_session, q1])
        await session.commit()

    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}
    return {
        "org_id": org_id,
        "user_id": user_id,
        "job_id": job_id,
        "app_id": app_id,
        "session_id": session_id,
        "q1_id": q1.id,
        "pq1_id": pq1_id,
        "pq2_id": pq2_id,
        "headers": headers,
    }


@pytest.mark.asyncio
async def test_sufficient_answer_selects_next_planned_question():
    """1. Sufficient answer -> next planned question from approved plan."""
    ctx = await setup_approved_plan_and_session()
    session_id = ctx["session_id"]
    q1_id = ctx["q1_id"]

    mock_analysis = {
        "answer_quality": "SUFFICIENT",
        "evidence_state": "DEMONSTRATED",
        "key_findings": ["Clearly explained select/epoll multiplexing and task scheduling"],
        "missing_points": [],
        "follow_up_needed": False,
        "follow_up_reason": "",
    }

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                f"/api/v1/interviews/{session_id}/questions/{q1_id}/answer",
                headers=ctx["headers"],
                json={"answer": "The event loop uses OS selectors like epoll/kqueue to register file descriptors and polls for readiness without blocking the execution thread."},
            )
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["analysis"]["answer_quality"] == "SUFFICIENT"
            assert data["analysis"]["evidence_state"] == "DEMONSTRATED"
            assert data["action"] == "NEXT_QUESTION"
            assert data["next_question"] is not None
            assert "EXPLAIN ANALYZE" in data["next_question"]["question"]
            assert data["next_question"]["question_type"] == "PLANNED"
            assert data["next_question"]["plan_question_id"] == str(ctx["pq2_id"])


@pytest.mark.asyncio
async def test_partial_answer_generates_targeted_follow_up():
    """2. Partial answer -> generates targeted follow-up probing missing points."""
    ctx = await setup_approved_plan_and_session()
    session_id = ctx["session_id"]
    q1_id = ctx["q1_id"]

    mock_analysis = {
        "answer_quality": "PARTIAL",
        "evidence_state": "VERIFICATION_NEEDED",
        "key_findings": ["Mentioned async/await syntax"],
        "missing_points": ["Did not explain underlying selector/OS polling mechanism"],
        "follow_up_needed": True,
        "follow_up_reason": "Needs to explain OS level IO multiplexing",
    }
    mock_follow_up = "How does the event loop interact with OS epoll/kqueue to monitor socket readiness?"

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)), \
         patch("app.services.interview.generate_targeted_follow_up", AsyncMock(return_value=mock_follow_up)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                f"/api/v1/interviews/{session_id}/questions/{q1_id}/answer",
                headers=ctx["headers"],
                json={"answer": "You write async def and await coroutines and the loop runs them."},
            )
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["analysis"]["answer_quality"] == "PARTIAL"
            assert data["analysis"]["evidence_state"] == "VERIFICATION_NEEDED"
            assert data["action"] == "FOLLOW_UP"
            assert data["next_question"] is not None
            assert data["next_question"]["question_type"] == "FOLLOW_UP"
            assert data["next_question"]["question"] == mock_follow_up


@pytest.mark.asyncio
async def test_insufficient_answer_generates_targeted_follow_up():
    """3. Insufficient answer -> generates targeted follow-up probing basic concept."""
    ctx = await setup_approved_plan_and_session()
    session_id = ctx["session_id"]
    q1_id = ctx["q1_id"]

    mock_analysis = {
        "answer_quality": "INSUFFICIENT",
        "evidence_state": "UNKNOWN",
        "key_findings": [],
        "missing_points": ["Entire event loop mechanism"],
        "follow_up_needed": True,
        "follow_up_reason": "Candidate provided vague non-technical answer",
    }
    mock_follow_up = "Can you describe what a coroutine is and how asyncio.gather executes tasks concurrently?"

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)), \
         patch("app.services.interview.generate_targeted_follow_up", AsyncMock(return_value=mock_follow_up)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                f"/api/v1/interviews/{session_id}/questions/{q1_id}/answer",
                headers=ctx["headers"],
                json={"answer": "I haven't used that much."},
            )
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["analysis"]["answer_quality"] == "INSUFFICIENT"
            assert data["analysis"]["evidence_state"] == "UNKNOWN"
            assert data["action"] == "FOLLOW_UP"
            assert data["next_question"]["question_type"] == "FOLLOW_UP"


@pytest.mark.asyncio
async def test_analysis_is_persisted():
    """4. Analysis is persisted in the database via InterviewAnswerAnalysis."""
    ctx = await setup_approved_plan_and_session()
    session_id = ctx["session_id"]
    q1_id = ctx["q1_id"]

    mock_analysis = {
        "answer_quality": "SUFFICIENT",
        "evidence_state": "DEMONSTRATED",
        "key_findings": ["Strong mastery of selectors"],
        "missing_points": [],
        "follow_up_needed": False,
        "follow_up_reason": "",
    }

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                f"/api/v1/interviews/{session_id}/questions/{q1_id}/answer",
                headers=ctx["headers"],
                json={"answer": "Detailed answer demonstrating full understanding."},
            )
            assert res.status_code == 200

    # Query DB directly to verify persistence
    async with async_session_factory() as session:
        from sqlalchemy import select
        stmt = select(InterviewAnswerAnalysis).where(
            InterviewAnswerAnalysis.session_id == session_id,
            InterviewAnswerAnalysis.question_id == q1_id,
        )
        record = await session.scalar(stmt)
        assert record is not None
        assert record.analysis["answer_quality"] == "SUFFICIENT"
        assert record.analysis["evidence_state"] == "DEMONSTRATED"
        assert "Strong mastery" in record.analysis["key_findings"][0]


@pytest.mark.asyncio
async def test_duplicate_planned_question_prevented():
    """5. Duplicate planned questions are prevented."""
    ctx = await setup_approved_plan_and_session()
    session_id = ctx["session_id"]
    q1_id = ctx["q1_id"]

    # First answer (sufficient) moves to question 2
    mock_analysis_1 = {
        "answer_quality": "SUFFICIENT",
        "evidence_state": "DEMONSTRATED",
        "key_findings": ["Good"],
        "missing_points": [],
        "follow_up_needed": False,
        "follow_up_reason": "",
    }

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis_1)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res1 = await client.post(
                f"/api/v1/interviews/{session_id}/questions/{q1_id}/answer",
                headers=ctx["headers"],
                json={"answer": "First answer."},
            )
            assert res1.status_code == 200
            q2_data = res1.json()["next_question"]
            q2_id = q2_data["id"]

            # Second answer (sufficient) -> all planned questions exhausted
            res2 = await client.post(
                f"/api/v1/interviews/{session_id}/questions/{q2_id}/answer",
                headers=ctx["headers"],
                json={"answer": "Second answer."},
            )
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["action"] == "ROUND_COMPLETE"
            assert data2["next_question"] is None


@pytest.mark.asyncio
async def test_duplicate_follow_up_prevented():
    """6. Duplicate follow-up question text is detected and prevented."""
    ctx = await setup_approved_plan_and_session()
    session_id = ctx["session_id"]
    q1_id = ctx["q1_id"]

    mock_analysis = {
        "answer_quality": "PARTIAL",
        "evidence_state": "VERIFICATION_NEEDED",
        "key_findings": [],
        "missing_points": ["Task scheduling"],
        "follow_up_needed": True,
        "follow_up_reason": "Explain scheduling",
    }
    # Return the exact same text as the initial question to test duplicate prevention
    duplicate_text = "How does the Python event loop handle non-blocking IO?"

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)), \
         patch("app.services.interview.generate_targeted_follow_up", AsyncMock(return_value=duplicate_text)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                f"/api/v1/interviews/{session_id}/questions/{q1_id}/answer",
                headers=ctx["headers"],
                json={"answer": "Partial answer."},
            )
            assert res.status_code == 200
            next_q = res.json()["next_question"]
            # The system must not output the exact duplicate
            assert next_q["question"] != duplicate_text
            assert "Python AsyncIO" in next_q["question"] or "Task scheduling" in next_q["question"]


@pytest.mark.asyncio
async def test_approved_plan_is_respected():
    """7. Approved plan sequence and question content is strictly respected."""
    ctx = await setup_approved_plan_and_session()
    session_id = ctx["session_id"]
    q1_id = ctx["q1_id"]

    mock_analysis = {
        "answer_quality": "SUFFICIENT",
        "evidence_state": "DEMONSTRATED",
        "key_findings": ["Understands async"],
        "missing_points": [],
        "follow_up_needed": False,
        "follow_up_reason": "",
    }

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                f"/api/v1/interviews/{session_id}/questions/{q1_id}/answer",
                headers=ctx["headers"],
                json={"answer": "Comprehensive answer."},
            )
            assert res.status_code == 200
            next_q = res.json()["next_question"]
            # Must strictly be Question 2 from the approved plan
            assert next_q["question"] == "Explain EXPLAIN ANALYZE in PostgreSQL and index scans."
            assert next_q["concept"] == "PostgreSQL Optimization"
            assert next_q["plan_question_id"] == str(ctx["pq2_id"])


@pytest.mark.asyncio
async def test_tenant_isolation():
    """8. Tenant isolation: unauthorized organization cannot submit answers."""
    ctx = await setup_approved_plan_and_session()
    session_id = ctx["session_id"]
    q1_id = ctx["q1_id"]

    # Other tenant
    other_org_id = uuid4()
    other_user_id = uuid4()
    async with async_session_factory() as session:
        other_org = Organization(id=other_org_id, name="Other Org", slug=f"other-{other_org_id.hex[:6]}")
        other_user = User(
            id=other_user_id,
            email=f"intruder_{other_user_id.hex[:6]}@example.com",
            full_name="Other User",
            role=UserRole.RECRUITER.value,
            organization_id=other_org_id,
            password_hash="fakehash",
            is_active=True,
        )
        session.add_all([other_org, other_user])
        await session.commit()

    other_token = create_access_token(str(other_user_id))
    other_headers = {"Authorization": f"Bearer {other_token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/interviews/{session_id}/questions/{q1_id}/answer",
            headers=other_headers,
            json={"answer": "Attempted answer from other tenant"},
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_round_completion_when_no_questions_remain():
    """9. Round completion when all approved questions have been answered."""
    ctx = await setup_approved_plan_and_session()
    session_id = ctx["session_id"]
    q1_id = ctx["q1_id"]

    mock_analysis = {
        "answer_quality": "SUFFICIENT",
        "evidence_state": "DEMONSTRATED",
        "key_findings": ["All good"],
        "missing_points": [],
        "follow_up_needed": False,
        "follow_up_reason": "",
    }

    with patch("app.services.interview.analyze_interview_answer", AsyncMock(return_value=mock_analysis)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res1 = await client.post(
                f"/api/v1/interviews/{session_id}/questions/{q1_id}/answer",
                headers=ctx["headers"],
                json={"answer": "Answer 1"},
            )
            assert res1.status_code == 200
            q2_id = res1.json()["next_question"]["id"]

            res2 = await client.post(
                f"/api/v1/interviews/{session_id}/questions/{q2_id}/answer",
                headers=ctx["headers"],
                json={"answer": "Answer 2"},
            )
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["action"] == "ROUND_COMPLETE"
            assert data2["next_question"] is None
