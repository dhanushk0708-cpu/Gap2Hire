from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.job import Job
from app.models.post_hire_outcome import PostHireOutcome
from app.schemas.hiring_intelligence import (
    AggregatedFinding,
    AggregatedRecommendation,
    HiringIntelligenceResponse,
)
from app.services.hiring_autopsy import (
    ApplicationNotFoundError as AutopsyAppNotFoundError,
    build_hiring_autopsy,
)

DEFAULT_LIMITATIONS: List[str] = [
    "Hiring intelligence is an aggregate organizational learning tool that identifies process improvement opportunities.",
    "It does not evaluate whether individual humans made correct or incorrect hiring decisions.",
    "AI recommendations are purely advisory and do not automatically alter job blueprints, interview plans, or hiring decisions.",
    "Aggregate insights require sufficient post-hire outcome data to identify statistically meaningful patterns.",
]


async def aggregate_hiring_intelligence(
    session: AsyncSession,
    organization_id: UUID,
) -> HiringIntelligenceResponse:
    """Aggregate hiring intelligence across all applications of a tenant.

    Returns counts, aggregated findings, and recommendations derived from the
    hiring autopsy service.
    """
    # 1. Total applications for the organization
    total_apps_stmt = (
        select(func.count(Application.id))
        .join(Job, Job.id == Application.job_id)
        .where(Job.organization_id == organization_id)
    )
    total_apps_result = await session.execute(total_apps_stmt)
    total_applications = total_apps_result.scalar() or 0

    # 2. Distinct applications that have at least one PostHireOutcome
    apps_with_outcomes_stmt = (
        select(Application.id)
        .join(PostHireOutcome, PostHireOutcome.application_id == Application.id)
        .join(Job, Job.id == Application.job_id)
        .where(Job.organization_id == organization_id)
        .distinct()
    )
    apps_with_outcomes_result = await session.execute(apps_with_outcomes_stmt)
    apps_with_outcomes_scalars = apps_with_outcomes_result.scalars().all()
    apps_with_outcomes = [app_id for app_id in apps_with_outcomes_scalars if app_id is not None]
    applications_with_outcomes = len(apps_with_outcomes)
    applications_without_outcomes = max(0, total_applications - applications_with_outcomes)

    # 3. Total outcome records for this organization
    total_outcome_stmt = (
        select(func.count(PostHireOutcome.id))
        .join(Application, Application.id == PostHireOutcome.application_id)
        .join(Job, Job.id == Application.job_id)
        .where(Job.organization_id == organization_id)
    )
    total_outcome_result = await session.execute(total_outcome_stmt)
    total_outcome_records = total_outcome_result.scalar() or 0

    # If there are no applications for the tenant
    if total_applications == 0:
        return HiringIntelligenceResponse(
            total_applications=0,
            applications_with_outcomes=0,
            applications_without_outcomes=0,
            total_outcome_records=0,
            findings=[],
            recommendations=[],
            limitations=DEFAULT_LIMITATIONS,
            message="No applications found for this organization.",
        )

    # If there are applications but no post-hire outcomes yet
    if applications_with_outcomes == 0:
        return HiringIntelligenceResponse(
            total_applications=total_applications,
            applications_with_outcomes=0,
            applications_without_outcomes=applications_without_outcomes,
            total_outcome_records=0,
            findings=[],
            recommendations=[],
            limitations=DEFAULT_LIMITATIONS,
            message="No post-hire outcomes have been recorded for this organization's applications yet. Findings and AI improvement recommendations require post-hire observation data.",
        )

    # 4. Aggregate findings and recommendations via hiring_autopsy
    finding_counts: Counter[tuple] = Counter()
    finding_apps: defaultdict[tuple, List[UUID]] = defaultdict(list)
    finding_jobs: defaultdict[tuple, Set[UUID]] = defaultdict(set)
    finding_outcomes: defaultdict[tuple, Set[UUID]] = defaultdict(set)
    finding_evidence: defaultdict[tuple, Set[UUID]] = defaultdict(set)

    recommendation_counts: Counter[tuple] = Counter()
    recommendation_apps: defaultdict[tuple, List[UUID]] = defaultdict(list)
    recommendation_supporting: defaultdict[tuple, List[str]] = defaultdict(list)
    recommendation_confidence: Dict[tuple, Optional[str]] = {}
    recommendation_action: Dict[tuple, Optional[str]] = {}

    for app_id in apps_with_outcomes:
        try:
            autopsy = await build_hiring_autopsy(session, app_id, organization_id)
        except AutopsyAppNotFoundError:
            continue

        app_job_id = getattr(autopsy, "job_id", None)
        app_outcomes = getattr(autopsy, "post_hire_outcomes", []) or []

        # Deduplicate findings within the same application
        seen_findings_in_app: Set[tuple] = set()
        for f in getattr(autopsy, "findings", []) or []:
            key = (f.category, f.affected_capability, f.finding_text)
            if key not in seen_findings_in_app:
                seen_findings_in_app.add(key)
                finding_counts[key] += 1
                finding_apps[key].append(app_id)

            if app_job_id:
                finding_jobs[key].add(app_job_id)

            # Match outcome IDs for this capability
            for o in app_outcomes:
                if (
                    getattr(o, "capability_name", "").strip().lower()
                    == getattr(f, "affected_capability", "").strip().lower()
                ):
                    finding_outcomes[key].add(o.id)

        # Deduplicate recommendations within the same application
        seen_sugs_in_app: Set[tuple] = set()
        for s in getattr(autopsy, "ai_improvement_suggestions", []) or []:
            key = (s.affected_capability, s.suggested_improvement)
            if key not in seen_sugs_in_app:
                seen_sugs_in_app.add(key)
                recommendation_counts[key] += 1
                recommendation_apps[key].append(app_id)

            recommendation_confidence[key] = getattr(s, "confidence_strength", None)
            recommendation_action[key] = getattr(s, "action_type", None)

            for rec_str in getattr(s, "supporting_records", []) or []:
                if rec_str not in recommendation_supporting[key]:
                    recommendation_supporting[key].append(rec_str)

    findings: List[AggregatedFinding] = []
    for (category, capability, summary), count in finding_counts.items():
        key = (category, capability, summary)
        findings.append(
            AggregatedFinding(
                capability_name=capability,
                category=category,
                summary=summary,
                count=count,
                application_ids=finding_apps[key],
                job_ids=list(finding_jobs[key]),
                outcome_ids=list(finding_outcomes[key]),
                evidence_ids=list(finding_evidence[key]),
            )
        )

    recommendations: List[AggregatedRecommendation] = []
    for (capability, suggestion_text), count in recommendation_counts.items():
        key = (capability, suggestion_text)
        recommendations.append(
            AggregatedRecommendation(
                capability_name=capability,
                suggestion_text=suggestion_text,
                count=count,
                application_ids=recommendation_apps[key],
                supporting_records=recommendation_supporting[key],
                confidence_strength=recommendation_confidence.get(key),
                action_type=recommendation_action.get(key),
            )
        )

    findings.sort(key=lambda f: f.count, reverse=True)
    recommendations.sort(key=lambda r: r.count, reverse=True)

    message = None
    if applications_with_outcomes > 0 and not findings and not recommendations:
        message = "Post-hire outcomes evaluated, but no process gaps or improvement suggestions were detected."

    return HiringIntelligenceResponse(
        total_applications=total_applications,
        applications_with_outcomes=applications_with_outcomes,
        applications_without_outcomes=applications_without_outcomes,
        total_outcome_records=total_outcome_records,
        findings=findings,
        recommendations=recommendations,
        limitations=DEFAULT_LIMITATIONS,
        message=message,
    )
