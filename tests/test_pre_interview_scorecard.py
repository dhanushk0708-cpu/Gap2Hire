from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.roles import UserRole
from app.db.session import get_db_session
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.candidate_source import CandidateSource
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.job import Job
from app.models.user import User
from app.models.verification import Verification
from app.schemas.pre_interview_scorecard import (
    ConfidenceLevelEnum,
    PreInterviewCapabilityStatusEnum,
    PreInterviewScorecard,
)
from app.services.application import ApplicationNotFoundError
from app.services.pre_interview_scorecard import (
    generate_pre_interview_scorecard,
    generate_targeted_question,
)


@pytest.fixture
def mock_scorecard_data():
    org_id = uuid4()
    app_id = uuid4()
    job_id = uuid4()
    cand_id = uuid4()

    candidate = Candidate(
        id=cand_id,
        email="alex.chen@example.com",
        full_name="Alex Chen",
    )

    job = Job(
        id=job_id,
        organization_id=org_id,
        title="Senior Backend Systems Engineer",
        description="Build high-performance distributed systems with Python, PostgreSQL, and FastAPI.",
    )

    application = Application(
        id=app_id,
        candidate_id=cand_id,
        job_id=job_id,
        status="APPLIED",
        resume_path="resumes/alex_chen.pdf",
    )
    application.candidate = candidate
    application.job = job

    # 4 distinct capabilities to test every status:
    # Cap 1: Verified via practical task -> SUPPORTED
    cap_verified = Capability(
        id=uuid4(),
        job_id=job_id,
        name="FastAPI & AsyncIO",
        description="Build async RESTful microservices with FastAPI",
        importance="CRITICAL",
        created_at=datetime.utcnow(),
    )

    # Cap 2: Demonstrated in code repository -> SUPPORTED
    cap_demonstrated = Capability(
        id=uuid4(),
        job_id=job_id,
        name="Distributed Systems & Kafka",
        description="Event streaming and idempotent distributed processing",
        importance="HIGH",
        created_at=datetime.utcnow(),
    )

    # Cap 3: Claimed only on resume -> PARTIAL
    cap_claimed = Capability(
        id=uuid4(),
        job_id=job_id,
        name="PostgreSQL Query Optimization",
        description="Index strategies, query plans, and partition management",
        importance="HIGH",
        created_at=datetime.utcnow(),
    )

    # Cap 4: No evidence in submission -> UNKNOWN (absence of evidence != failure)
    cap_unknown = Capability(
        id=uuid4(),
        job_id=job_id,
        name="Kubernetes & Terraform",
        description="Cloud deployment automation and pod orchestration",
        importance="MEDIUM",
        created_at=datetime.utcnow(),
    )

    # Candidate source
    source_github = CandidateSource(
        id=uuid4(),
        application_id=app_id,
        url="https://github.com/alexchen/event-bus",
        source_type="GITHUB",
        title="Event Bus Distributed Processor",
    )
    application.sources = [source_github]

    # Verification for Cap 1
    ver_pass = Verification(
        id=uuid4(),
        application_id=app_id,
        capability_id=cap_verified.id,
        type="PRACTICAL_TASK",
        result="PASS",
        submission_content="Implemented async connection pool and background task pipeline.",
        created_at=datetime.utcnow(),
    )

    # Demonstrated Evidence for Cap 2
    ev_demo = Evidence(
        id=uuid4(),
        application_id=app_id,
        capability_id=cap_demonstrated.id,
        candidate_source_id=source_github.id,
        source_type="GITHUB",
        content="Designed event streaming pipeline handling 10k msgs/sec with Kafka consumer groups.",
        strength="STRONG",
        provenance="DEMONSTRATED",
        created_at=datetime.utcnow(),
    )

    # Resume Claim Evidence for Cap 3
    ev_claim = Evidence(
        id=uuid4(),
        application_id=app_id,
        capability_id=cap_claimed.id,
        candidate_source_id=None,
        source_type="RESUME",
        content="Optimized PostgreSQL queries across enterprise database.",
        strength="WEAK",
        provenance="CLAIM",
        created_at=datetime.utcnow(),
    )

    capabilities = [cap_verified, cap_demonstrated, cap_claimed, cap_unknown]
    evidences = [ev_demo, ev_claim]
    verifications = [ver_pass]

    return {
        "org_id": org_id,
        "app_id": app_id,
        "job_id": job_id,
        "cand_id": cand_id,
        "application": application,
        "capabilities": capabilities,
        "evidences": evidences,
        "verifications": verifications,
    }


