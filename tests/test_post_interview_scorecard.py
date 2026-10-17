from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.roles import UserRole
from app.db.session import get_db_session
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.candidate_scorecard import CandidateScorecard
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.interview_answer_analysis import InterviewAnswerAnalysis
from app.models.job import Job
from app.models.user import User
from app.schemas.post_interview_scorecard import (
    PostInterviewChangeTypeEnum,
    PostInterviewScorecard,
)
from app.schemas.pre_interview_scorecard import (
    ConfidenceLevelEnum,
    PreInterviewCapabilityStatusEnum,
    PreInterviewScorecard,
)
from app.services.application import ApplicationNotFoundError
from app.services.interview import InvalidSessionStateError
from app.services.post_interview_scorecard import generate_post_interview_scorecard
from app.services.pre_interview_scorecard import generate_pre_interview_scorecard


@pytest.fixture
def mock_post_scorecard_data():
    org_id = uuid4()
    app_id = uuid4()
    job_id = uuid4()
    cand_id = uuid4()
    session_id = uuid4()

    candidate = Candidate(
        id=cand_id,
        email="elena.rostova@example.com",
        full_name="Elena Rostova",
    )

    job = Job(
        id=job_id,
        organization_id=org_id,
        title="Principal Distributed Systems Architect",
        description="Design event-driven architectures with Python, Kafka, and Redis.",
    )

    application = Application(
        id=app_id,
        candidate_id=cand_id,
        job_id=job_id,
        status="INTERVIEW_COMPLETED",
        resume_path="resumes/elena_rostova.pdf",
    )
    application.candidate = candidate
    application.job = job

    # 4 capabilities to verify all transitions:
    # 1. Cap 1: UNKNOWN at baseline -> SUPPORTED in interview (Strengthened)
    cap1 = Capability(
        id=uuid4(),
        job_id=job_id,
        name="Apache Kafka Architecture",
        description="Event stream partitioning and consumer group rebalancing",
        importance="CRITICAL",
        created_at=datetime.now(timezone.utc),
    )

    # 2. Cap 2: SUPPORTED at baseline -> CONFIRMED in interview
    cap2 = Capability(
        id=uuid4(),
        job_id=job_id,
        name="Python AsyncIO",
        description="Concurrency primitives and event loop scheduling",
        importance="HIGH",
        created_at=datetime.now(timezone.utc),
    )

    # 3. Cap 3: PARTIAL at baseline -> PARTIAL (Unverified Claim) in interview
    cap3 = Capability(
        id=uuid4(),
        job_id=job_id,
        name="Distributed Tracing & OpenTelemetry",
        description="Trace context propagation and latency profiling",
        importance="MEDIUM",
        created_at=datetime.now(timezone.utc),
    )

    # 4. Cap 4: UNKNOWN at baseline -> UNKNOWN (Untested, absence != failure)
    cap4 = Capability(
        id=uuid4(),
        job_id=job_id,
        name="Kubernetes Operator SDK",
        description="Custom controllers and reconciliation loops",
        importance="MEDIUM",
        created_at=datetime.now(timezone.utc),
    )

    capabilities = [cap1, cap2, cap3, cap4]

    # Pre-interview baseline evidence
    ev_cap2 = Evidence(
        id=uuid4(),
        application_id=app_id,
        capability_id=cap2.id,
        source_type="GITHUB",
        content="Published asyncio rate limiter library on GitHub.",
        strength="STRONG",
        provenance="DEMONSTRATED",
        created_at=datetime.now(timezone.utc),
    )
    ev_cap3 = Evidence(
        id=uuid4(),
        application_id=app_id,
        capability_id=cap3.id,
        source_type="RESUME",
        content="Resume claim: Used OpenTelemetry at prior company.",
        strength="MODERATE",
        provenance="CLAIM",
        created_at=datetime.now(timezone.utc),
    )
    evidences = [ev_cap2, ev_cap3]

    # Completed Interview Session
    interview_session = InterviewSession(
        id=session_id,
        application_id=app_id,
        status="COMPLETED",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )

    # Question 1: Evaluates Cap 1 (Kafka) -> Answered sufficiently
    q1 = InterviewQuestion(
        id=uuid4(),
        session_id=session_id,
        capability_id=cap1.id,
        concept="Apache Kafka Architecture",
        question="How do you handle consumer group rebalancing without causing packet storms?",
        answer="We tuned heartbeat intervals and configured cooperative sticky assignors.",
        sequence_number=1,
        created_at=datetime.now(timezone.utc),
    )
    analysis1 = InterviewAnswerAnalysis(
        id=uuid4(),
        session_id=session_id,
        question_id=q1.id,
        analysis={
            "answer_quality": "SUFFICIENT",
            "evidence_state": "DEMONSTRATED",
            "key_findings": ["Understands cooperative sticky assignors", "Tuned consumer heartbeats"],
            "missing_points": [],
            "follow_up_needed": False,
        },
        created_at=datetime.now(timezone.utc),
    )

    # Question 2: Evaluates Cap 2 (Python AsyncIO) -> Reaffirmed verified knowledge
    q2 = InterviewQuestion(
        id=uuid4(),
        session_id=session_id,
        capability_id=cap2.id,
        concept="Python AsyncIO",
        question="Explain how asyncio task cancellation interacts with shielding.",
        answer="asyncio.shield prevents outer cancellation from propagating to the child task.",
        sequence_number=2,
        created_at=datetime.now(timezone.utc),
    )
    analysis2 = InterviewAnswerAnalysis(
        id=uuid4(),
        session_id=session_id,
        question_id=q2.id,
        analysis={
            "answer_quality": "SUFFICIENT",
            "evidence_state": "DEMONSTRATED",
            "key_findings": ["Detailed explanation of task shielding and cancellation semantics"],
            "missing_points": [],
            "follow_up_needed": False,
        },
        created_at=datetime.now(timezone.utc),
    )

    # Question 3: Evaluates Cap 3 (OpenTelemetry) -> Partial / superficial answer
    q3 = InterviewQuestion(
        id=uuid4(),
        session_id=session_id,
        capability_id=cap3.id,
        concept="Distributed Tracing & OpenTelemetry",
        question="Describe how you configured trace context propagation across gRPC boundaries.",
        answer="We used standard headers.",
        sequence_number=3,
        created_at=datetime.now(timezone.utc),
    )
    analysis3 = InterviewAnswerAnalysis(
        id=uuid4(),
        session_id=session_id,
        question_id=q3.id,
        analysis={
            "answer_quality": "PARTIAL",
            "evidence_state": "CLAIM",
            "key_findings": ["Mentioned headers"],
            "missing_points": ["Did not explain W3C tracecontext headers or interceptor architecture"],
            "follow_up_needed": True,
            "follow_up_reason": "Lacks architectural depth",
        },
        created_at=datetime.now(timezone.utc),
    )

    # Notice: Cap 4 (Kubernetes Operator SDK) was NOT asked at all!
    interview_session.questions = [q1, q2, q3]
    interview_session.messages = []
    interview_session.answer_analyses = [analysis1, analysis2, analysis3]

    # Pre-Interview Baseline Scorecard
    baseline_scorecard = PreInterviewScorecard(
        application_id=app_id,
        job_id=job_id,
        job_title=job.title,
        candidate_id=cand_id,
        candidate_name=candidate.full_name,
        candidate_email=candidate.email,
        assessment_timestamp=datetime.now(timezone.utc),
        scorecard_version=1,
        evidence_readiness_score=37.5,
        score_explanation="Baseline readiness: 1 supported, 1 partial, 2 unknown.",
        executive_summary="Candidate has demonstrated Python AsyncIO, claims OpenTelemetry, missing Kafka and K8s.",
        total_capabilities=4,
        supported_count=1,
        partial_count=1,
        unknown_count=2,
        contradictory_count=0,
        critical_verification_needs=["Apache Kafka Architecture"],
        human_review_notice="Pre-interview evaluation only.",
        capabilities=[
            {
                "capability_id": cap1.id,
                "capability_name": cap1.name,
                "requirement_description": cap1.description,
                "importance": cap1.importance,
                "status": "UNKNOWN",
                "status_rationale": "No mention in resume.",
                "confidence": "NONE",
                "confidence_justification": "Zero evidence discovered in submitted artifacts.",
                "supporting_evidence": [],
                "recommended_verification": {
                    "action_type": "INTERVIEW_PROBE",
                    "priority": "HIGH",
                    "guidance": "Test Kafka consumer groups in technical interview.",
                },
                "targeted_questions": [],
            },
            {
                "capability_id": cap2.id,
                "capability_name": cap2.name,
                "requirement_description": cap2.description,
                "importance": cap2.importance,
                "status": "SUPPORTED",
                "status_rationale": "Demonstrated via public GitHub repository.",
                "confidence": "HIGH",
                "confidence_justification": "Public code repository with AsyncIO implementation.",
                "supporting_evidence": [
                    {
                        "id": str(ev_cap2.id),
                        "source_type": "GITHUB",
                        "source_reference": "GitHub repo",
                        "excerpt": "asyncio rate limiter library",
                        "source_location": "github.com",
                        "provenance": "DEMONSTRATED",
                        "strength": "STRONG",
                    }
                ],
                "recommended_verification": {
                    "action_type": "TECHNICAL_CONFIRMATION",
                    "priority": "LOW",
                    "guidance": "Confirm async design.",
                },
                "targeted_questions": [],
            },
            {
                "capability_id": cap3.id,
                "capability_name": cap3.name,
                "requirement_description": cap3.description,
                "importance": cap3.importance,
                "status": "PARTIAL",
                "status_rationale": "Self-reported claim on resume.",
                "confidence": "LOW",
                "confidence_justification": "Self-reported resume claim without third-party evidence.",
                "supporting_evidence": [
                    {
                        "id": str(ev_cap3.id),
                        "source_type": "RESUME",
                        "source_reference": "Resume PDF",
                        "excerpt": "Used OpenTelemetry at prior company",
                        "source_location": "Page 1",
                        "provenance": "CLAIM",
                        "strength": "MODERATE",
                    }
                ],
                "recommended_verification": {
                    "action_type": "INTERVIEW_PROBE",
                    "priority": "MEDIUM",
                    "guidance": "Probe practical tracing.",
                },
                "targeted_questions": [],
            },
            {
                "capability_id": cap4.id,
                "capability_name": cap4.name,
                "requirement_description": cap4.description,
                "importance": cap4.importance,
                "status": "UNKNOWN",
                "status_rationale": "No evidence found.",
                "confidence": "NONE",
                "confidence_justification": "Absence of evidence is not evidence of absence.",
                "supporting_evidence": [],
                "recommended_verification": {
                    "action_type": "EXPLORATORY_PROBE",
                    "priority": "MEDIUM",
                    "guidance": "Ask exploratory questions.",
                },
                "targeted_questions": [],
            },
        ],
    )

    baseline_record = CandidateScorecard(
        id=uuid4(),
        application_id=app_id,
        job_id=job_id,
        scorecard_type="PRE_INTERVIEW",
        version=1,
        is_baseline=True,
        scorecard_data=baseline_scorecard.model_dump(mode="json"),
        created_at=datetime.now(timezone.utc),
    )

    return {
        "org_id": org_id,
        "app_id": app_id,
        "job_id": job_id,
        "cand_id": cand_id,
        "session_id": session_id,
        "application": application,
        "job": job,
        "candidate": candidate,
        "capabilities": capabilities,
        "evidences": evidences,
        "interview_session": interview_session,
        "baseline_scorecard": baseline_scorecard,
        "baseline_record": baseline_record,
        "cap1": cap1,
        "cap2": cap2,
        "cap3": cap3,
        "cap4": cap4,
    }


