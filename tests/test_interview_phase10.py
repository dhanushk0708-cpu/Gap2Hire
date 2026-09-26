import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.roles import UserRole
from app.core.security import create_access_token
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.capability import Capability
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.interview_answer_analysis import InterviewAnswerAnalysis
from app.models.interview_integrity import InterviewIntegrityEvent
from app.models.interview_report import InterviewReportModel
from app.models.job import Job
from app.models.user import User
from app.schemas.interview_analysis import (
    CandidateInterviewPreAnalysis,
    InterviewReport,
    PostInterviewCapabilityFinding,
)
from app.services.interview import (
    InterviewSessionNotFoundError,
    InvalidSessionStateError,
)
from app.services.interview_report import (
    InterviewReportNotFoundError,
    build_interview_report_response,
    generate_and_persist_interview_report,
    get_persisted_interview_report,
)


@pytest.fixture(scope="module")
def sync_client():
    with TestClient(app) as client:
        yield client


def build_mock_phase10_session(session_status: str = "COMPLETED"):
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    job_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    app_id = uuid.uuid4()
    session_id = uuid.uuid4()
    recruiter_user_id = uuid.uuid4()
    candidate_user_id = uuid.uuid4()

    # Recruiter
    recruiter_user = User(
        id=recruiter_user_id,
        organization_id=org_id,
        email="hr.manager@example.com",
        role=UserRole.HIRING_MANAGER.value,
        is_active=True,
    )

    # Candidate
    candidate = Candidate(
        id=cand_id,
        full_name="Alex Phase10 Candidate",
        email=f"alex.{cand_id.hex[:6]}@example.com",
    )
    candidate_user = User(
        id=candidate_user_id,
        organization_id=org_id,
        email=candidate.email,
        role=UserRole.CANDIDATE.value,
        is_active=True,
    )

    # Job & Capabilities
    job = Job(
        id=job_id,
        organization_id=org_id,
        title="Senior Backend Systems Engineer",
        description="FastAPI, PostgreSQL, Concurrency",
    )
    cap1 = Capability(
        id=uuid.uuid4(),
        job_id=job_id,
        name="FastAPI",
        description="High throughput API routing",
        importance="HIGH",
    )
    cap2 = Capability(
        id=uuid.uuid4(),
        job_id=job_id,
        name="PostgreSQL",
        description="Complex relational queries and locks",
        importance="HIGH",
    )
    cap3 = Capability(
        id=uuid.uuid4(),
        job_id=job_id,
        name="Kubernetes",
        description="Container orchestration",
        importance="MEDIUM",
    )

    application = Application(
        id=app_id,
        candidate_id=cand_id,
        job_id=job_id,
        candidate=candidate,
        job=job,
        status="SCREENING",
        shortlist_status="SHORTLISTED",
    )

    # Interview Questions and Messages
    q1_id = uuid.uuid4()
    q1 = InterviewQuestion(
        id=q1_id,
        session_id=session_id,
        capability_id=cap1.id,
        concept="FastAPI",
        question="How does dependency injection work in FastAPI?",
        sequence_number=1,
    )
    q2_id = uuid.uuid4()
    q2 = InterviewQuestion(
        id=q2_id,
        session_id=session_id,
        capability_id=cap2.id,
        concept="PostgreSQL",
        question="How do you handle lock contention on high-concurrency tables?",
        sequence_number=2,
    )

    m_sys = InterviewMessage(
        session_id=session_id,
        role="SYSTEM",
        content="Interview session started.",
        sequence_number=1,
    )
    m_a1 = InterviewMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        role="CANDIDATE",
        content="FastAPI uses `Depends()` to resolve callables hierarchically per request lifecycle.",
        sequence_number=2,
    )
    m_a2 = InterviewMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        role="CANDIDATE",
        content="I use optimistic concurrency or partitioned updates to avoid table-level locks.",
        sequence_number=3,
    )

    aa1 = InterviewAnswerAnalysis(
        id=uuid.uuid4(),
        session_id=session_id,
        question_id=q1_id,
        analysis={
            "answer_quality": "SUFFICIENT",
            "evidence_state": "DEMONSTRATED",
            "key_findings": ["Understands Depends() and hierarchical resolver"],
            "missing_points": [],
            "follow_up_needed": False,
        },
    )
    aa2 = InterviewAnswerAnalysis(
        id=uuid.uuid4(),
        session_id=session_id,
        question_id=q2_id,
        analysis={
            "answer_quality": "SUFFICIENT",
            "evidence_state": "DEMONSTRATED",
            "key_findings": ["Accurately detailed optimistic locking strategies"],
            "missing_points": [],
            "follow_up_needed": False,
        },
    )

    # Integrity Events (Telemetry)
    evt1 = InterviewIntegrityEvent(
        id=uuid.uuid4(),
        interview_session_id=session_id,
        event_type="TAB_HIDDEN",
        occurred_at=datetime.now(timezone.utc),
        metadata_json={},
    )
    evt2 = InterviewIntegrityEvent(
        id=uuid.uuid4(),
        interview_session_id=session_id,
        event_type="FULLSCREEN_EXIT",
        occurred_at=datetime.now(timezone.utc),
        metadata_json={},
    )

    session_obj = InterviewSession(
        id=session_id,
        application_id=app_id,
        status=session_status,
        application=application,
        questions=[q1, q2],
        messages=[m_sys, m_a1, m_a2],
        answer_analyses=[aa1, aa2],
        integrity_events=[evt1, evt2],
        ended_at=datetime.now(timezone.utc) if session_status == "COMPLETED" else None,
    )

    return {
        "org_id": org_id,
        "other_org_id": other_org_id,
        "recruiter_user": recruiter_user,
        "candidate_user": candidate_user,
        "candidate": candidate,
        "job": job,
        "capabilities": [cap1, cap2, cap3],
        "application": application,
        "session": session_obj,
        "q1": q1,
        "q2": q2,
    }


