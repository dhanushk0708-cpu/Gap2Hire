from datetime import datetime
from uuid import UUID, uuid4
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.main import app
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.candidate_source import CandidateSource
from app.models.capability import Capability
from app.models.evidence import Evidence
from app.models.job import Job
from app.models.user import User
from app.schemas.screening import (
    CandidateScreeningProfile,
    CapabilityScreeningEvaluation,
    JobTopNResult,
    TopNCandidateItem,
)
from app.services.evidence import record_candidate_evidence
from app.services.top_n_selection import (
    DynamicTopNSelector,
    candidate_comparison_key,
    compare_candidates,
)


async def setup_tenant_job_and_reviewer(client: AsyncClient, shortlist_size: int = 5):
    """Creates a tenant organization, recruiter user, and job."""
    org_name = f"Screening Corp {uuid4()}"
    email = f"recruiter-{uuid4()}@screeningcorp.com"
    password = "SecurePassword123!"

    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Screening Recruiter",
            "organization_name": org_name,
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    job_resp = await client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Senior AI Systems Engineer",
            "description": "Python, FastAPI, and Distributed Systems",
            "shortlist_size": shortlist_size,
        },
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    return headers, UUID(job_id)


async def create_candidate_and_app(
    client: AsyncClient,
    headers: dict,
    job_id: UUID,
    name: str,
    resume_text: str = "Experienced Python developer.",
) -> tuple[UUID, UUID]:
    """Helper to create a candidate and application."""
    cand_resp = await client.post(
        "/api/v1/candidates",
        headers=headers,
        json={"email": f"{uuid4()}@example.com", "full_name": name},
    )
    assert cand_resp.status_code == 201
    cand_id = UUID(cand_resp.json()["id"])

    app_resp = await client.post(
        "/api/v1/applications",
        headers=headers,
        json={"candidate_id": str(cand_id), "job_id": str(job_id)},
    )
    assert app_resp.status_code == 201
    app_id = UUID(app_resp.json()["id"])

    # Attach resume text
    async with async_session_factory() as session:
        app_obj = await session.get(Application, app_id)
        if app_obj:
            app_obj.resume_text = resume_text
            await session.commit()

    return cand_id, app_id


# -------------------------------------------------------------------------------------------------
# 1. Shortlist size configuration
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_job_shortlist_size_configuration():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_tenant_job_and_reviewer(client, shortlist_size=5)

        # Verify initial default
        job_get = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert job_get.status_code == 200
        assert job_get.json()["shortlist_size"] == 5

        # Update shortlist size via PUT endpoint
        put_resp = await client.put(
            f"/api/v1/jobs/{job_id}/shortlist-size",
            headers=headers,
            json={"shortlist_size": 3},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["shortlist_size"] == 3

        # Verify persisted in database
        job_get2 = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert job_get2.json()["shortlist_size"] == 3


# -------------------------------------------------------------------------------------------------
# 2. Candidate screening profile creation
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_candidate_screening_profile_creation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_tenant_job_and_reviewer(client)
        cand_id, app_id = await create_candidate_and_app(client, headers, job_id, "Alice Smith")

        resp = await client.get(f"/api/v1/applications/{app_id}/screening-profile", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        # Verify all mandatory structured dimensions
        assert data["application_id"] == str(app_id)
        assert data["candidate_id"] == str(cand_id)
        assert "hard_requirement_coverage" in data
        assert "required_capability_evidence" in data
        assert "preferred_capability_evidence" in data
        assert "evidence_strength" in data
        assert "evidence_provenance" in data
        assert "relevant_project_evidence" in data
        assert "relevant_resume_evidence" in data
        assert "unknown_capabilities" in data
        assert "insufficient_capabilities" in data
        assert "verification_needed" in data
        assert "summary_explanation" in data


# -------------------------------------------------------------------------------------------------
# 3. Evidence-to-capability mapping
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_evidence_to_capability_mapping():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_tenant_job_and_reviewer(client)
        cand_id, app_id = await create_candidate_and_app(client, headers, job_id, "Bob Jones")

        # Create 2 capabilities: 1 required (CRITICAL), 1 preferred (MEDIUM)
        cap1 = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json={"name": "FastAPI", "importance": "CRITICAL"},
        )
        cap1_id = UUID(cap1.json()["id"])

        cap2 = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json={"name": "Docker", "importance": "MEDIUM"},
        )
        cap2_id = UUID(cap2.json()["id"])

        # Record resume claim for FastAPI and demonstrated code for Docker
        async with async_session_factory() as session:
            me = await client.get("/api/v1/auth/me", headers=headers)
            org_id = UUID(me.json()["organization_id"])

            await record_candidate_evidence(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                capability_id=cap1_id,
                source_type="RESUME",
                strength="STRONG",
                provenance="CLAIM",
                content="Built microservices using FastAPI.",
            )
            await record_candidate_evidence(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                capability_id=cap2_id,
                source_type="GITHUB",
                strength="STRONG",
                provenance="DEMONSTRATED",
                content="Containerized services with multi-stage Dockerfile.",
            )

        resp = await client.get(f"/api/v1/applications/{app_id}/screening-profile", headers=headers)
        assert resp.status_code == 200
        profile = resp.json()

        assert profile["hard_requirement_coverage"]["total"] == 1
        assert profile["hard_requirement_coverage"]["met"] == 1
        assert profile["hard_requirement_coverage"]["is_satisfied"] is True
        assert len(profile["relevant_resume_evidence"]) == 1
        assert len(profile["relevant_project_evidence"]) == 1