@pytest.mark.asyncio
async def test_post_interview_scorecard_generation_and_baseline_immutability(mock_post_scorecard_data):
    """
    Verifies that:
    1. Pre-interview baseline is preserved and immutable.
    2. UNKNOWN capability tested in interview with sufficient answer is upgraded to SUPPORTED (Strengthened).
    3. SUPPORTED capability reaffirmed in interview remains CONFIRMED.
    4. PARTIAL claim tested with superficial answer remains PARTIAL (Unverified Claim).
    5. UNTESTED capability strictly remains UNKNOWN with REMAINED_UNKNOWN change type (absence != failure).
    6. Readiness delta is calculated correctly.
    """
    data = mock_post_scorecard_data
    mock_session = AsyncMock()

    # Session queries: application, interview_session, existing_post_rec, baseline_rec, caps, verifications
    mock_session.scalar.side_effect = [
        data["application"],        # application query
        data["interview_session"],  # interview_session query
        None,                       # existing_post_rec
        data["baseline_record"],    # baseline_rec
    ]

    mock_session.scalars.side_effect = [
        MagicMock(all=lambda: data["capabilities"]),  # caps_stmt
        MagicMock(all=lambda: []),                    # ver_stmt
    ]

    post_scorecard = await generate_post_interview_scorecard(
        session=mock_session,
        application_id=data["app_id"],
        organization_id=data["org_id"],
        force_refresh=False,
    )

    assert isinstance(post_scorecard, PostInterviewScorecard)
    assert post_scorecard.application_id == data["app_id"]
    assert post_scorecard.interview_session_id == data["session_id"]
    assert post_scorecard.baseline_scorecard_id == data["baseline_record"].id

    caps_by_name = {c.capability_name: c for c in post_scorecard.capabilities}

    # 1. Cap 1 (Kafka): UNKNOWN -> SUPPORTED (STRENGTHENED)
    c1 = caps_by_name["Apache Kafka Architecture"]
    assert c1.original_status == PreInterviewCapabilityStatusEnum.UNKNOWN
    assert c1.updated_status == PreInterviewCapabilityStatusEnum.SUPPORTED
    assert c1.change_type == PostInterviewChangeTypeEnum.STRENGTHENED
    assert len(c1.interview_evidence) == 1
    assert c1.interview_evidence[0].evaluation_quality == "SUFFICIENT"
    assert "cooperative sticky assignors" in (c1.interview_evidence[0].candidate_answer_excerpt or "")

    # 2. Cap 2 (Python AsyncIO): SUPPORTED -> SUPPORTED (CONFIRMED)
    c2 = caps_by_name["Python AsyncIO"]
    assert c2.original_status == PreInterviewCapabilityStatusEnum.SUPPORTED
    assert c2.updated_status == PreInterviewCapabilityStatusEnum.SUPPORTED
    assert c2.change_type == PostInterviewChangeTypeEnum.CONFIRMED
    assert len(c2.interview_evidence) == 1

    # 3. Cap 3 (OpenTelemetry): PARTIAL -> PARTIAL (UNVERIFIED_CLAIM)
    c3 = caps_by_name["Distributed Tracing & OpenTelemetry"]
    assert c3.original_status == PreInterviewCapabilityStatusEnum.PARTIAL
    assert c3.updated_status == PreInterviewCapabilityStatusEnum.PARTIAL
    assert c3.change_type == PostInterviewChangeTypeEnum.UNVERIFIED_CLAIM
    assert len(c3.interview_evidence) == 1
    assert c3.interview_evidence[0].evaluation_quality == "PARTIAL"

    # 4. Cap 4 (K8s Operator SDK): UNKNOWN -> UNKNOWN (REMAINED_UNKNOWN, absence != failure)
    c4 = caps_by_name["Kubernetes Operator SDK"]
    assert c4.original_status == PreInterviewCapabilityStatusEnum.UNKNOWN
    assert c4.updated_status == PreInterviewCapabilityStatusEnum.UNKNOWN
    assert c4.change_type == PostInterviewChangeTypeEnum.REMAINED_UNKNOWN
    assert len(c4.interview_evidence) == 0
    assert "not tested during this interview session" in c4.change_summary
    assert "Absence of interview questioning is not candidate failure" in c4.change_summary

    # Summary metrics & Deltas
    # Baseline readiness: ((1 * 1.0) + (1 * 0.5)) / 4 * 100 = 37.5%
    # Post-interview: ((2 * 1.0) + (1 * 0.5)) / 4 * 100 = 62.5%
    # Delta: +25.0%
    assert post_scorecard.baseline_readiness_score == 37.5
    assert post_scorecard.post_interview_readiness_score == 62.5
    assert post_scorecard.readiness_change_delta == 25.0
    assert post_scorecard.capabilities_strengthened_count == 1
    assert post_scorecard.capabilities_unverified_count == 2
    assert post_scorecard.supported_count == 2
    assert post_scorecard.partial_count == 1
    assert post_scorecard.unknown_count == 1

    # Check persistence was called
    assert mock_session.add.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_post_interview_scorecard_requires_completed_session(mock_post_scorecard_data):
    """
    Verifies that calling post-interview scorecard on an IN_PROGRESS or CREATED session
    raises InvalidSessionStateError.
    """
    data = mock_post_scorecard_data
    data["interview_session"].status = "IN_PROGRESS"

    mock_session = AsyncMock()
    mock_session.scalar.side_effect = [
        data["application"],
        data["interview_session"],
    ]

    with pytest.raises(InvalidSessionStateError):
        await generate_post_interview_scorecard(
            session=mock_session,
            application_id=data["app_id"],
            organization_id=data["org_id"],
        )


