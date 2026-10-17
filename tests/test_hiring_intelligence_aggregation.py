from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.roles import UserRole
from app.db.session import get_db_session
from app.main import app
from app.models.user import User
from app.schemas.hiring_autopsy import (
    AIImprovementSuggestion,
    AutopsyFinding,
    CapabilityOutcomeComparison,
    HiringAutopsyResponse,
)
from app.schemas.hiring_intelligence import HiringIntelligenceResponse
from app.schemas.post_hire_outcome import PostHireOutcomeResponse
from app.services.hiring_autopsy import ApplicationNotFoundError as AutopsyAppNotFoundError
from app.services.hiring_intelligence import aggregate_hiring_intelligence


class SimpleResult:
    """Mock for SQLAlchemy Result object with synchronous scalar and scalars methods."""

    def __init__(self, scalar_value=0, rows=None):
        self._scalar = scalar_value
        self._rows = rows or []

    def scalar_one(self):
        return self._scalar

    def scalar(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows


def _make_dummy_autopsy(
    app_id: UUID,
    job_id: UUID,
    findings: list[AutopsyFinding] | None = None,
    suggestions: list[AIImprovementSuggestion] | None = None,
    outcomes: list[PostHireOutcomeResponse] | None = None,
) -> HiringAutopsyResponse:
    return HiringAutopsyResponse(
        application_id=app_id,
        job_id=job_id,
        job_title="Senior Engineer",
        candidate_id=uuid4(),
        candidate_name="Jane Doe",
        decision_summary={"status": "HIRED", "decision": "OFFER"},
        decision_replay_summary={"total_capabilities_evaluated": 2},
        post_hire_outcomes=outcomes or [],
        capability_comparison=[
            CapabilityOutcomeComparison(
                capability_name="Python",
                pre_hire_evidence_state="DEMONSTRATED",
                interview_demonstration_state="DEMONSTRATED_STRONG",
                post_hire_outcome_status="MEETS_EXPECTATION",
                outcome_delta_observation="Aligned.",
            )
        ],
        findings=findings or [],
        ai_improvement_suggestions=suggestions or [],
        limitations=["Advisory only."],
    )


# ---------------------------------------------------------------------------
# 1. Empty Tenant
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aggregate_empty_tenant():
    """When a tenant has 0 applications and 0 outcomes, returns zeros with informational message."""
    mock_session = AsyncMock()

    # Query 1: count apps = 0; Query 2: app_ids = []; Query 3: count outcomes = 0
    mock_session.execute.side_effect = [
        SimpleResult(scalar_value=0),
        SimpleResult(rows=[]),
        SimpleResult(scalar_value=0),
    ]

    org_id = uuid4()
    result = await aggregate_hiring_intelligence(mock_session, org_id)

    assert result.total_applications == 0
    assert result.applications_with_outcomes == 0
    assert result.applications_without_outcomes == 0
    assert result.total_outcome_records == 0
    assert result.findings == []
    assert result.recommendations == []
    assert "No applications found" in result.message
    assert len(result.limitations) > 0


# ---------------------------------------------------------------------------
# 2. Applications Without Post-Hire Outcomes
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aggregate_applications_without_outcomes():
    """When a tenant has applications but no post-hire outcomes recorded yet."""
    mock_session = AsyncMock()

    # Query 1: 4 apps; Query 2: 0 apps with outcomes; Query 3: 0 outcomes
    mock_session.execute.side_effect = [
        SimpleResult(scalar_value=4),
        SimpleResult(rows=[]),
        SimpleResult(scalar_value=0),
    ]

    org_id = uuid4()
    result = await aggregate_hiring_intelligence(mock_session, org_id)

    assert result.total_applications == 4
    assert result.applications_with_outcomes == 0
    assert result.applications_without_outcomes == 4
    assert result.total_outcome_records == 0
    assert result.findings == []
    assert result.recommendations == []
    assert "No post-hire outcomes have been recorded" in result.message


# ---------------------------------------------------------------------------
# 3. Multiple Applications & Correct Outcome Counts
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aggregate_multiple_applications_and_correct_outcome_counts():
    """Verifies aggregation across multiple applications with correct outcome counts and provenance."""
    mock_session = AsyncMock()

    app1_id = uuid4()
    app2_id = uuid4()
    job_id = uuid4()
    org_id = uuid4()

    outcome1_id = uuid4()
    outcome2_id = uuid4()

    # Total 5 applications, 2 with outcomes, 3 total outcome records
    mock_session.execute.side_effect = [
        SimpleResult(scalar_value=5),
        SimpleResult(rows=[app1_id, app2_id]),
        SimpleResult(scalar_value=3),
    ]

    finding_shared = AutopsyFinding(
        category="UNVERIFIED_CAPABILITY",
        affected_capability="Distributed Systems",
        finding_text="Lacked live verification of distributed consensus.",
        grounded_facts=["Fact 1"],
    )
    suggestion_shared = AIImprovementSuggestion(
        suggestion_id="sug-1",
        affected_capability="Distributed Systems",
        observed_pattern="Pattern observed.",
        suggested_improvement="Add live consensus design round.",
        action_type="ADD_VERIFICATION_STEP",
        confidence_strength="HIGH_CONFIDENCE",
        supporting_records=["Record A"],
    )

    cand_id = uuid4()
    outcomes_app1 = [
        PostHireOutcomeResponse(
            id=outcome1_id,
            application_id=app1_id,
            job_id=job_id,
            job_title="Senior Engineer",
            candidate_id=cand_id,
            candidate_name="Jane Doe",
            capability_name="Distributed Systems",
            observed_outcome_description="Struggled with consensus.",
            outcome_status="NEEDS_DEVELOPMENT",
            outcome_period="90_DAYS",
            recorded_by=uuid4(),
            recorded_by_name="Engineering Manager",
            recorded_at="2026-01-01T00:00:00",
            created_at="2026-01-01T00:00:00",
        )
    ]

    outcomes_app2 = [
        PostHireOutcomeResponse(
            id=outcome2_id,
            application_id=app2_id,
            job_id=job_id,
            job_title="Senior Engineer",
            candidate_id=cand_id,
            candidate_name="Jane Doe",
            capability_name="Distributed Systems",
            observed_outcome_description="Needed mentoring on consensus.",
            outcome_status="PARTIALLY_MEETS_EXPECTATION",
            outcome_period="90_DAYS",
            recorded_by=uuid4(),
            recorded_by_name="Engineering Manager",
            recorded_at="2026-01-01T00:00:00",
            created_at="2026-01-01T00:00:00",
        )
    ]

    autopsy1 = _make_dummy_autopsy(
        app1_id, job_id, findings=[finding_shared], suggestions=[suggestion_shared], outcomes=outcomes_app1
    )
    autopsy2 = _make_dummy_autopsy(
        app2_id, job_id, findings=[finding_shared], suggestions=[suggestion_shared], outcomes=outcomes_app2
    )

    with patch(
        "app.services.hiring_intelligence.build_hiring_autopsy",
        side_effect=[autopsy1, autopsy2],
    ) as mock_autopsy:
        result = await aggregate_hiring_intelligence(mock_session, org_id)

        assert result.total_applications == 5
        assert result.applications_with_outcomes == 2
        assert result.applications_without_outcomes == 3
        assert result.total_outcome_records == 3

        # Findings aggregated
        assert len(result.findings) == 1
        agg_finding = result.findings[0]
        assert agg_finding.capability_name == "Distributed Systems"
        assert agg_finding.count == 2
        assert set(agg_finding.application_ids) == {app1_id, app2_id}
        assert job_id in agg_finding.job_ids
        assert set(agg_finding.outcome_ids) == {outcome1_id, outcome2_id}

        # Recommendations aggregated
        assert len(result.recommendations) == 1
        agg_rec = result.recommendations[0]
        assert agg_rec.capability_name == "Distributed Systems"
        assert agg_rec.count == 2
        assert set(agg_rec.application_ids) == {app1_id, app2_id}
        assert agg_rec.action_type == "ADD_VERIFICATION_STEP"
        assert agg_rec.confidence_strength == "HIGH_CONFIDENCE"

        # Verify autopsy was called with correct organization_id
        assert mock_autopsy.call_count == 2
        for call_args in mock_autopsy.call_args_list:
            assert call_args[0][2] == org_id


# ---------------------------------------------------------------------------
# 4. Repeated Findings and Recommendations Within a Single Application
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aggregate_repeated_findings_and_recommendations_in_single_app():
    """Verifies that an application producing repeated identical findings or recommendations is only counted once."""
    mock_session = AsyncMock()
    app_id = uuid4()
    job_id = uuid4()
    org_id = uuid4()

    mock_session.execute.side_effect = [
        SimpleResult(scalar_value=1),
        SimpleResult(rows=[app_id]),
        SimpleResult(scalar_value=2),
    ]

    repeated_finding = AutopsyFinding(
        category="UNVERIFIED_CAPABILITY",
        affected_capability="SQL Optimization",
        finding_text="Lacked query tuning verification.",
        grounded_facts=["Fact A"],
    )
    repeated_suggestion = AIImprovementSuggestion(
        suggestion_id="sug-rep",
        affected_capability="SQL Optimization",
        observed_pattern="Slow queries observed.",
        suggested_improvement="Include query tuning exercise.",
        action_type="ADD_VERIFICATION_STEP",
        confidence_strength="HIGH_CONFIDENCE",
        supporting_records=["Rec 1"],
    )

    # Both findings and suggestions are duplicated within the single autopsy
    autopsy = _make_dummy_autopsy(
        app_id,
        job_id,
        findings=[repeated_finding, repeated_finding],
        suggestions=[repeated_suggestion, repeated_suggestion],
    )

    with patch("app.services.hiring_intelligence.build_hiring_autopsy", return_value=autopsy):
        result = await aggregate_hiring_intelligence(mock_session, org_id)

        assert len(result.findings) == 1
        assert result.findings[0].count == 1
        assert result.findings[0].application_ids == [app_id]

        assert len(result.recommendations) == 1
        assert result.recommendations[0].count == 1
        assert result.recommendations[0].application_ids == [app_id]


# ---------------------------------------------------------------------------
# 5. Missing Findings or Recommendations
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aggregate_missing_findings_or_recommendations():
    """When an application with outcomes yields no findings and no suggestions, aggregate handles cleanly."""
    mock_session = AsyncMock()
    app_id = uuid4()
    job_id = uuid4()
    org_id = uuid4()

    mock_session.execute.side_effect = [
        SimpleResult(scalar_value=1),
        SimpleResult(rows=[app_id]),
        SimpleResult(scalar_value=1),
    ]

    autopsy = _make_dummy_autopsy(
        app_id,
        job_id,
        findings=[],
        suggestions=[],
    )

    with patch("app.services.hiring_intelligence.build_hiring_autopsy", return_value=autopsy):
        result = await aggregate_hiring_intelligence(mock_session, org_id)

        assert result.total_applications == 1
        assert result.applications_with_outcomes == 1
        assert result.findings == []
        assert result.recommendations == []
        assert "no process gaps or improvement suggestions were detected" in result.message


# ---------------------------------------------------------------------------
# 6. Tenant Isolation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aggregate_tenant_isolation():
    """Verifies that queries strictly filter by the provided organization_id."""
    executed_statements = []

    async def fake_execute(stmt):
        stmt_str = str(stmt)
        executed_statements.append(stmt)
        if "count" in stmt_str.lower():
            return SimpleResult(scalar_value=0)
        return SimpleResult(rows=[])

    mock_session = AsyncMock()
    mock_session.execute.side_effect = fake_execute

    org_a = uuid4()
    await aggregate_hiring_intelligence(mock_session, org_a)

    # Check that all 3 executed queries enforce Job.organization_id == org_a
    assert len(executed_statements) == 3
    for stmt in executed_statements:
        compiled_sql = str(stmt)
        assert "jobs.organization_id =" in compiled_sql


# ---------------------------------------------------------------------------
# 7. API Endpoint: Authorized Access
# ---------------------------------------------------------------------------
def test_api_hiring_intelligence_endpoint_authorized():
    """Verifies that an authorized recruiter can fetch aggregate hiring intelligence."""
    org_id = uuid4()
    recruiter_user = User(
        id=uuid4(),
        organization_id=org_id,
        email="recruiter@example.com",
        full_name="HR Recruiter",
        role=UserRole.RECRUITER.value,
        is_active=True,
    )

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        SimpleResult(scalar_value=2),
        SimpleResult(rows=[]),
        SimpleResult(scalar_value=0),
    ]

    async def mock_db_session():
        yield mock_db

    from app.api.dependencies import get_current_user

    async def mock_get_current_user():
        return recruiter_user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db_session] = mock_db_session

    try:
        with TestClient(app) as client:
            resp = client.get("/api/v1/applications/hiring-intelligence")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_applications"] == 2
            assert data["applications_with_outcomes"] == 0
            assert data["applications_without_outcomes"] == 2
            assert data["total_outcome_records"] == 0
            assert data["findings"] == []
            assert data["recommendations"] == []
            assert len(data["limitations"]) > 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 8. API Endpoint: Unauthorized Access (Candidate role)
# ---------------------------------------------------------------------------
def test_api_hiring_intelligence_endpoint_unauthorized_candidate():
    """Verifies that a user with CANDIDATE role receives 403 Forbidden."""
    candidate_user = User(
        id=uuid4(),
        organization_id=uuid4(),
        email="candidate@example.com",
        full_name="Alex Candidate",
        role=UserRole.CANDIDATE.value,
        is_active=True,
    )

    from app.api.dependencies import get_current_user

    async def mock_get_current_user():
        return candidate_user

    app.dependency_overrides[get_current_user] = mock_get_current_user

    try:
        with TestClient(app) as client:
            resp = client.get("/api/v1/applications/hiring-intelligence")
            assert resp.status_code == 403
            assert "permission" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 9. API Endpoint: Unauthenticated Access
# ---------------------------------------------------------------------------
def test_api_hiring_intelligence_endpoint_unauthenticated():
    """Verifies that an unauthenticated request without a token returns 401 Unauthorized."""
    # Ensure no dependency overrides
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        resp = client.get("/api/v1/applications/hiring-intelligence")
        assert resp.status_code == 401