def setup_mock_db(ctx, existing_report=None):
    mock_db = AsyncMock()

    def mock_scalar(stmt):
        stmt_str = str(stmt).lower()
        if "interview_reports" in stmt_str:
            return existing_report
        return ctx["session"]

    def mock_scalars(stmt):
        stmt_str = str(stmt).lower()
        m = MagicMock()
        if "capabilities" in stmt_str:
            m.all.return_value = ctx["capabilities"]
        else:
            m.all.return_value = []
        return m

    mock_db.scalar.side_effect = mock_scalar
    mock_db.scalars.side_effect = mock_scalars
    return mock_db


# ==============================================================================
# TEST 1: Report Cannot Be Generated For Incomplete Interview
# ==============================================================================

@pytest.mark.asyncio
async def test_report_cannot_be_generated_for_incomplete_interview():
    """Test 1: Report generation is rejected if the session is not in COMPLETED status."""
    ctx = build_mock_phase10_session(session_status="IN_PROGRESS")
    mock_db = setup_mock_db(ctx)

    with pytest.raises(InvalidSessionStateError) as exc_info:
        await generate_and_persist_interview_report(
            session=mock_db,
            session_id=ctx["session"].id,
            organization_id=ctx["org_id"],
        )

    assert "Expected 'COMPLETED'" in str(exc_info.value)


# ==============================================================================
# TEST 2: Authorized HR Can Generate Report
# ==============================================================================