@pytest.mark.asyncio
async def test_scorecard_generation_logic(mock_scorecard_data):
    """
    Verifies domain logic of pre-interview scorecard:
    - Verified capability becomes SUPPORTED (HIGH confidence).
    - Demonstrated capability becomes SUPPORTED (HIGH/MEDIUM confidence).
    - Claim-only capability becomes PARTIAL (LOW confidence).
    - Missing capability becomes strictly UNKNOWN (NONE confidence), preserving the core principle
      that absence of evidence is not evidence of absence.
    - Preserves provenance and generates targeted interview questions.
    """
    data = mock_scorecard_data
    mock_session = AsyncMock()

    # Configure session mocks
    mock_session.scalar.side_effect = [
        data["application"],  # app_stmt
        None,                 # existing_scorecard_rec
        None,                 # latest_plan
        None,                 # dataset_file
    ]

    mock_session.scalars.side_effect = [
        MagicMock(all=lambda: data["capabilities"]),   # caps_stmt
        MagicMock(all=lambda: data["evidences"]),      # ev_stmt
        MagicMock(all=lambda: data["verifications"]),  # ver_stmt
    ]

    scorecard = await generate_pre_interview_scorecard(
        session=mock_session,
        application_id=data["app_id"],
        organization_id=data["org_id"],
    )

    assert isinstance(scorecard, PreInterviewScorecard)
    assert scorecard.application_id == data["app_id"]
    assert scorecard.job_title == "Senior Backend Systems Engineer"
    assert scorecard.candidate_name == "Alex Chen"
    assert scorecard.total_capabilities == 4

    caps_by_name = {c.capability_name: c for c in scorecard.capabilities}

    # 1. Verified capability -> SUPPORTED, HIGH confidence
    cap1 = caps_by_name["FastAPI & AsyncIO"]
    assert cap1.status == PreInterviewCapabilityStatusEnum.SUPPORTED
    assert cap1.confidence == ConfidenceLevelEnum.HIGH
    assert len(cap1.supporting_evidence) == 1
    assert cap1.supporting_evidence[0].provenance == "VERIFIED"

    # 2. Demonstrated in code repository -> SUPPORTED
    cap2 = caps_by_name["Distributed Systems & Kafka"]
    assert cap2.status == PreInterviewCapabilityStatusEnum.SUPPORTED
    assert cap2.confidence in (ConfidenceLevelEnum.HIGH, ConfidenceLevelEnum.MEDIUM)
    assert len(cap2.supporting_evidence) == 1
    assert cap2.supporting_evidence[0].provenance == "DEMONSTRATED"
    assert "github.com" in (cap2.supporting_evidence[0].source_reference or "")

    # 3. Resume claim only -> PARTIAL, LOW confidence
    cap3 = caps_by_name["PostgreSQL Query Optimization"]
    assert cap3.status == PreInterviewCapabilityStatusEnum.PARTIAL
    assert cap3.confidence == ConfidenceLevelEnum.LOW
    assert len(cap3.supporting_evidence) == 1
    assert cap3.supporting_evidence[0].provenance == "CLAIM"

    # 4. No mention anywhere -> UNKNOWN, NONE confidence
    # Strict compliance: Absence of evidence is NOT negative evidence / failure
    cap4 = caps_by_name["Kubernetes & Terraform"]
    assert cap4.status == PreInterviewCapabilityStatusEnum.UNKNOWN
    assert cap4.confidence == ConfidenceLevelEnum.NONE
    assert "Absence of evidence is not evidence of absence" in cap4.status_rationale
    assert len(cap4.supporting_evidence) == 0

    # Summary metrics & Evidence Readiness Score
    assert scorecard.supported_count == 2
    assert scorecard.partial_count == 1
    assert scorecard.unknown_count == 1
    assert scorecard.contradictory_count == 0

    # Formula: (2*1.0 + 1*0.5) / 4 * 100 = 62.5%
    assert scorecard.evidence_readiness_score == 62.5
    assert "evidence completeness" in scorecard.score_explanation.lower()

    # Targeted interview questions generated for gaps
    assert len(cap3.targeted_questions) >= 1
    assert cap3.targeted_questions[0].intent == "VERIFY_CLAIM"

    assert len(cap4.targeted_questions) >= 1
    assert cap4.targeted_questions[0].intent == "PROBE_UNKNOWN"

    # Human review notice present
    assert "NOTICE FOR EVALUATORS" in scorecard.human_review_notice


