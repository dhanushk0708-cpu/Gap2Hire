import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.roles import UserRole
from app.core.security import create_access_token
from app.db.session import get_db_session
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.candidate_hiring_decision import CandidateHiringDecision
from app.models.interview import InterviewSession
from app.models.interview_report import InterviewReportModel
from app.models.job import Job
from app.models.user import User
from app.schemas.hiring_decision import (
    HiringDecisionCreate,
    HiringDecisionHistoryResponse,
    HiringDecisionResponse,
    HiringDecisionType,
)
from app.services.hiring_decision import (
    ApplicationNotFoundError,
    get_application_hiring_decisions,
    record_human_hiring_decision,
)


@pytest.fixture(scope="module")
def sync_client():
    with TestClient(app) as client:
        yield client


def build_mock_phase11_context():
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    job_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    app_id = uuid.uuid4()
    session_id = uuid.uuid4()
    report_id = uuid.uuid4()
    recruiter_user_id = uuid.uuid4()
    candidate_user_id = uuid.uuid4()

    # Recruiter
    recruiter_user = User(
        id=recruiter_user_id,
        organization_id=org_id,
        email="hr.manager@example.com",
        full_name="Sarah HR Manager",
        role=UserRole.HIRING_MANAGER.value,
        is_active=True,
    )

    # Candidate
    candidate = Candidate(
        id=cand_id,
        full_name="David Candidate",
        email=f"david.{cand_id.hex[:6]}@example.com",
    )
    candidate_user = User(
        id=candidate_user_id,
        organization_id=org_id,
        email=candidate.email,
        full_name="David Candidate",
        role=UserRole.CANDIDATE.value,
        is_active=True,
    )

    # Job
    job = Job(
        id=job_id,
        organization_id=org_id,
        title="Principal Infrastructure Engineer",
        description="Kubernetes, Linux Kernels, Distributed Consensus",
    )

    # Application
    application = Application(
        id=app_id,
        candidate_id=cand_id,
        job_id=job_id,
        status="INTERVIEW",
        shortlist_status="SHORTLISTED",
        candidate=candidate,
        job=job,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Session & Report
    interview_session = InterviewSession(
        id=session_id,
        application_id=app_id,
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
    )

    report = InterviewReportModel(
        id=report_id,
        interview_session_id=session_id,
        status="COMPLETED",
        summary="Candidate demonstrated solid infrastructure engineering capabilities.",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    return {
        "org_id": org_id,
        "other_org_id": other_org_id,
        "job": job,
        "candidate": candidate,
        "application": application,
        "session": interview_session,
        "report": report,
        "recruiter_user": recruiter_user,
        "candidate_user": candidate_user,
    }


# ==============================================================================
# 1. Test SELECTED decision accepted
# ==============================================================================
def test_selected_decision_accepted(sync_client: TestClient):
    ctx = build_mock_phase11_context()
    token = create_access_token(str(ctx["recruiter_user"].id))

    async def override_get_user():
        return ctx["recruiter_user"]

    app.dependency_overrides[get_current_user] = override_get_user

    payload = {
        "decision": "SELECTED",
        "decision_reason": "Candidate demonstrated verified technical capabilities in distributed consensus and Linux internals.",
    }

    try:
        with patch("app.api.applications.record_human_hiring_decision") as mock_service:
            mock_service.return_value = HiringDecisionResponse(
                id=uuid.uuid4(),
                application_id=ctx["application"].id,
                candidate_id=ctx["candidate"].id,
                candidate_name="David Candidate",
                job_id=ctx["job"].id,
                job_title=ctx["job"].title,
                decision="SELECTED",
                decision_reason=payload["decision_reason"],
                decided_by=ctx["recruiter_user"].id,
                decided_by_name=ctx["recruiter_user"].full_name,
                decided_at=datetime.now(timezone.utc),
                report_id=ctx["report"].id,
                application_status="SELECTED",
                created_at=datetime.now(timezone.utc),
            )

            resp = sync_client.post(
                f"/api/v1/applications/{ctx['application'].id}/hiring-decision",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["decision"] == "SELECTED"
            assert data["decided_by_name"] == "Sarah HR Manager"
            assert data["application_status"] == "SELECTED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ==============================================================================
# 2. Test REJECTED decision accepted
# ==============================================================================
def test_rejected_decision_accepted(sync_client: TestClient):
    ctx = build_mock_phase11_context()
    token = create_access_token(str(ctx["recruiter_user"].id))

    async def override_get_user():
        return ctx["recruiter_user"]

    app.dependency_overrides[get_current_user] = override_get_user

    payload = {
        "decision": "REJECTED",
        "decision_reason": "Live answers revealed insufficient depth in distributed transactions required for this role.",
    }

    try:
        with patch("app.api.applications.record_human_hiring_decision") as mock_service:
            mock_service.return_value = HiringDecisionResponse(
                id=uuid.uuid4(),
                application_id=ctx["application"].id,
                candidate_id=ctx["candidate"].id,
                candidate_name="David Candidate",
                job_id=ctx["job"].id,
                job_title=ctx["job"].title,
                decision="REJECTED",
                decision_reason=payload["decision_reason"],
                decided_by=ctx["recruiter_user"].id,
                decided_by_name=ctx["recruiter_user"].full_name,
                decided_at=datetime.now(timezone.utc),
                report_id=ctx["report"].id,
                application_status="REJECTED",
                created_at=datetime.now(timezone.utc),
            )

            resp = sync_client.post(
                f"/api/v1/applications/{ctx['application'].id}/hiring-decision",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["decision"] == "REJECTED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ==============================================================================
# 3. Test ON_HOLD decision accepted
# ==============================================================================
def test_on_hold_decision_accepted(sync_client: TestClient):
    ctx = build_mock_phase11_context()
    token = create_access_token(str(ctx["recruiter_user"].id))

    async def override_get_user():
        return ctx["recruiter_user"]

    app.dependency_overrides[get_current_user] = override_get_user

    payload = {
        "decision": "ON_HOLD",
        "decision_reason": "Strong candidate; waiting for remaining candidates in current interview batch before final selection.",
    }

    try:
        with patch("app.api.applications.record_human_hiring_decision") as mock_service:
            mock_service.return_value = HiringDecisionResponse(
                id=uuid.uuid4(),
                application_id=ctx["application"].id,
                candidate_id=ctx["candidate"].id,
                candidate_name="David Candidate",
                job_id=ctx["job"].id,
                job_title=ctx["job"].title,
                decision="ON_HOLD",
                decision_reason=payload["decision_reason"],
                decided_by=ctx["recruiter_user"].id,
                decided_by_name=ctx["recruiter_user"].full_name,
                decided_at=datetime.now(timezone.utc),
                report_id=ctx["report"].id,
                application_status="ON_HOLD",
                created_at=datetime.now(timezone.utc),
            )

            resp = sync_client.post(
                f"/api/v1/applications/{ctx['application'].id}/hiring-decision",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["decision"] == "ON_HOLD"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ==============================================================================
# 4. Test invalid decision rejected
# ==============================================================================
def test_invalid_decision_rejected(sync_client: TestClient):
    ctx = build_mock_phase11_context()
    token = create_access_token(str(ctx["recruiter_user"].id))

    async def override_get_user():
        return ctx["recruiter_user"]

    app.dependency_overrides[get_current_user] = override_get_user

    payload = {
        "decision": "FAST_TRACK_HIRE",
        "decision_reason": "Bypassing normal flow.",
    }

    try:
        resp = sync_client.post(
            f"/api/v1/applications/{ctx['application'].id}/hiring-decision",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ==============================================================================
# 5. Test empty or whitespace-only reason rejected
# ==============================================================================
def test_empty_or_whitespace_reason_rejected(sync_client: TestClient):
    ctx = build_mock_phase11_context()
    token = create_access_token(str(ctx["recruiter_user"].id))

    async def override_get_user():
        return ctx["recruiter_user"]

    app.dependency_overrides[get_current_user] = override_get_user

    payload = {
        "decision": "SELECTED",
        "decision_reason": "   ",
    }

    try:
        resp = sync_client.post(
            f"/api/v1/applications/{ctx['application'].id}/hiring-decision",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ==============================================================================
# 6. Test unauthorized user cannot submit decision
# ==============================================================================
def test_unauthorized_user_cannot_submit_decision(sync_client: TestClient):
    ctx = build_mock_phase11_context()
    token = create_access_token(str(ctx["candidate_user"].id))

    async def override_get_user():
        return ctx["candidate_user"]

    app.dependency_overrides[get_current_user] = override_get_user

    payload = {
        "decision": "SELECTED",
        "decision_reason": "Self-selecting for hire.",
    }

    try:
        resp = sync_client.post(
            f"/api/v1/applications/{ctx['application'].id}/hiring-decision",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ==============================================================================
# 7. Test cross-tenant decision rejected
# ==============================================================================
@pytest.mark.asyncio
async def test_cross_tenant_decision_rejected():
    ctx = build_mock_phase11_context()
    other_user = User(
        id=uuid.uuid4(),
        organization_id=ctx["other_org_id"],
        email="other.hr@competitor.com",
        role=UserRole.HIRING_MANAGER.value,
        is_active=True,
    )

    session = AsyncMock()
    session.scalar.return_value = None  # Not found under other org's tenant query

    with pytest.raises(ApplicationNotFoundError):
        await record_human_hiring_decision(
            session=session,
            application_id=ctx["application"].id,
            user=other_user,
            data=HiringDecisionCreate(
                decision=HiringDecisionType.SELECTED,
                decision_reason="Cross-tenant attempt.",
            ),
        )


# ==============================================================================
# 8. Test decision updates application lifecycle correctly
# ==============================================================================
@pytest.mark.asyncio
async def test_decision_updates_application_lifecycle():
    ctx = build_mock_phase11_context()
    session = AsyncMock()

    def mock_scalar_side_effect(stmt):
        stmt_str = str(stmt).lower()
        if "from applications" in stmt_str or "applications.id" in stmt_str:
            return ctx["application"]
        if "from interview_reports" in stmt_str or "interview_reports.id" in stmt_str:
            return ctx["report"]
        if "from candidate_hiring_decisions" in stmt_str:
            return None
        return None

    session.scalar.side_effect = mock_scalar_side_effect

    res = await record_human_hiring_decision(
        session=session,
        application_id=ctx["application"].id,
        user=ctx["recruiter_user"],
        data=HiringDecisionCreate(
            decision=HiringDecisionType.SELECTED,
            decision_reason="Demonstrated all required capabilities in interview.",
        ),
    )

    assert res.decision == "SELECTED"
    assert ctx["application"].status == "SELECTED"
    assert ctx["application"].shortlist_status == "SELECTED"
    assert ctx["application"].shortlisted_at is not None


# ==============================================================================
# 9. Test previous decisions remain in history
# ==============================================================================
@pytest.mark.asyncio
async def test_previous_decisions_remain_in_history():
    ctx = build_mock_phase11_context()
    session = AsyncMock()

    first_decision_id = uuid.uuid4()
    existing_first_decision = CandidateHiringDecision(
        id=first_decision_id,
        application_id=ctx["application"].id,
        job_id=ctx["job"].id,
        decision="ON_HOLD",
        decision_reason="Holding for further review.",
        decided_by=ctx["recruiter_user"].id,
        decided_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
    )

    def mock_scalar_side_effect(stmt):
        stmt_str = str(stmt).lower()
        if "from applications" in stmt_str or "applications.id" in stmt_str:
            return ctx["application"]
        if "from interview_reports" in stmt_str or "interview_reports.id" in stmt_str:
            return ctx["report"]
        if "from candidate_hiring_decisions" in stmt_str:
            return existing_first_decision
        return None

    session.scalar.side_effect = mock_scalar_side_effect

    res = await record_human_hiring_decision(
        session=session,
        application_id=ctx["application"].id,
        user=ctx["recruiter_user"],
        data=HiringDecisionCreate(
            decision=HiringDecisionType.SELECTED,
            decision_reason="Reviewed pipeline; selected for hire.",
        ),
    )

    assert res.decision == "SELECTED"
    assert res.previous_decision_id == first_decision_id


# ==============================================================================
# 10. Test decision history endpoint returns chronological records
# ==============================================================================
def test_decision_history_endpoint_returns_chronological_records(sync_client: TestClient):
    ctx = build_mock_phase11_context()
    token = create_access_token(str(ctx["recruiter_user"].id))

    async def override_get_user():
        return ctx["recruiter_user"]

    app.dependency_overrides[get_current_user] = override_get_user

    d1 = HiringDecisionResponse(
        id=uuid.uuid4(),
        application_id=ctx["application"].id,
        candidate_id=ctx["candidate"].id,
        candidate_name="David Candidate",
        job_id=ctx["job"].id,
        job_title=ctx["job"].title,
        decision="ON_HOLD",
        decision_reason="Reviewing pipeline pool.",
        decided_by=ctx["recruiter_user"].id,
        decided_by_name="Sarah HR Manager",
        decided_at=datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc),
        report_id=ctx["report"].id,
        application_status="ON_HOLD",
        created_at=datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc),
    )

    d2 = HiringDecisionResponse(
        id=uuid.uuid4(),
        application_id=ctx["application"].id,
        candidate_id=ctx["candidate"].id,
        candidate_name="David Candidate",
        job_id=ctx["job"].id,
        job_title=ctx["job"].title,
        decision="SELECTED",
        decision_reason="Offer extended after final panel debrief.",
        decided_by=ctx["recruiter_user"].id,
        decided_by_name="Sarah HR Manager",
        decided_at=datetime(2026, 9, 22, 16, 30, tzinfo=timezone.utc),
        report_id=ctx["report"].id,
        previous_decision_id=d1.id,
        application_status="SELECTED",
        created_at=datetime(2026, 9, 22, 16, 30, tzinfo=timezone.utc),
    )

    try:
        with patch("app.api.applications.get_application_hiring_decisions") as mock_service:
            mock_service.return_value = HiringDecisionHistoryResponse(
                application_id=ctx["application"].id,
                candidate_id=ctx["candidate"].id,
                candidate_name="David Candidate",
                current_decision=d2,
                history=[d1, d2],
                total_decisions=2,
            )

            resp = sync_client.get(
                f"/api/v1/applications/{ctx['application'].id}/hiring-decisions",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["total_decisions"] == 2
            assert len(data["history"]) == 2
            assert data["history"][0]["decision"] == "ON_HOLD"
            assert data["history"][1]["decision"] == "SELECTED"
            assert data["current_decision"]["decision"] == "SELECTED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
