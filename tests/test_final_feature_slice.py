import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.roles import UserRole
from app.core.security import create_access_token
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.candidate_hiring_decision import CandidateHiringDecision
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.interview import InterviewSession
from app.models.interview_report import InterviewReportModel
from app.models.job import Job
from app.models.post_hire_outcome import PostHireOutcome
from app.models.user import User
from app.schemas.post_hire_outcome import OutcomePeriod, OutcomeStatus, PostHireOutcomeCreate
from app.services.decision_replay import ApplicationNotFoundError as ReplayAppNotFoundError, build_decision_replay
from app.services.hiring_autopsy import ApplicationNotFoundError as AutopsyAppNotFoundError, build_hiring_autopsy
from app.services.post_hire_outcome import (
    ApplicationNotFoundError as OutcomeAppNotFoundError,
    InvalidOutcomeStatusError,
    list_post_hire_outcomes,
    record_post_hire_outcome,
)


@pytest.fixture(scope="module")
def sync_client():
    with TestClient(app) as client:
        yield client


def build_mock_context():
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    job_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    app_id = uuid.uuid4()
    session_id = uuid.uuid4()
    report_id = uuid.uuid4()
    recruiter_id = uuid.uuid4()
    candidate_user_id = uuid.uuid4()

    recruiter = User(
        id=recruiter_id,
        organization_id=org_id,
        email="lead.recruiter@example.com",
        full_name="Alex Lead Recruiter",
        role=UserRole.HIRING_MANAGER.value,
        is_active=True,
    )

    candidate = Candidate(
        id=cand_id,
        full_name="Jordan Developer",
        email=f"jordan.{cand_id.hex[:6]}@example.com",
    )

    candidate_user = User(
        id=candidate_user_id,
        organization_id=org_id,
        email=candidate.email,
        full_name="Jordan Developer",
        role=UserRole.CANDIDATE.value,
        is_active=True,
    )

    job = Job(
        id=job_id,
        organization_id=org_id,
        title="Staff Backend Engineer",
        description="FastAPI, PostgreSQL, Redis, Concurrency",
    )

    cap1 = Capability(id=uuid.uuid4(), job_id=job_id, name="FastAPI & AsyncIO", importance="HIGH")
    cap2 = Capability(id=uuid.uuid4(), job_id=job_id, name="Redis Distributed Caching", importance="HIGH")

    application = Application(
        id=app_id,
        candidate_id=cand_id,
        job_id=job_id,
        candidate=candidate,
        job=job,
        status="SELECTED",
        shortlist_status="SELECTED",
        screening_status="COMPLETED",
        screening_notes="Strong backend background",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    decision = CandidateHiringDecision(
        id=uuid.uuid4(),
        application_id=app_id,
        job_id=job_id,
        decision="SELECTED",
        decision_reason="Demonstrated solid async patterns and production architecture skills.",
        decided_by=recruiter_id,
        decided_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    decision.decider = recruiter

    report = InterviewReportModel(
        id=report_id,
        interview_session_id=session_id,
        status="COMPLETED",
        summary="Candidate demonstrated proficiency in FastAPI; Redis was not probed in depth.",
        demonstrated_capabilities=[{"capability_name": "FastAPI & AsyncIO"}],
        unknown_capabilities=[{"capability_name": "Redis Distributed Caching"}],
        question_findings=[{"question": "How do you handle async sessions in FastAPI?"}],
        unresolved_areas=[{"area": "Redis cache invalidation"}],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    evidence_fastapi = Evidence(
        id=uuid.uuid4(),
        application_id=app_id,
        capability_id=cap1.id,
        capability=cap1,
        content="FastAPI async endpoints and dependencies",
        strength="HIGH",
        provenance="DEMONSTRATED",
        source_type="GITHUB",
    )

    evidence_redis = Evidence(
        id=uuid.uuid4(),
        application_id=app_id,
        capability_id=cap2.id,
        capability=cap2,
        content="Redis caching claim without verified repo proof",
        strength="LOW",
        provenance="CLAIM",
        source_type="RESUME",
    )

    return {
        "org_id": org_id,
        "other_org_id": other_org_id,
        "recruiter": recruiter,
        "candidate": candidate,
        "candidate_user": candidate_user,
        "job": job,
        "cap1": cap1,
        "cap2": cap2,
        "application": application,
        "decision": decision,
        "report": report,
        "evidence_fastapi": evidence_fastapi,
        "evidence_redis": evidence_redis,
    }


# ==============================================================================
# PART 1: DECISION REPLAY TESTS
# ==============================================================================

def test_authorized_hr_can_access_decision_replay(sync_client: TestClient):
    ctx = build_mock_context()
    token = create_access_token(str(ctx["recruiter"].id))

    async def override_user():
        return ctx["recruiter"]

    app.dependency_overrides[get_current_user] = override_user
    try:
        with patch("app.api.applications.build_decision_replay") as mock_replay:
            from app.schemas.decision_replay import DecisionContext, DecisionReplayResponse, ScreeningSnapshotContext
            mock_replay.return_value = DecisionReplayResponse(
                application_id=ctx["application"].id,
                job_id=ctx["job"].id,
                candidate_id=ctx["candidate"].id,
                reconstructed_at=datetime.now(timezone.utc),
                decision_context=DecisionContext(
                    application_id=ctx["application"].id,
                    candidate_id=ctx["candidate"].id,
                    candidate_name="Jordan Developer",
                    job_id=ctx["job"].id,
                    job_title=ctx["job"].title,
                    decision="SELECTED",
                    decision_reason="Hired based on live demonstration.",
                    decided_by_id=ctx["recruiter"].id,
                    decided_by_name="Alex Lead Recruiter",
                    decided_at=datetime.now(timezone.utc),
                    application_status="SELECTED",
                ),
                screening_context=ScreeningSnapshotContext(
                    screening_status="COMPLETED",
                    shortlist_status="SELECTED",
                ),
                limitations=["Snapshot reconstructed from persisted records."],
            )

            resp = sync_client.get(
                f"/api/v1/applications/{ctx['application'].id}/decision-replay",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["decision_context"]["decision"] == "SELECTED"
            assert data["decision_context"]["candidate_name"] == "Jordan Developer"
            assert len(data["limitations"]) > 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_candidate_cannot_access_decision_replay(sync_client: TestClient):
    ctx = build_mock_context()
    token = create_access_token(str(ctx["candidate_user"].id))

    async def override_user():
        return ctx["candidate_user"]

    app.dependency_overrides[get_current_user] = override_user
    try:
        resp = sync_client.get(
            f"/api/v1/applications/{ctx['application'].id}/decision-replay",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_cross_tenant_decision_replay_rejected():
    ctx = build_mock_context()
    session = AsyncMock()
    session.scalar.return_value = None  # Not found under other org

    with pytest.raises(ReplayAppNotFoundError):
        await build_decision_replay(
            session=session,
            application_id=ctx["application"].id,
            organization_id=ctx["other_org_id"],
        )


@pytest.mark.asyncio
async def test_decision_replay_preserves_evidence_and_interview_context():
    ctx = build_mock_context()
    session = AsyncMock()

    def mock_scalar(stmt):
        s = str(stmt).lower()
        if "from applications" in s:
            return ctx["application"]
        if "from interview_reports" in s:
            return ctx["report"]
        return None

    session.scalar.side_effect = mock_scalar

    def mock_execute(stmt):
        s = str(stmt).lower()
        res = MagicMock()
        if "from candidate_hiring_decisions" in s:
            res.scalars.return_value.all.return_value = [ctx["decision"]]
        elif "from evidence" in s:
            res.scalars.return_value.all.return_value = [ctx["evidence_fastapi"], ctx["evidence_redis"]]
        elif "from interview_integrity_events" in s:
            res.scalars.return_value.all.return_value = []
        else:
            res.scalars.return_value.all.return_value = []
        return res

    session.execute.side_effect = mock_execute

    replay = await build_decision_replay(
        session=session,
        application_id=ctx["application"].id,
        organization_id=ctx["org_id"],
    )

    assert replay.decision_context.decision == "SELECTED"
    assert len(replay.evidence_context) == 2
    assert replay.interview_context is not None
    assert "FastAPI & AsyncIO" in replay.interview_context.demonstrated_capabilities
    assert "Redis Distributed Caching" in replay.interview_context.unknown_capabilities


# ==============================================================================
# PART 2: POST-HIRE OUTCOMES TESTS
# ==============================================================================

def test_create_post_hire_outcome_success(sync_client: TestClient):
    ctx = build_mock_context()
    token = create_access_token(str(ctx["recruiter"].id))

    async def override_user():
        return ctx["recruiter"]

    app.dependency_overrides[get_current_user] = override_user

    payload = {
        "capability_name": "Redis Distributed Caching",
        "outcome_period": "90_DAYS",
        "observed_outcome_description": "Candidate struggled with Redis cluster lock TTL and required team pairing.",
        "outcome_status": "NEEDS_DEVELOPMENT",
        "evidence_reference": "PR #410",
    }

    try:
        with patch("app.api.applications.record_post_hire_outcome") as mock_record:
            from app.schemas.post_hire_outcome import PostHireOutcomeResponse
            mock_record.return_value = PostHireOutcomeResponse(
                id=uuid.uuid4(),
                application_id=ctx["application"].id,
                job_id=ctx["job"].id,
                job_title=ctx["job"].title,
                candidate_id=ctx["candidate"].id,
                candidate_name="Jordan Developer",
                recorded_by=ctx["recruiter"].id,
                recorded_by_name="Alex Lead Recruiter",
                recorded_at=datetime.now(timezone.utc),
                outcome_period=payload["outcome_period"],
                capability_name=payload["capability_name"],
                observed_outcome_description=payload["observed_outcome_description"],
                outcome_status=payload["outcome_status"],
                evidence_reference=payload["evidence_reference"],
                created_at=datetime.now(timezone.utc),
            )

            resp = sync_client.post(
                f"/api/v1/applications/{ctx['application'].id}/post-hire-outcomes",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == status.HTTP_201_CREATED
            data = resp.json()
            assert data["capability_name"] == "Redis Distributed Caching"
            assert data["outcome_status"] == "NEEDS_DEVELOPMENT"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_invalid_post_hire_outcome_status_rejected(sync_client: TestClient):
    ctx = build_mock_context()
    token = create_access_token(str(ctx["recruiter"].id))

    async def override_user():
        return ctx["recruiter"]

    app.dependency_overrides[get_current_user] = override_user

    payload = {
        "capability_name": "PostgreSQL",
        "outcome_period": "90_DAYS",
        "observed_outcome_description": "Exceeded all expectations on queries.",
        "outcome_status": "SUPERSTAR_100",  # Invalid enum
    }

    try:
        resp = sync_client.post(
            f"/api/v1/applications/{ctx['application'].id}/post-hire-outcomes",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_candidate_cannot_create_or_list_post_hire_outcomes(sync_client: TestClient):
    ctx = build_mock_context()
    token = create_access_token(str(ctx["candidate_user"].id))

    async def override_user():
        return ctx["candidate_user"]

    app.dependency_overrides[get_current_user] = override_user
    try:
        resp = sync_client.get(
            f"/api/v1/applications/{ctx['application'].id}/post-hire-outcomes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_cross_tenant_post_hire_outcome_rejected():
    ctx = build_mock_context()
    session = AsyncMock()
    session.scalar.return_value = None

    other_user = User(
        id=uuid.uuid4(),
        organization_id=ctx["other_org_id"],
        role=UserRole.HIRING_MANAGER.value,
        is_active=True,
    )

    with pytest.raises(OutcomeAppNotFoundError):
        await record_post_hire_outcome(
            session=session,
            application_id=ctx["application"].id,
            user=other_user,
            data=PostHireOutcomeCreate(
                capability_name="Redis",
                observed_outcome_description="Good performance.",
                outcome_status=OutcomeStatus.MEETS_EXPECTATION,
            ),
        )


# ==============================================================================
# PART 3: HIRING AUTOPSY & AI IMPROVEMENT SUGGESTIONS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_hiring_autopsy_identifies_unverified_capability_gap():
    ctx = build_mock_context()
    session = AsyncMock()

    outcome_redis = PostHireOutcome(
        id=uuid.uuid4(),
        application_id=ctx["application"].id,
        job_id=ctx["job"].id,
        recorded_by=ctx["recruiter"].id,
        recorded_at=datetime.now(timezone.utc),
        outcome_period="90_DAYS",
        capability_name="Redis Distributed Caching",
        observed_outcome_description="Candidate required additional support when implementing Redis distributed locks.",
        outcome_status="NEEDS_DEVELOPMENT",
    )
    outcome_redis.recorder = ctx["recruiter"]

    def mock_scalar(stmt):
        s = str(stmt).lower()
        if "from applications" in s:
            return ctx["application"]
        if "from candidate_hiring_decisions" in s:
            return ctx["decision"]
        if "from interview_reports" in s:
            return ctx["report"]
        return None

    session.scalar.side_effect = mock_scalar

    def mock_execute(stmt):
        s = str(stmt).lower()
        res = MagicMock()
        if "from evidence" in s:
            res.scalars.return_value.all.return_value = [ctx["evidence_fastapi"], ctx["evidence_redis"]]
        elif "from post_hire_outcomes" in s:
            res.scalars.return_value.all.return_value = [outcome_redis]
        elif "from capabilities" in s:
            res.scalars.return_value.all.return_value = [ctx["cap1"], ctx["cap2"]]
        else:
            res.scalars.return_value.all.return_value = []
        return res

    session.execute.side_effect = mock_execute

    autopsy = await build_hiring_autopsy(
        session=session,
        application_id=ctx["application"].id,
        organization_id=ctx["org_id"],
    )

    assert len(autopsy.capability_comparison) >= 2
    assert len(autopsy.findings) >= 1
    assert len(autopsy.ai_improvement_suggestions) >= 1

    # Verify finding category and affected capability
    redis_finding = next((f for f in autopsy.findings if "Redis" in f.affected_capability), None)
    assert redis_finding is not None
    assert redis_finding.category == "UNVERIFIED_CAPABILITY"

    # Verify suggestion is advisory and suggests a verification step
    redis_sug = next((s for s in autopsy.ai_improvement_suggestions if "Redis" in s.affected_capability), None)
    assert redis_sug is not None
    assert redis_sug.action_type == "ADD_VERIFICATION_STEP"
    assert redis_sug.is_advisory_only is True


def test_hiring_autopsy_endpoint_success(sync_client: TestClient):
    ctx = build_mock_context()
    token = create_access_token(str(ctx["recruiter"].id))

    async def override_user():
        return ctx["recruiter"]

    app.dependency_overrides[get_current_user] = override_user

    try:
        with patch("app.api.applications.build_hiring_autopsy") as mock_autopsy:
            from app.schemas.hiring_autopsy import AIImprovementSuggestion, AutopsyFinding, CapabilityOutcomeComparison, HiringAutopsyResponse
            mock_autopsy.return_value = HiringAutopsyResponse(
                application_id=ctx["application"].id,
                job_id=ctx["job"].id,
                job_title=ctx["job"].title,
                candidate_id=ctx["candidate"].id,
                candidate_name="Jordan Developer",
                decision_summary={"decision": "SELECTED"},
                decision_replay_summary={"total_capabilities_evaluated": 2},
                capability_comparison=[
                    CapabilityOutcomeComparison(
                        capability_name="Redis Distributed Caching",
                        pre_hire_evidence_state="UNKNOWN",
                        interview_demonstration_state="UNTESTED_OR_INSUFFICIENT",
                        post_hire_outcome_status="NEEDS_DEVELOPMENT",
                        outcome_delta_observation="Observed outcome indicated additional development needed.",
                    )
                ],
                findings=[
                    AutopsyFinding(
                        category="UNVERIFIED_CAPABILITY",
                        affected_capability="Redis Distributed Caching",
                        finding_text="Lacked live verification during hiring.",
                    )
                ],
                ai_improvement_suggestions=[
                    AIImprovementSuggestion(
                        suggestion_id="sug-1",
                        affected_capability="Redis Distributed Caching",
                        observed_pattern="Marked UNKNOWN pre-hire.",
                        suggested_improvement="Add live coding exercise for Redis in future interviews.",
                        action_type="ADD_VERIFICATION_STEP",
                        confidence_strength="HIGH_CONFIDENCE",
                        is_advisory_only=True,
                    )
                ],
                limitations=["Learning tool only. Does not evaluate human decision correctness."],
            )

            resp = sync_client.get(
                f"/api/v1/applications/{ctx['application'].id}/hiring-autopsy",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert len(data["capability_comparison"]) == 1
            assert len(data["ai_improvement_suggestions"]) == 1
            assert data["ai_improvement_suggestions"][0]["is_advisory_only"] is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_candidate_cannot_access_hiring_autopsy(sync_client: TestClient):
    ctx = build_mock_context()
    token = create_access_token(str(ctx["candidate_user"].id))

    async def override_user():
        return ctx["candidate_user"]

    app.dependency_overrides[get_current_user] = override_user
    try:
        resp = sync_client.get(
            f"/api/v1/applications/{ctx['application'].id}/hiring-autopsy",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        app.dependency_overrides.pop(get_current_user, None)