@pytest.mark.asyncio
async def test_scorecard_cross_tenant_isolation(mock_scorecard_data):
    """
    Verifies that requesting a scorecard from a different organization raises ApplicationNotFoundError
    (tenant isolation enforced at the database query level).
    """
    data = mock_scorecard_data
    mock_session = AsyncMock()
    mock_session.scalar.return_value = None  # Not found under different org

    different_org_id = uuid4()
    with pytest.raises(ApplicationNotFoundError):
        await generate_pre_interview_scorecard(
            session=mock_session,
            application_id=data["app_id"],
            organization_id=different_org_id,
        )


def test_targeted_question_generator_unit():
    """
    Tests targeted question generation logic for diverse capability types and gap states.
    """
    # 1. Partial claim
    q_claim = generate_targeted_question("Docker", "Containerization", PreInterviewCapabilityStatusEnum.PARTIAL, "HIGH")
    assert q_claim.intent == "VERIFY_CLAIM"
    assert "production project" in q_claim.question_text

    # 2. Unknown requirement
    q_unknown = generate_targeted_question("Rust", "Memory safety", PreInterviewCapabilityStatusEnum.UNKNOWN, "MEDIUM")
    assert q_unknown.intent == "PROBE_UNKNOWN"
    assert "What exposure or related conceptual experience" in q_unknown.question_text

    # 3. Contradictory requirement
    q_contra = generate_targeted_question("AWS", "Cloud infra", PreInterviewCapabilityStatusEnum.CONTRADICTORY, "HIGH")
    assert q_contra.intent == "RESOLVE_CONTRADICTION"
    assert "conflicting references" in q_contra.question_text


def test_api_pre_interview_scorecard_endpoint(mock_scorecard_data):
    """
    Tests GET and POST /api/v1/applications/{application_id}/pre-interview-scorecard endpoints
    with role authorization and mocked database session.
    """
    data = mock_scorecard_data
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
        None,
        None,
        None,
    ]
    mock_db.scalars.side_effect = [
        MagicMock(all=lambda: data["capabilities"]),
        MagicMock(all=lambda: data["evidences"]),
        MagicMock(all=lambda: data["verifications"]),
    ]

    async def mock_db_session():
        yield mock_db

    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db_session] = mock_db_session

    try:
        with TestClient(app) as client:
            # 1. GET Scorecard
            resp = client.get(f"/api/v1/applications/{app_id}/pre-interview-scorecard")
            assert resp.status_code == 200
            scorecard_json = resp.json()

            assert scorecard_json["application_id"] == str(app_id)
            assert scorecard_json["candidate_name"] == "Alex Chen"
            assert scorecard_json["total_capabilities"] == 4
            assert scorecard_json["evidence_readiness_score"] == 62.5
            assert len(scorecard_json["capabilities"]) == 4

            # Verify presence of human notice and score explanation
            assert "NOTICE FOR EVALUATORS" in scorecard_json["human_review_notice"]
            assert "evidence completeness" in scorecard_json["score_explanation"].lower()

            # 2. POST Refresh Scorecard
            # Reset mock side effects for refresh call
            mock_db.scalar.side_effect = [
                data["application"],
                None,
                None,
                None,
            ]
            mock_db.scalars.side_effect = [
                MagicMock(all=lambda: data["capabilities"]),
                MagicMock(all=lambda: data["evidences"]),
                MagicMock(all=lambda: data["verifications"]),
            ]
            resp_refresh = client.post(f"/api/v1/applications/{app_id}/pre-interview-scorecard/refresh")
            assert resp_refresh.status_code == 200
            refresh_json = resp_refresh.json()
            assert refresh_json["application_id"] == str(app_id)
            assert refresh_json["evidence_readiness_score"] == 62.5

    finally:
        app.dependency_overrides.clear()