# -------------------------------------------------------------------------------------------------
# 4. Unknown & Insufficient handling
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unknown_and_insufficient_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_tenant_job_and_reviewer(client)
        cand_id, app_id = await create_candidate_and_app(client, headers, job_id, "Charlie Brown")

        # Create 2 capabilities: Redis (unknown), Kubernetes (insufficient source)
        c_redis = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json={"name": "Redis", "importance": "HIGH"},
        )
        c_k8s = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json={"name": "Kubernetes", "importance": "HIGH"},
        )

        me = await client.get("/api/v1/auth/me", headers=headers)
        org_id = UUID(me.json()["organization_id"])

        # Record INSUFFICIENT for Kubernetes
        async with async_session_factory() as session:
            await record_candidate_evidence(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                capability_id=UUID(c_k8s.json()["id"]),
                source_type="GITHUB",
                strength="INSUFFICIENT",
                provenance="CLAIM",
                content=None,
            )

        resp = await client.get(f"/api/v1/applications/{app_id}/screening-profile", headers=headers)
        assert resp.status_code == 200
        p = resp.json()

        assert "Redis" in p["unknown_capabilities"]
        assert "Kubernetes" in p["insufficient_capabilities"]
        assert p["screening_status"] == "NEEDS_REVIEW"  # Unknowns flag NEEDS_REVIEW, not failure!
        assert len(p["verification_needed"]) == 2


# -------------------------------------------------------------------------------------------------
# 5. Hard requirement handling
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hard_requirement_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_tenant_job_and_reviewer(client)
        cand_id, app_id = await create_candidate_and_app(client, headers, job_id, "Diana Prince")

        cap = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json={"name": "PostgreSQL", "importance": "CRITICAL"},
        )
        cap_id = UUID(cap.json()["id"])

        me = await client.get("/api/v1/auth/me", headers=headers)
        org_id = UUID(me.json()["organization_id"])

        async with async_session_factory() as session:
            await record_candidate_evidence(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                capability_id=cap_id,
                source_type="GITHUB",
                strength="STRONG",
                provenance="DEMONSTRATED",
                content="Complex SQL migrations and indexing.",
            )

        resp = await client.get(f"/api/v1/applications/{app_id}/screening-profile", headers=headers)
        assert resp.status_code == 200
        p = resp.json()
        assert p["hard_requirement_coverage"]["is_satisfied"] is True
        assert p["screening_status"] == "ELIGIBLE"


