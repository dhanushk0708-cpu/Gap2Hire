from datetime import datetime, timedelta, timezone
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
from app.models.interview_plan import (
    InterviewPlan,
    InterviewPlanQuestion,
    InterviewPlanRound,
)
from app.models.interview_schedule import InterviewSchedule
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User


async def setup_test_context():
    org_id = uuid4()
    user_id = uuid4()
    job_id = uuid4()
    cand_id = uuid4()
    app_id = uuid4()

    async with async_session_factory() as session:
        org = Organization(id=org_id, name="HR Editor Org", slug=f"org-{org_id.hex[:6]}")
        user = User(
            id=user_id,
            email=f"hr_{user_id.hex[:6]}@example.com",
            full_name="HR Manager",
            role=UserRole.RECRUITER.value,
            organization_id=org_id,
            password_hash="fakehash",
            is_active=True,
        )
        job = Job(
            id=job_id,
            organization_id=org_id,
            created_by=user_id,
            title="Senior Platform Engineer",
            description="High scale distributed systems and cloud infrastructure",
            status="PUBLISHED",
            shortlist_size=5,
        )
        cand = Candidate(
            id=cand_id,
            full_name="Samantha Ray",
            email=f"samantha_{cand_id.hex[:6]}@example.com",
        )
        application = Application(
            id=app_id,
            job_id=job_id,
            candidate_id=cand_id,
            status="SHORTLISTED",
            shortlist_status="SHORTLISTED",
            resume_text="Senior developer with strong Python, Kubernetes, and PostgreSQL experience.",
        )
        cap1 = Capability(
            id=uuid4(),
            job_id=job_id,
            name="Distributed Systems",
            description="Microservices and event-driven architecture",
            importance="CRITICAL",
        )
        cap2 = Capability(
            id=uuid4(),
            job_id=job_id,
            name="PostgreSQL",
            description="Query optimization and connection pooling",
            importance="HIGH",
        )

        session.add(org)
        await session.flush()
        session.add(user)
        await session.flush()
        session.add(job)
        await session.flush()
        session.add(cand)
        await session.flush()
        session.add(application)
        await session.flush()
        session.add_all([cap1, cap2])
        await session.flush()
        await session.commit()

    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}
    return {
        "org_id": org_id,
        "user_id": user_id,
        "job_id": job_id,
        "cand_id": cand_id,
        "app_id": app_id,
        "headers": headers,
    }


@pytest.mark.asyncio
async def test_create_and_retrieve_interview_plan():
    ctx = await setup_test_context()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create plan
        res = await ac.post(
            f"/api/v1/applications/{ctx['app_id']}/interview/plans",
            headers=ctx["headers"],
            json={},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["application_id"] == str(ctx["app_id"])
        assert data["version"] == 1
        assert data["lock_version"] == 1
        assert data["status"] == "DRAFT"
        assert len(data["rounds"]) >= 1

        # Check structured fields on round
        round1 = data["rounds"][0]
        assert "evaluation_criteria" in round1
        assert "expected_evidence" in round1
        assert round1["question_generation_mode"] in ["AI_GENERATED", "HR_DEFINED", "HYBRID"]
        assert round1["difficulty"] in ["EASY", "MEDIUM", "HARD"]

        # Retrieve plan by ID
        get_res = await ac.get(f"/api/v1/interview-plans/{data['id']}", headers=ctx["headers"])
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["id"] == data["id"]
        assert len(get_data["rounds"]) == len(data["rounds"])


@pytest.mark.asyncio
async def test_edit_reorder_and_delete_rounds():
    ctx = await setup_test_context()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Create initial draft plan
        res = await ac.post(
            f"/api/v1/applications/{ctx['app_id']}/interview/plans",
            headers=ctx["headers"],
            json={},
        )
        plan_id = res.json()["id"]

        # 2. Modify rounds: reorder, add round, delete round, edit criteria
        updated_rounds = [
            {
                "round_number": 1,
                "title": "Custom Round A — System Architecture",
                "objective": "Deep-dive into multi-region architecture.",
                "description": "Architectural resilience and failover.",
                "concepts": ["Architecture", "Resilience"],
                "evaluation_criteria": ["Understands CAP theorem trade-offs.", "Explains replication lag."],
                "expected_evidence": ["Past outage post-mortem walkthrough."],
                "question_generation_mode": "HYBRID",
                "difficulty": "HARD",
                "estimated_duration_minutes": 45,
                "required": True,
                "sequence": 1,
                "questions": [
                    {
                        "question_text": "How do you design active-active database replication across two AWS regions?",
                        "concept": "Architecture",
                        "difficulty": "HARD",
                        "question_type": "SYSTEM_DESIGN",
                        "purpose": "Test multi-region database understanding",
                        "evidence_being_verified": "Multi-region replication",
                        "is_hr_authored": True,
                        "status": "APPROVED",
                        "sequence": 1,
                    }
                ],
            },
            {
                "round_number": 2,
                "title": "Custom Round B — Coding & Concurrency",
                "objective": "Evaluate thread safety and async programming.",
                "description": "Live programming and concurrency review.",
                "concepts": ["Concurrency", "AsyncIO"],
                "evaluation_criteria": ["Avoids deadlocks.", "Uses proper synchronization primitives."],
                "expected_evidence": ["Clean async producer-consumer implementation."],
                "question_generation_mode": "HR_DEFINED",
                "difficulty": "MEDIUM",
                "estimated_duration_minutes": 30,
                "required": True,
                "sequence": 2,
                "questions": [
                    {
                        "question_text": "Explain race conditions in asyncio and how to prevent them.",
                        "concept": "Concurrency",
                        "difficulty": "MEDIUM",
                        "question_type": "PRACTICAL",
                        "is_hr_authored": True,
                        "status": "APPROVED",
                        "sequence": 1,
                    }
                ],
            },
        ]

        put_res = await ac.put(
            f"/api/v1/interview-plans/{plan_id}",
            headers=ctx["headers"],
            json={
                "rounds": updated_rounds,
                "hr_feedback": "Customized by engineering hiring committee",
                "lock_version": 1,
            },
        )
        assert put_res.status_code == 200
        saved = put_res.json()
        assert len(saved["rounds"]) == 2
        assert saved["rounds"][0]["title"] == "Custom Round A — System Architecture"
        assert saved["rounds"][1]["title"] == "Custom Round B — Coding & Concurrency"
        assert saved["lock_version"] == 2
        assert saved["rounds"][0]["questions"][0]["is_hr_authored"] is True


@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict():
    ctx = await setup_test_context()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            f"/api/v1/applications/{ctx['app_id']}/interview/plans",
            headers=ctx["headers"],
            json={},
        )
        plan_data = res.json()
        plan_id = plan_data["id"]

        # Attempt update with stale lock_version (e.g. 99 instead of 1)
        conflict_res = await ac.put(
            f"/api/v1/interview-plans/{plan_id}",
            headers=ctx["headers"],
            json={
                "rounds": plan_data["rounds"],
                "lock_version": 99,
            },
        )
        assert conflict_res.status_code == 409
        assert "Conflict" in conflict_res.json()["detail"]