@pytest.mark.asyncio
async def test_authorized_hr_can_generate_report():
    """Test 2: Authorized HR / Hiring Manager generates a structured report."""
    ctx = build_mock_phase10_session(session_status="COMPLETED")
    mock_db = setup_mock_db(ctx)

    with patch("app.services.interview_report.build_candidate_interview_pre_analysis") as mock_pre:
        mock_pre.return_value = CandidateInterviewPreAnalysis(
            application_id=ctx["application"].id,
            candidate_id=ctx["candidate"].id,
            candidate_name=ctx["candidate"].full_name,
            candidate_email=ctx["candidate"].email,
            job_id=ctx["job"].id,
            job_title=ctx["job"].title,
            candidate_claims=[{"capability_name": "FastAPI", "provenance": "CLAIM"}],
            candidate_strengths=[],
            candidate_unknowns=[{"capability_name": "Kubernetes", "provenance": "UNKNOWN"}],
            verification_targets=[],
            relevant_concepts=["FastAPI", "PostgreSQL"],
            grounded_summary="Pre-interview summary",
        )

        report = await generate_and_persist_interview_report(
            session=mock_db,
            session_id=ctx["session"].id,
            organization_id=ctx["org_id"],
        )

        assert report.status == "COMPLETED"
        assert report.interview_session_id == ctx["session"].id
        assert len(report.question_findings) == 2
        assert len(report.demonstrated_capabilities) >= 1
        assert report.summary is not None


# ==============================================================================
# TEST 3: Unauthorized User Cannot Access Report Generation
# ==============================================================================