# -------------------------------------------------------------------------------------------------
# 6. Deterministic candidate comparison
# -------------------------------------------------------------------------------------------------
def test_deterministic_candidate_comparison():
    now = datetime.utcnow()
    # Candidate A: 2 hard reqs met, 1 demonstrated, 0 unknowns
    prof_a = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Candidate A",
        candidate_email="a@test.com",
        job_id=uuid4(),
        job_title="Engineer",
        capability_results=[
            CapabilityScreeningEvaluation(
                capability_id=uuid4(),
                capability_name="Python",
                is_required=True,
                status="MET",
                provenance="DEMONSTRATED",
                evidence_strength="STRONG",
            ),
            CapabilityScreeningEvaluation(
                capability_id=uuid4(),
                capability_name="FastAPI",
                is_required=True,
                status="MET",
                provenance="CLAIM",
                evidence_strength="STRONG",
            ),
        ],
        hard_requirement_coverage={"total": 2, "met": 2},
        evidence_strength={"STRONG": 2},
        evidence_provenance={"DEMONSTRATED": 1, "CLAIM": 1},
        applied_at=now,
    )

    # Candidate B: 1 hard req met, 4 preferred skills met
    prof_b = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Candidate B",
        candidate_email="b@test.com",
        job_id=uuid4(),
        job_title="Engineer",
        capability_results=[
            CapabilityScreeningEvaluation(
                capability_id=uuid4(),
                capability_name="Python",
                is_required=True,
                status="MET",
                provenance="DEMONSTRATED",
                evidence_strength="STRONG",
            ),
            CapabilityScreeningEvaluation(
                capability_id=uuid4(),
                capability_name="FastAPI",
                is_required=True,
                status="UNKNOWN",
                provenance="UNKNOWN",
            ),
            CapabilityScreeningEvaluation(
                capability_id=uuid4(),
                capability_name="Docker",
                is_required=False,
                status="MET",
                provenance="DEMONSTRATED",
            ),
            CapabilityScreeningEvaluation(
                capability_id=uuid4(),
                capability_name="Redis",
                is_required=False,
                status="MET",
                provenance="DEMONSTRATED",
            ),
        ],
        hard_requirement_coverage={"total": 2, "met": 1},
        unknown_capabilities=["FastAPI"],
        evidence_strength={"STRONG": 3},
        evidence_provenance={"DEMONSTRATED": 3},
        applied_at=now,
    )

    # Deterministic policy: Hard requirement coverage takes absolute precedence
    assert compare_candidates(prof_a, prof_b) > 0
    assert compare_candidates(prof_b, prof_a) < 0


# -------------------------------------------------------------------------------------------------
# -------------------------------------------------------------------------------------------------
# 7. Top-N is maximum, not quota: 1 qualified + 1 unqualified candidate -> 1 shortlisted
# -------------------------------------------------------------------------------------------------
def test_top_n_is_maximum_not_quota_one_qualified_one_unqualified():
    """
    Top-N is a MAXIMUM, not a quota.
    Top-N=5 with 2 candidates (1 qualified + 1 unqualified) -> exactly 1 in Top-N.
    Empty capacity (4 positions) remains unfilled.
    """
    selector = DynamicTopNSelector(shortlist_size=5, job_id=uuid4(), job_title="Architect")
    now = datetime.utcnow()

    # c1 is qualified: satisfies all 2 required capabilities
    c1 = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Qualified Cand",
        candidate_email="c1@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 2, "met": 2, "is_satisfied": True},
        evidence_provenance={"DEMONSTRATED": 2},
        applied_at=now,
    )
    # c2 is unqualified: satisfies only 1 of 2 required capabilities
    c2 = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Unqualified Cand",
        candidate_email="c2@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 2, "met": 1, "is_satisfied": False},
        unknown_capabilities=["FastAPI"],
        applied_at=now,
    )

    ev1 = selector.add_candidate(c1)
    ev2 = selector.add_candidate(c2)

    assert ev1["action"] == "ENTERED_TOP_N"
    assert ev2["action"] == "EXCLUDED"
    assert "Missing required capabilities" in ev2["reason"]

    res = selector.to_job_top_n_result()
    # Exactly 1 candidate shortlisted despite shortlist_size=5
    assert len(res.top_n_candidates) == 1
    assert res.top_n_candidates[0].candidate_name == "Qualified Cand"
    # c2 remains excluded with transparent reason
    assert len(res.excluded_candidates) == 1
    assert res.excluded_candidates[0].candidate_name == "Unqualified Cand"
    assert "Missing required capabilities" in res.excluded_candidates[0].selection_reason
    # Cutoff candidate is None because Top-N capacity is not full
    assert res.cutoff_candidate is None