@pytest.mark.asyncio
async def test_post_interview_scorecard_cross_tenant_isolation(mock_post_scorecard_data):
    """
    Verifies that requesting a post-interview scorecard across tenant boundaries
    raises ApplicationNotFoundError.
    """
    data = mock_post_scorecard_data
    mock_session = AsyncMock()
    mock_session.scalar.return_value = None  # Cross-tenant query returns None

    diff_org_id = uuid4()
    with pytest.raises(ApplicationNotFoundError):
        await generate_post_interview_scorecard(
            session=mock_session,
            application_id=data["app_id"],
            organization_id=diff_org_id,
        )


def test_api_post_interview_scorecard_endpoints(mock_post_scorecard_data):
    """
    Tests GET and POST /api/v1/applications/{application_id}/post-interview-scorecard endpoints
    with role authorization.
    """
    data = mock_post_scorecard_data
    app_id = data["app_id"]
    org_id = data["org_id"]

    recruiter_user = User(
        id=uuid4(),
        organization_id=org_id,
        email="recruiter@example.com",
        full_name="HR Recruiter",
        role=UserRole.RECRUITER.value,
        is_active=True,
    )

    from app.api.dependencies import get_current_user

    async def mock_get_current_user():
        return recruiter_user

    mock_db = AsyncMock()
    mock_db.scalar.side_effect = [
        data["application"],
        data["interview_session"],
        None,
        data["baseline_record"],
    ]
    mock_db.scalars.side_effect = [
        MagicMock(all=lambda: data["capabilities"]),
        MagicMock(all=lambda: []),
    ]

    async def mock_db_session():
        yield mock_db

    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db_session] = mock_db_session

    try:
        with TestClient(app) as client:
            resp = client.get(f"/api/v1/applications/{app_id}/post-interview-scorecard")
            assert resp.status_code == 200
            scorecard_json = resp.json()

            assert scorecard_json["application_id"] == str(app_id)
            assert scorecard_json["baseline_readiness_score"] == 37.5
            assert scorecard_json["post_interview_readiness_score"] == 62.5
            assert scorecard_json["readiness_change_delta"] == 25.0
            assert len(scorecard_json["capabilities"]) == 4

            # Verify change analysis presence
            kafka_cap = next(c for c in scorecard_json["capabilities"] if c["capability_name"] == "Apache Kafka Architecture")
            assert kafka_cap["change_type"] == "STRENGTHENED"
            assert kafka_cap["original_status"] == "UNKNOWN"
            assert kafka_cap["updated_status"] == "SUPPORTED"

            # Untested cap remains UNKNOWN
            k8s_cap = next(c for c in scorecard_json["capabilities"] if c["capability_name"] == "Kubernetes Operator SDK")
            assert k8s_cap["change_type"] == "REMAINED_UNKNOWN"
            assert k8s_cap["updated_status"] == "UNKNOWN"

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_adding_new_evidence_does_not_mutate_historical_baseline(mock_post_scorecard_data):
    """
    Regression test proving that adding new candidate evidence after the baseline is established
    cannot mutate the original historical pre-interview baseline scorecard.
    """
    data = mock_post_scorecard_data
    app_id = data["app_id"]
    org_id = data["org_id"]

    # 1. Existing baseline record is in DB
    baseline_rec = data["baseline_record"]
    original_readiness = baseline_rec.scorecard_data["evidence_readiness_score"]
    original_supported_count = baseline_rec.scorecard_data["supported_count"]
    assert original_readiness == 37.5
    assert original_supported_count == 1

    # 2. Candidate completes interview or introduces new evidence
    # Now simulate requesting pre-interview scorecard: it must return the frozen baseline
    mock_session = AsyncMock()
    mock_session.scalar.side_effect = [
        data["application"],  # application query
        baseline_rec,         # existing_scorecard_rec query
    ]

    retrieved = await generate_pre_interview_scorecard(
        session=mock_session,
        application_id=app_id,
        organization_id=org_id,
        force_refresh=False,
    )

    assert retrieved.evidence_readiness_score == 37.5
    assert retrieved.supported_count == 1
    assert retrieved.version == 1

    # 3. Simulate calling refresh on an application that has already conducted an interview
    # The immutability safeguard must prevent mutating the baseline
    mock_session.scalar.side_effect = [
        data["application"],  # application query
        baseline_rec,         # existing_scorecard_rec query
        uuid4(),              # session_check finds an existing interview session!
    ]

    refreshed_during_interview = await generate_pre_interview_scorecard(
        session=mock_session,
        application_id=app_id,
        organization_id=org_id,
        force_refresh=True,
    )

    # Immutability preserved!
    assert refreshed_during_interview.evidence_readiness_score == 37.5
    assert refreshed_during_interview.supported_count == 1
    assert refreshed_during_interview.version == 1