@pytest.mark.asyncio
async def test_question_preview_generation_modes():
    ctx = await setup_test_context()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Mode: HR_DEFINED -> returns only the HR-authored questions
        hr_questions = [
            {
                "question_text": "What is the difference between a process and a thread?",
                "concept": "Operating Systems",
                "difficulty": "EASY",
                "question_type": "CONCEPTUAL",
                "is_hr_authored": True,
                "sequence": 1,
            }
        ]
        preview_hr = await ac.post(
            f"/api/v1/applications/{ctx['app_id']}/interview/plans/preview-questions",
            headers=ctx["headers"],
            json={
                "round_title": "HR Only Round",
                "objective": "Verify foundational OS concepts",
                "concepts": ["Operating Systems"],
                "difficulty": "EASY",
                "question_generation_mode": "HR_DEFINED",
                "hr_questions": hr_questions,
                "target_count": 3,
            },
        )
        assert preview_hr.status_code == 200
        hr_result = preview_hr.json()
        assert len(hr_result) == 1
        assert hr_result[0]["question_text"] == "What is the difference between a process and a thread?"
        assert hr_result[0]["is_hr_authored"] is True

        # 2. Mode: HYBRID -> preserves HR question and synthesizes additional questions
        preview_hybrid = await ac.post(
            f"/api/v1/applications/{ctx['app_id']}/interview/plans/preview-questions",
            headers=ctx["headers"],
            json={
                "round_title": "Hybrid Architecture Round",
                "objective": "Assess multi-threading and cache invalidation",
                "concepts": ["Caching", "Distributed Systems"],
                "difficulty": "HARD",
                "question_generation_mode": "HYBRID",
                "hr_questions": hr_questions,
                "target_count": 3,
            },
        )
        assert preview_hybrid.status_code == 200
        hybrid_result = preview_hybrid.json()
        assert len(hybrid_result) >= 2
        # First question is the HR-authored one
        assert hybrid_result[0]["is_hr_authored"] is True
        # Complementary questions are AI-grounded
        assert hybrid_result[1]["is_hr_authored"] is False
        assert hybrid_result[1]["difficulty"] == "HARD"

        # 3. Mode: AI_GENERATED -> generates questions matching difficulty and criteria
        preview_ai = await ac.post(
            f"/api/v1/applications/{ctx['app_id']}/interview/plans/preview-questions",
            headers=ctx["headers"],
            json={
                "round_title": "Pure AI Round",
                "objective": "Assess database indexing",
                "concepts": ["PostgreSQL"],
                "difficulty": "MEDIUM",
                "question_generation_mode": "AI_GENERATED",
                "target_count": 2,
            },
        )
        assert preview_ai.status_code == 200
        ai_result = preview_ai.json()
        assert len(ai_result) >= 1
        assert "PostgreSQL" in ai_result[0]["concept"] or "Engineering" in ai_result[0]["concept"]