# -------------------------------------------------------------------------------------------------
# 8. Top-N=5 with 2 qualified candidates -> 2 shortlisted, empty capacity unfilled
# -------------------------------------------------------------------------------------------------
def test_top_n_with_two_qualified_candidates():
    """
    Top-N=5 with 2 qualified candidates -> exactly 2 shortlisted.
    Empty capacity (3 positions) remains unfilled.
    """
    selector = DynamicTopNSelector(shortlist_size=5, job_id=uuid4(), job_title="Architect")
    now = datetime.utcnow()

    c1 = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Qualified Cand 1",
        candidate_email="c1@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 2, "met": 2, "is_satisfied": True},
        evidence_provenance={"DEMONSTRATED": 2},
        applied_at=now,
    )
    c2 = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Qualified Cand 2",
        candidate_email="c2@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 2, "met": 2, "is_satisfied": True},
        evidence_provenance={"CLAIM": 2},
        applied_at=now,
    )

    selector.add_candidate(c1)
    selector.add_candidate(c2)

    res = selector.to_job_top_n_result()
    assert len(res.top_n_candidates) == 2
    assert len(res.excluded_candidates) == 0
    # Capacity is not filled (2 < 5), so cutoff is None
    assert res.cutoff_candidate is None


# -------------------------------------------------------------------------------------------------
# 9. Zero-evidence candidate never enters Top-N
# -------------------------------------------------------------------------------------------------
def test_zero_evidence_candidate_never_enters_top_n():
    selector = DynamicTopNSelector(shortlist_size=5, job_id=uuid4(), job_title="Architect")
    now = datetime.utcnow()

    zero_ev_cand = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Zero Evidence",
        candidate_email="zero@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 2, "met": 0, "is_satisfied": False},
        evidence_provenance={},
        evidence_strength={},
        unknown_capabilities=["Python", "FastAPI"],
        applied_at=now,
    )

    ev = selector.add_candidate(zero_ev_cand)
    assert ev["action"] == "EXCLUDED"
    assert "Missing required capabilities" in ev["reason"]

    res = selector.to_job_top_n_result()
    assert len(res.top_n_candidates) == 0
    assert len(res.excluded_candidates) == 1
    assert res.excluded_candidates[0].candidate_name == "Zero Evidence"


# -------------------------------------------------------------------------------------------------
# 10. Insufficient required capability candidate does not enter Top-N
# -------------------------------------------------------------------------------------------------
def test_insufficient_required_capability_does_not_enter_top_n():
    selector = DynamicTopNSelector(shortlist_size=5, job_id=uuid4(), job_title="Architect")
    now = datetime.utcnow()

    cand = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Insufficient Candidate",
        candidate_email="insufficient@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 3, "met": 2, "is_satisfied": False},
        insufficient_capabilities=["FastAPI"],
        applied_at=now,
    )

    ev = selector.add_candidate(cand)
    assert ev["action"] == "EXCLUDED"
    assert "Missing required capabilities" in ev["reason"]

    res = selector.to_job_top_n_result()
    assert len(res.top_n_candidates) == 0
    assert len(res.excluded_candidates) == 1