def test_unauthorized_user_cannot_generate_report(sync_client):
    """Test 3: Candidates or users without HR roles cannot trigger report generation endpoint."""
    ctx = build_mock_phase10_session(session_status="COMPLETED")
    token = create_access_token(str(ctx["candidate_user"].id))

    async def override_get_user():
        return ctx["candidate_user"]

    from app.api.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = override_get_user

    try:
        response = sync_client.post(
            f"/api/v1/interviews/{ctx['session'].id}/report",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ==============================================================================
# TEST 4: Cross-Tenant Access Rejected
# ==============================================================================

def test_cross_tenant_report_access_rejected(sync_client):
    """Test 4: Access to report generation for another tenant is rejected with 404."""
    ctx = build_mock_phase10_session(session_status="COMPLETED")
    other_recruiter = User(
        id=uuid.uuid4(),
        organization_id=ctx["other_org_id"],
        email="other.hr@example.com",
        role=UserRole.HIRING_MANAGER.value,
        is_active=True,
    )
    token = create_access_token(str(other_recruiter.id))

    mock_db = AsyncMock()
    mock_db.scalar.return_value = None  # Not found for other tenant

    async def override_get_db():
        yield mock_db

    async def override_get_user():
        return other_recruiter

    from app.api.dependencies import get_current_user
    from app.db.session import get_db_session

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_user

    try:
        response = sync_client.post(
            f"/api/v1/interviews/{ctx['session'].id}/report",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_user, None)


# ==============================================================================
# TEST 5: Report Persists Successfully
# ==============================================================================

@pytest.mark.asyncio
async def test_report_persists_successfully():
    """Test 5: Report is persisted in PostgreSQL with all required fields."""
    ctx = build_mock_phase10_session(session_status="COMPLETED")
    mock_db = setup_mock_db(ctx)

    with patch("app.services.interview_report.build_candidate_interview_pre_analysis") as mock_pre:
        mock_pre.return_value = CandidateInterviewPreAnalysis(
            application_id=ctx["application"].id,
            candidate_id=ctx["candidate"].id,
            candidate_name=ctx["candidate"].full_name,
            candidate_email=ctx["candidate"].email,
            job_id=ctx["job"].id,
            job_title=ctx["job"].title,
            candidate_claims=[],
            candidate_strengths=[],
            candidate_unknowns=[],
            verification_targets=[],
            relevant_concepts=[],
        )

        report = await generate_and_persist_interview_report(
            session=mock_db,
            session_id=ctx["session"].id,
            organization_id=ctx["org_id"],
        )

        assert mock_db.add.called or mock_db.commit.called
        assert report.interview_session_id == ctx["session"].id
        assert report.generation_source == "SYSTEM_AI"


# ==============================================================================
# TEST 6: Capability Evidence Preserves Provenance
# ==============================================================================

@pytest.mark.asyncio
async def test_capability_evidence_preserves_provenance():
    """Test 6: Pre-interview and post-interview provenance are tracked with source references."""
    ctx = build_mock_phase10_session(session_status="COMPLETED")
    mock_db = setup_mock_db(ctx)

    with patch("app.services.interview_report.build_candidate_interview_pre_analysis") as mock_pre:
        mock_pre.return_value = CandidateInterviewPreAnalysis(
            application_id=ctx["application"].id,
            candidate_id=ctx["candidate"].id,
            candidate_name=ctx["candidate"].full_name,
            candidate_email=ctx["candidate"].email,
            job_id=ctx["job"].id,
            job_title=ctx["job"].title,
            candidate_claims=[{"capability_name": "FastAPI", "provenance": "CLAIM"}],
            candidate_strengths=[],
            candidate_unknowns=[{"capability_name": "Kubernetes", "provenance": "UNKNOWN"}],
            verification_targets=[],
            relevant_concepts=["FastAPI"],
        )

        report = await generate_and_persist_interview_report(
            session=mock_db,
            session_id=ctx["session"].id,
            organization_id=ctx["org_id"],
        )

        fastapi_finding = next(
            (f for f in report.evidence_findings if f["capability_name"] == "FastAPI"), None
        )
        assert fastapi_finding is not None
        assert fastapi_finding["pre_interview_provenance"] == "CLAIM"
        assert fastapi_finding["post_interview_provenance"] == "DEMONSTRATED"
        assert len(fastapi_finding["source_references"]) > 0


# ==============================================================================
# TEST 7: CLAIM Is Not Upgraded Without Interview Evidence
# ==============================================================================

@pytest.mark.asyncio
async def test_claim_not_upgraded_without_interview_evidence():
    """Test 7: A resume CLAIM is not upgraded to DEMONSTRATED if not evaluated in interview."""
    ctx = build_mock_phase10_session(session_status="COMPLETED")
    # Cap 3 (Kubernetes) was NOT asked in interview
    mock_db = setup_mock_db(ctx)

    with patch("app.services.interview_report.build_candidate_interview_pre_analysis") as mock_pre:
        mock_pre.return_value = CandidateInterviewPreAnalysis(
            application_id=ctx["application"].id,
            candidate_id=ctx["candidate"].id,
            candidate_name=ctx["candidate"].full_name,
            candidate_email=ctx["candidate"].email,
            job_id=ctx["job"].id,
            job_title=ctx["job"].title,
            candidate_claims=[{"capability_name": "Kubernetes", "provenance": "CLAIM"}],
            candidate_strengths=[],
            candidate_unknowns=[],
            verification_targets=[],
            relevant_concepts=[],
        )

        report = await generate_and_persist_interview_report(
            session=mock_db,
            session_id=ctx["session"].id,
            organization_id=ctx["org_id"],
        )

        k8s_finding = next(
            (f for f in report.evidence_findings if f["capability_name"] == "Kubernetes"), None
        )
        assert k8s_finding is not None
        assert k8s_finding["pre_interview_provenance"] == "CLAIM"
        assert k8s_finding["post_interview_provenance"] == "CLAIM"  # Retained claim, NOT DEMONSTRATED


# ==============================================================================
# TEST 8: UNKNOWN Is Preserved as Unknown and Not Treated as Failure
# ==============================================================================

@pytest.mark.asyncio
async def test_unknown_preserved_as_unknown():
    """Test 8: UNKNOWN capability without interview data remains UNKNOWN without negative scoring."""
    ctx = build_mock_phase10_session(session_status="COMPLETED")
    mock_db = setup_mock_db(ctx)

    with patch("app.services.interview_report.build_candidate_interview_pre_analysis") as mock_pre:
        mock_pre.return_value = CandidateInterviewPreAnalysis(
            application_id=ctx["application"].id,
            candidate_id=ctx["candidate"].id,
            candidate_name=ctx["candidate"].full_name,
            candidate_email=ctx["candidate"].email,
            job_id=ctx["job"].id,
            job_title=ctx["job"].title,
            candidate_claims=[],
            candidate_strengths=[],
            candidate_unknowns=[{"capability_name": "Kubernetes", "provenance": "UNKNOWN"}],
            verification_targets=[],
            relevant_concepts=[],
        )

        report = await generate_and_persist_interview_report(
            session=mock_db,
            session_id=ctx["session"].id,
            organization_id=ctx["org_id"],
        )

        k8s_finding = next(
            (f for f in report.evidence_findings if f["capability_name"] == "Kubernetes"), None
        )
        assert k8s_finding is not None
        assert k8s_finding["pre_interview_provenance"] == "UNKNOWN"
        assert k8s_finding["post_interview_provenance"] == "UNKNOWN"
        assert "not a failure" in k8s_finding["observation"].lower()


# ==============================================================================
# TEST 9: Integrity Observations Remain Separate From Skill Evidence
# ==============================================================================

@pytest.mark.asyncio
async def test_integrity_observations_separate_from_skill_evidence():
    """Test 9: Integrity telemetry is reported strictly as factual observations without cheating scores."""
    ctx = build_mock_phase10_session(session_status="COMPLETED")
    mock_db = setup_mock_db(ctx)

    with patch("app.services.interview_report.build_candidate_interview_pre_analysis") as mock_pre:
        mock_pre.return_value = CandidateInterviewPreAnalysis(
            application_id=ctx["application"].id,
            candidate_id=ctx["candidate"].id,
            candidate_name=ctx["candidate"].full_name,
            candidate_email=ctx["candidate"].email,
            job_id=ctx["job"].id,
            job_title=ctx["job"].title,
            candidate_claims=[],
            candidate_strengths=[],
            candidate_unknowns=[],
            verification_targets=[],
            relevant_concepts=[],
        )

        report = await generate_and_persist_interview_report(
            session=mock_db,
            session_id=ctx["session"].id,
            organization_id=ctx["org_id"],
        )

        integ = report.integrity_summary
        assert integ["total_events"] == 2
        assert "TAB_HIDDEN" in integ["raw_event_count_by_type"]
        assert "FULLSCREEN_EXIT" in integ["raw_event_count_by_type"]
        # Invariant: No cheating classification
        assert "cheating" not in report.summary.lower()
        assert "dishonest" not in report.summary.lower()


# ==============================================================================
# TEST 10: Report GET Endpoint Returns Persisted Report
# ==============================================================================

def test_report_get_endpoint_returns_persisted_report(sync_client):
    """Test 10: GET /api/v1/interviews/{session_id}/report retrieves persisted report."""
    ctx = build_mock_phase10_session(session_status="COMPLETED")
    token = create_access_token(str(ctx["recruiter_user"].id))

    persisted_report_model = InterviewReportModel(
        id=uuid.uuid4(),
        interview_session_id=ctx["session"].id,
        status="COMPLETED",
        generation_source="SYSTEM_AI",
        summary="Candidate demonstrated solid knowledge in FastAPI.",
        strengths=[],
        demonstrated_capabilities=[{"capability_name": "FastAPI", "observation": "Strong answers"}],
        claimed_capabilities=[],
        unknown_capabilities=[],
        verification_needed=[],
        evidence_findings=[],
        round_summaries=[],
        question_findings=[],
        follow_up_findings=[],
        integrity_summary={"total_events": 0, "observations": []},
        unresolved_areas=[],
        recommendations_for_human_review=[],
        metadata_json={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_db = setup_mock_db(ctx, existing_report=persisted_report_model)

    async def override_get_db():
        yield mock_db

    async def override_get_user():
        return ctx["recruiter_user"]

    from app.api.dependencies import get_current_user
    from app.db.session import get_db_session

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_user

    try:
        response = sync_client.get(
            f"/api/v1/interviews/{ctx['session'].id}/report",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert data["session_id"] == str(ctx["session"].id)
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_user, None)