@pytest.mark.asyncio
async def test_approval_and_version_preservation():
    ctx = await setup_test_context()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Create v1 draft
        create_res = await ac.post(
            f"/api/v1/applications/{ctx['app_id']}/interview/plans",
            headers=ctx["headers"],
            json={},
        )
        plan_v1_id = create_res.json()["id"]

        # 2. Approve v1 plan
        appr_res = await ac.post(
            f"/api/v1/interview-plans/{plan_v1_id}/approve",
            headers=ctx["headers"],
            json={"notes": "Approved v1 for scheduling"},
        )
        assert appr_res.status_code == 200
        v1_data = appr_res.json()
        assert v1_data["status"] == "APPROVED"
        assert v1_data["version"] == 1

        # 3. Edit approved plan -> should spawn v2 draft, leaving v1 approved & intact
        edit_res = await ac.put(
            f"/api/v1/interview-plans/{plan_v1_id}",
            headers=ctx["headers"],
            json={
                "rounds": [
                    {
                        "round_number": 1,
                        "title": "Updated Round in v2",
                        "objective": "New objective in v2",
                        "concepts": ["Distributed Systems"],
                        "estimated_duration_minutes": 60,
                        "required": True,
                        "sequence": 1,
                        "questions": [],
                    }
                ],
                "hr_feedback": "Drafting version 2 after recruiter debrief",
                "lock_version": v1_data["lock_version"],
            },
        )
        assert edit_res.status_code == 200
        v2_data = edit_res.json()
        assert v2_data["version"] == 2
        assert v2_data["status"] == "DRAFT"
        assert v2_data["id"] != plan_v1_id
        assert v2_data["rounds"][0]["title"] == "Updated Round in v2"

        # 4. Verify v1 is still APPROVED and completely intact
        v1_check = await ac.get(f"/api/v1/interview-plans/{plan_v1_id}", headers=ctx["headers"])
        assert v1_check.status_code == 200
        assert v1_check.json()["status"] == "APPROVED"
        assert v1_check.json()["version"] == 1

        # 5. Verify list endpoint returns both versions
        list_res = await ac.get(f"/api/v1/applications/{ctx['app_id']}/interview/plans", headers=ctx["headers"])
        assert list_res.status_code == 200
        all_plans = list_res.json()
        assert len(all_plans) >= 2


@pytest.mark.asyncio
async def test_scheduled_interview_locks_approved_plan():
    ctx = await setup_test_context()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create and approve plan
        create_res = await ac.post(
            f"/api/v1/applications/{ctx['app_id']}/interview/plans",
            headers=ctx["headers"],
            json={},
        )
        plan_id = create_res.json()["id"]
        round_id = create_res.json()["rounds"][0]["id"]

        await ac.post(
            f"/api/v1/interview-plans/{plan_id}/approve",
            headers=ctx["headers"],
            json={"notes": "Ready to schedule"},
        )

        # Schedule interview passing explicit plan_id and round_id
        start_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        sched_res = await ac.post(
            "/api/v1/interviews/schedules",
            headers=ctx["headers"],
            json={
                "application_id": str(ctx["app_id"]),
                "scheduled_start": start_time,
                "duration_minutes": 45,
                "interview_type": "ONLINE",
                "plan_id": plan_id,
                "round_id": round_id,
            },
        )
        assert sched_res.status_code == 201
        sched_data = sched_res.json()
        assert sched_data["plan_id"] == plan_id
        assert sched_data["round_id"] == round_id


@pytest.mark.asyncio
async def test_tenant_isolation_and_authorization():
    ctx = await setup_test_context()
    other_org_id = uuid4()
    other_user_id = uuid4()
    async with async_session_factory() as session:
        other_org = Organization(id=other_org_id, name="Other Org", slug=f"other-{other_org_id.hex[:6]}")
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
        await session.flush()
        session.add(other_user)
        await session.commit()

    other_token = create_access_token(str(other_user_id))
    other_headers = {"Authorization": f"Bearer {other_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create plan in Org 1
        create_res = await ac.post(
            f"/api/v1/applications/{ctx['app_id']}/interview/plans",
            headers=ctx["headers"],
            json={},
        )
        plan_id = create_res.json()["id"]

        # Attempt to access or modify from Org 2
        unauth_get = await ac.get(f"/api/v1/interview-plans/{plan_id}", headers=other_headers)
        assert unauth_get.status_code == 404

        unauth_update = await ac.put(
            f"/api/v1/interview-plans/{plan_id}",
            headers=other_headers,
            json={"rounds": []},
        )
        assert unauth_update.status_code == 404