# -------------------------------------------------------------------------------------------------
# 11. Stronger later candidate displaces weaker eligible candidate
# -------------------------------------------------------------------------------------------------
def test_later_stronger_candidate_replaces_cutoff():
    selector = DynamicTopNSelector(shortlist_size=2, job_id=uuid4(), job_title="Architect")
    now = datetime.utcnow()

    # Both c1 and c2 are eligible (both satisfy hard reqs)
    c1 = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Cand 1 (Strong)",
        candidate_email="c1@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 2, "met": 2, "is_satisfied": True},
        evidence_provenance={"DEMONSTRATED": 2},
        applied_at=now,
    )
    c2 = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Cand 2 (Cutoff)",
        candidate_email="c2@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 2, "met": 2, "is_satisfied": True},
        evidence_provenance={"CLAIM": 2},
        applied_at=now,
    )

    selector.add_candidate(c1)
    selector.add_candidate(c2)
    assert len(selector.get_top_n()) == 2
    assert selector.get_cutoff().candidate_name == "Cand 2 (Cutoff)"

    # Candidate 3 arrives later: has 2 hard requirements met AND demonstrated evidence (stronger than Candidate 2)
    c3 = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Cand 3 (Late Strong)",
        candidate_email="c3@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 2, "met": 2, "is_satisfied": True},
        evidence_provenance={"DEMONSTRATED": 1, "CLAIM": 1},
        applied_at=now,
    )
    ev3 = selector.add_candidate(c3)

    assert ev3["action"] == "DISPLACED_CUTOFF"
    assert ev3["displaced_candidate"] == "Cand 2 (Cutoff)"

    res = selector.to_job_top_n_result()
    assert len(res.top_n_candidates) == 2
    top_names = [c.candidate_name for c in res.top_n_candidates]
    assert "Cand 1 (Strong)" in top_names
    assert "Cand 3 (Late Strong)" in top_names
    assert len(res.excluded_candidates) == 1
    assert res.excluded_candidates[0].candidate_name == "Cand 2 (Cutoff)"


# -------------------------------------------------------------------------------------------------
# 12. Candidate inserted at non-terminal rank
# -------------------------------------------------------------------------------------------------
def test_candidate_inserted_at_non_terminal_rank():
    selector = DynamicTopNSelector(shortlist_size=3, job_id=uuid4(), job_title="Lead")
    now = datetime.utcnow()

    # Initial 3 eligible candidates
    for i in range(3):
        selector.add_candidate(
            CandidateScreeningProfile(
                application_id=uuid4(),
                candidate_id=uuid4(),
                candidate_name=f"Rank {i+1}",
                candidate_email=f"r{i+1}@test.com",
                job_id=selector.job_id,
                job_title=selector.job_title,
                hard_requirement_coverage={"total": 2, "met": 2, "is_satisfied": True},
                evidence_provenance={"DEMONSTRATED": 3 - i},
                applied_at=now,
            )
        )

    # Super candidate arrives with 5 demonstrated capabilities (takes Rank 1)
    super_cand = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Super Candidate",
        candidate_email="super@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 2, "met": 2, "is_satisfied": True},
        evidence_provenance={"DEMONSTRATED": 5},
        applied_at=now,
    )
    selector.add_candidate(super_cand)

    res = selector.to_job_top_n_result()
    assert res.top_n_candidates[0].candidate_name == "Super Candidate"
    assert res.top_n_candidates[0].rank == 1
    assert res.top_n_candidates[1].candidate_name == "Rank 1"
    assert res.top_n_candidates[2].candidate_name == "Rank 2"
    assert res.excluded_candidates[0].candidate_name == "Rank 3"


# -------------------------------------------------------------------------------------------------
# 10. Candidate outside Top-N
# -------------------------------------------------------------------------------------------------
def test_weaker_candidate_outside_top_n():
    selector = DynamicTopNSelector(shortlist_size=1, job_id=uuid4(), job_title="Lead")
    now = datetime.utcnow()

    strong = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Strong Leader",
        candidate_email="lead@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 2, "met": 2},
        applied_at=now,
    )
    weak = CandidateScreeningProfile(
        application_id=uuid4(),
        candidate_id=uuid4(),
        candidate_name="Junior Dev",
        candidate_email="jr@test.com",
        job_id=selector.job_id,
        job_title=selector.job_title,
        hard_requirement_coverage={"total": 2, "met": 0},
        applied_at=now,
    )

    selector.add_candidate(strong)
    ev_weak = selector.add_candidate(weak)

    assert ev_weak["action"] == "EXCLUDED"
    res = selector.to_job_top_n_result()
    assert len(res.top_n_candidates) == 1
    assert res.top_n_candidates[0].candidate_name == "Strong Leader"
    assert len(res.excluded_candidates) == 1
    assert res.excluded_candidates[0].candidate_name == "Junior Dev"


# -------------------------------------------------------------------------------------------------
# 11. Empty candidate set
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_candidate_set():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_tenant_job_and_reviewer(client)

        resp = await client.post(f"/api/v1/jobs/{job_id}/screening/run", headers=headers)
        assert resp.status_code == 200
        res = resp.json()
        assert res["total_candidates_evaluated"] == 0
        assert len(res["top_n_candidates"]) == 0
        assert res["cutoff_candidate"] is None


# -------------------------------------------------------------------------------------------------
# 12. Tenant isolation in screening
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tenant_isolation_in_screening():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers1, job1 = await setup_tenant_job_and_reviewer(client)
        headers2, job2 = await setup_tenant_job_and_reviewer(client)

        cand1, app1 = await create_candidate_and_app(client, headers1, job1, "Tenant 1 Cand")

        # Org 2 attempts to run screening on Org 1's job -> 404
        bad_run = await client.post(f"/api/v1/jobs/{job1}/screening/run", headers=headers2)
        assert bad_run.status_code == 404

        # Org 2 attempts to access Org 1's candidate screening profile -> 404
        bad_prof = await client.get(f"/api/v1/applications/{app1}/screening-profile", headers=headers2)
        assert bad_prof.status_code == 404


# -------------------------------------------------------------------------------------------------
# 13. HR authorization
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hr_authorization_and_review():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_tenant_job_and_reviewer(client)

        # Unauthenticated request -> 401
        unauth = await client.post(f"/api/v1/jobs/{job_id}/screening/run")
        assert unauth.status_code == 401

        # Authorized recruiter request -> 200
        auth_ok = await client.get(f"/api/v1/jobs/{job_id}/screening/top-n", headers=headers)
        assert auth_ok.status_code == 200


# -------------------------------------------------------------------------------------------------
# 14. Evidence provenance preserved
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_evidence_provenance_preservation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_tenant_job_and_reviewer(client)
        cand_id, app_id = await create_candidate_and_app(client, headers, job_id, "Provenance Candidate")

        cap = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json={"name": "FastAPI", "importance": "HIGH"},
        )
        cap_id = UUID(cap.json()["id"])

        me = await client.get("/api/v1/auth/me", headers=headers)
        org_id = UUID(me.json()["organization_id"])

        # Create a candidate source
        async with async_session_factory() as session:
            src = CandidateSource(
                application_id=app_id,
                url="https://github.com/example/repo",
                source_type="GITHUB",
            )
            session.add(src)
            await session.commit()
            await session.refresh(src)
            src_id = src.id

            await record_candidate_evidence(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                capability_id=cap_id,
                source_type="GITHUB",
                strength="STRONG",
                provenance="DEMONSTRATED",
                content="FastAPI route definitions in app/main.py",
                candidate_source_id=src_id,
            )

        resp = await client.get(f"/api/v1/applications/{app_id}/screening-profile", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        eval_item = data["capability_results"][0]

        assert eval_item["provenance"] == "DEMONSTRATED"
        assert eval_item["source_url"] == "https://github.com/example/repo"
        assert eval_item["source_type"] == "GITHUB"


# -------------------------------------------------------------------------------------------------
# 15. Screening result API & Top-N run
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_screening_run_api_and_results():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_tenant_job_and_reviewer(client, shortlist_size=1)
        c1_id, app1_id = await create_candidate_and_app(client, headers, job_id, "Candidate 1", "Python and SQL.")
        c2_id, app2_id = await create_candidate_and_app(client, headers, job_id, "Candidate 2", "Python, FastAPI, SQL, Docker.")

        # Create Capability
        cap = await client.post(
            f"/api/v1/jobs/{job_id}/capabilities",
            headers=headers,
            json={"name": "FastAPI", "importance": "CRITICAL"},
        )
        cap_id = UUID(cap.json()["id"])

        me = await client.get("/api/v1/auth/me", headers=headers)
        org_id = UUID(me.json()["organization_id"])

        # Give Candidate 2 demonstrated proof for FastAPI
        async with async_session_factory() as session:
            await record_candidate_evidence(
                session=session,
                organization_id=org_id,
                application_id=app2_id,
                capability_id=cap_id,
                source_type="GITHUB",
                strength="STRONG",
                provenance="DEMONSTRATED",
                content="Demonstrated FastAPI in repository.",
            )

        # Run automated screening workflow for the job
        run_resp = await client.post(f"/api/v1/jobs/{job_id}/screening/run", headers=headers)
        assert run_resp.status_code == 200
        result = run_resp.json()

        assert result["total_candidates_evaluated"] == 2
        assert len(result["top_n_candidates"]) == 1
        assert result["top_n_candidates"][0]["application_id"] == str(app2_id)
        assert len(result["excluded_candidates"]) == 1
        assert result["excluded_candidates"][0]["application_id"] == str(app1_id)

        # Verify database statuses updated
        async with async_session_factory() as session:
            a1 = await session.get(Application, app1_id)
            a2 = await session.get(Application, app2_id)
            assert a2.shortlist_status == "SHORTLISTED"
            assert a1.shortlist_status == "NOT_SHORTLISTED"


# -------------------------------------------------------------------------------------------------
# 16. Real smoke test: Dhanush / Inslight Application
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_real_smoke_test_dhanush_inslight():
    """
    Smoke test targeting the real application 591ea6bb-cfa3-4c97-a5b5-9e6c6d031f5c
    and candidate 767061b1-a7fb-4c19-9583-4b2ed2e5c145.
    """
    dhanush_app_id = UUID("591ea6bb-cfa3-4c97-a5b5-9e6c6d031f5c")
    async with async_session_factory() as session:
        stmt = (
            select(Application)
            .join(Job, Job.id == Application.job_id)
            .where(Application.id == dhanush_app_id)
            .options(selectinload(Application.job))
        )
        app_obj = await session.scalar(stmt)
        if not app_obj:
            pytest.skip("Dhanush test application not present in this database instance.")

        from app.services.screening import build_candidate_screening_profile
        profile = await build_candidate_screening_profile(
            session=session,
            application_id=dhanush_app_id,
            organization_id=app_obj.job.organization_id,
        )

        assert profile.application_id == dhanush_app_id
        assert profile.candidate_name is not None
        assert profile.hard_requirement_coverage is not None
        assert isinstance(profile.capability_results, list)
        assert profile.screening_status in {"ELIGIBLE", "NEEDS_REVIEW", "NOT_ELIGIBLE"}


# -------------------------------------------------------------------------------------------------
# 17. Evidence semantics: CLAIM != DEMONSTRATED != VERIFIED, and factual summary counts
# -------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_evidence_semantics_and_factual_screening_summary():
    """
    Verifies:
    1. Resume claim renders as CLAIM (not as VERIFIED).
    2. Demonstrated source renders as DEMONSTRATED.
    3. Verified evidence renders as VERIFIED.
    4. UNKNOWN renders correctly with verification_needed=True.
    5. INSUFFICIENT renders correctly with verification_needed=True.
    6. Screening summary counts all evidence states factually.
    7. Resume-only candidate does not display 'verified'.
    8. Mixed CLAIM + DEMONSTRATED candidate displays both correctly.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, job_id = await setup_tenant_job_and_reviewer(client)
        cand_id, app_id = await create_candidate_and_app(client, headers, job_id, "Multi Evidence Candidate")

        # Create 5 capabilities
        c_python = await client.post(f"/api/v1/jobs/{job_id}/capabilities", headers=headers, json={"name": "Python", "importance": "CRITICAL"})
        c_fastapi = await client.post(f"/api/v1/jobs/{job_id}/capabilities", headers=headers, json={"name": "FastAPI", "importance": "CRITICAL"})
        c_postgres = await client.post(f"/api/v1/jobs/{job_id}/capabilities", headers=headers, json={"name": "PostgreSQL", "importance": "HIGH"})
        c_docker = await client.post(f"/api/v1/jobs/{job_id}/capabilities", headers=headers, json={"name": "Docker", "importance": "MEDIUM"})
        c_redis = await client.post(f"/api/v1/jobs/{job_id}/capabilities", headers=headers, json={"name": "Redis", "importance": "LOW"})

        me = await client.get("/api/v1/auth/me", headers=headers)
        org_id = UUID(me.json()["organization_id"])

        from app.models.verification import Verification
        async with async_session_factory() as session:
            # 1. Python: VERIFIED via practical assessment
            ver = Verification(
                application_id=app_id,
                capability_id=UUID(c_python.json()["id"]),
                type="ASSESSMENT",
                status="COMPLETED",
                result="PASS",
            )
            session.add(ver)

            # 2. FastAPI: DEMONSTRATED via GitHub source
            src = CandidateSource(
                application_id=app_id,
                url="https://github.com/candidate/fastapi-app",
                source_type="GITHUB",
            )
            session.add(src)
            await session.commit()
            await session.refresh(src)

            await record_candidate_evidence(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                capability_id=UUID(c_fastapi.json()["id"]),
                source_type="GITHUB",
                strength="STRONG",
                provenance="DEMONSTRATED",
                content="Demonstrated async FastAPI endpoints.",
                candidate_source_id=src.id,
            )

            # 3. PostgreSQL: CLAIM via Resume
            await record_candidate_evidence(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                capability_id=UUID(c_postgres.json()["id"]),
                source_type="RESUME",
                strength="STRONG",
                provenance="CLAIM",
                content="3 years PostgreSQL schema design.",
            )

            # 4. Docker: INSUFFICIENT
            await record_candidate_evidence(
                session=session,
                organization_id=org_id,
                application_id=app_id,
                capability_id=UUID(c_docker.json()["id"]),
                source_type="GITHUB",
                strength="INSUFFICIENT",
                provenance="CLAIM",
                content=None,
            )

            # 5. Redis: left with 0 evidence -> UNKNOWN
            await session.commit()

        # Query Screening Report endpoint
        resp = await client.get(f"/api/v1/applications/{app_id}/screening", headers=headers)
        assert resp.status_code == 200
        report = resp.json()

        # Factual counts
        assert report["verified_count"] == 1
        assert report["demonstrated_count"] == 1
        assert report["claims_count"] == 2  # PostgreSQL (resume claim) + Docker (insufficient claim)
        assert report["unknown_count"] == 1  # Redis (unknown)
        assert report["insufficient_count"] == 1  # Docker (insufficient)
        assert report["verification_needed_count"] >= 3

        # Semantic distinctions
        evals_by_name = {e["requirement_name"]: e for e in report["requirements_evaluated"]}

        # Python: VERIFIED
        assert evals_by_name["Python"]["provenance"] == "VERIFIED"
        assert evals_by_name["Python"]["verification_status"] == "PASSED"

        # FastAPI: DEMONSTRATED (NOT VERIFIED!)
        assert evals_by_name["FastAPI"]["provenance"] == "DEMONSTRATED"
        assert evals_by_name["FastAPI"]["verification_status"] == "NOT_YET_VERIFIED"
        assert evals_by_name["FastAPI"]["provenance"] != "VERIFIED"

        # PostgreSQL: CLAIM (NOT VERIFIED, NOT DEMONSTRATED!)
        assert evals_by_name["PostgreSQL"]["provenance"] == "CLAIM"
        assert evals_by_name["PostgreSQL"]["verification_status"] == "NOT_YET_VERIFIED"
        assert evals_by_name["PostgreSQL"]["provenance"] != "VERIFIED"
        assert evals_by_name["PostgreSQL"]["provenance"] != "DEMONSTRATED"

        # Docker: INSUFFICIENT
        assert evals_by_name["Docker"]["status"] == "INSUFFICIENT"
        assert evals_by_name["Docker"]["verification_needed"] is True

        # Redis: UNKNOWN
        assert evals_by_name["Redis"]["status"] == "UNKNOWN"
        assert evals_by_name["Redis"]["provenance"] == "UNKNOWN"
        assert evals_by_name["Redis"]["verification_needed"] is True

        # Summary does not claim candidate is fully verified
        assert "Independent verification is still required" in report["summary_explanation"] or "preliminary" in report["summary_explanation"]
        assert "ready for shortlisting" not in report["summary_explanation"].lower()

