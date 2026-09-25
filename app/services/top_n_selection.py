import logging
from typing import Any, Optional
from uuid import UUID

from app.schemas.screening import (
    CandidateScreeningProfile,
    JobTopNResult,
    TopNCandidateItem,
)

logger = logging.getLogger(__name__)


def candidate_comparison_key(profile: CandidateScreeningProfile) -> tuple:
    """
    Computes a purely deterministic comparison key from structured candidate screening dimensions.
    Zero opaque AI scores. Completely reproducible and auditable.

    Precedence order:
    1. Hard requirements met (required capability count)
    2. Hard requirements demonstrated via code/project artifacts
    3. Preferred requirements met (preferred capability count)
    4. Total demonstrated / verified evidence count
    5. Total strong evidence count
    6. Resume claim evidence count
    7. Fewer unknowns / insufficient capabilities (negative count)
    8. Application timestamp (earlier applicants win tie-breaks)
    """
    hard_met = profile.hard_requirement_coverage.get("met", 0)

    hard_demonstrated = sum(
        1
        for r in profile.capability_results
        if r.is_required and r.status == "MET" and r.provenance in {"DEMONSTRATED", "VERIFIED"}
    )

    pref_met = sum(
        1
        for r in profile.capability_results
        if not r.is_required and r.status == "MET"
    )

    demonstrated_ev = profile.evidence_provenance.get(
        "DEMONSTRATED", 0
    ) + profile.evidence_provenance.get("VERIFIED", 0)

    strong_ev = profile.evidence_strength.get("STRONG", 0)
    claim_ev = profile.evidence_provenance.get("CLAIM", 0)
    unknowns = len(profile.unknown_capabilities) + len(profile.insufficient_capabilities)

    # Invert timestamp for descending sort: earlier datetime -> larger number
    applied_ts = -profile.applied_at.timestamp() if profile.applied_at else 0.0

    return (
        hard_met,
        hard_demonstrated,
        pref_met,
        demonstrated_ev,
        strong_ev,
        claim_ev,
        -unknowns,
        applied_ts,
    )


def compare_candidates(a: CandidateScreeningProfile, b: CandidateScreeningProfile) -> int:
    """
    Returns:
       > 0 if candidate A is strictly stronger than candidate B
       < 0 if candidate B is strictly stronger than candidate A
       = 0 if identical ranking dimensions
    """
    key_a = candidate_comparison_key(a)
    key_b = candidate_comparison_key(b)
    if key_a > key_b:
        return 1
    elif key_a < key_b:
        return -1
    return 0


def evaluate_shortlist_eligibility(profile: CandidateScreeningProfile) -> tuple[bool, str]:
    """
    Determines whether a candidate satisfies the deterministic screening eligibility policy
    required to enter the recommended Top-N competitive shortlist.

    Rules:
    1. A candidate with screening_status == 'NOT_ELIGIBLE' is NEVER shortlist-eligible.
    2. Zero-evidence candidates or candidates with no supported capabilities are NEVER shortlist-eligible.
    3. If the job has hard/critical requirements (total > 0):
       - Candidate MUST satisfy ALL required capabilities (is_hard_satisfied is True, i.e. met == total).
       - Meeting only a partial subset of required capabilities does NOT qualify a candidate for Top-N.
    4. If the job has no required capabilities (total == 0):
       - Candidate must have at least one supported preferred capability.
    5. UNKNOWN != NO SKILL and INSUFFICIENT != NO SKILL:
       - Unmet capabilities do not declare the candidate 'has no skill', but indicate that
         critical job requirements lack proof, making the candidate ineligible for an immediate
         shortlist recommendation without prior interview/practical verification.
    """
    if profile.screening_status == "NOT_ELIGIBLE":
        return False, "Candidate lacks essential capability signals required for this role."

    total_met = sum(1 for r in profile.capability_results if r.status == "MET")
    hard_total = profile.hard_requirement_coverage.get("total", 0)
    hard_met = profile.hard_requirement_coverage.get("met", 0)
    if "is_satisfied" in profile.hard_requirement_coverage:
        is_hard_satisfied = bool(profile.hard_requirement_coverage["is_satisfied"])
    else:
        is_hard_satisfied = (hard_total > 0 and hard_met >= hard_total)

    # Hard/Critical requirements check: MUST be satisfied in full
    if hard_total > 0:
        if not is_hard_satisfied or hard_met < hard_total:
            missing_required = [
                r.capability_name
                for r in profile.capability_results
                if r.is_required and r.status != "MET"
            ]
            missing_desc = f": {', '.join(missing_required)}" if missing_required else ""
            return (
                False,
                f"Missing required capabilities: {hard_met} of {hard_total} required capabilities satisfied{missing_desc}.",
            )
    else:
        # No explicit hard requirements: must meet at least one capability
        if (
            total_met == 0
            and not profile.relevant_project_evidence
            and not profile.relevant_resume_evidence
            and not profile.evidence_provenance
        ):
            return False, "Candidate has zero supported capabilities identified from resume or source artifacts."

    # Grounded evidence check: candidate must have evidence supporting claims
    has_evidence = bool(
        profile.relevant_project_evidence
        or profile.relevant_resume_evidence
        or profile.evidence_provenance
        or profile.evidence_strength
        or total_met > 0
        or hard_met > 0
    )
    if not has_evidence:
        return False, "No grounded evidence found in resume claims or public project artifacts."

    return (
        True,
        f"Eligible: Meets all {hard_total} required capabilities with supported evidence."
        if hard_total > 0
        else f"Eligible: {total_met} capabilities supported with evidence.",
    )


class DynamicTopNSelector:
    """
    Maintains a continuous, competitive Top-N candidate pool under HR-configured maximum capacity.
    Processes all candidates without early stopping.
    Top-N is a MAXIMUM CEILING, NOT A MINIMUM QUOTA:
    - Only candidates satisfying evaluate_shortlist_eligibility can enter Top-N.
    - If fewer eligible candidates exist than shortlist_size, empty positions remain empty.
    - When a stronger eligible candidate arrives, they displace the current lowest cutoff candidate.
    """

    def __init__(self, shortlist_size: int, job_id: UUID, job_title: str):
        self.shortlist_size: int = max(1, shortlist_size)
        self.job_id: UUID = job_id
        self.job_title: str = job_title
        self.candidates: list[CandidateScreeningProfile] = []
        self.selection_log: list[str] = []

    def partition_candidates(
        self,
    ) -> tuple[list[CandidateScreeningProfile], list[tuple[CandidateScreeningProfile, str]]]:
        """
        Partitions candidate pool into:
        1. shortlist-eligible candidates (sorted by deterministic comparison key descending)
        2. ineligible candidates with specific failure reasons
        """
        eligible: list[CandidateScreeningProfile] = []
        ineligible: list[tuple[CandidateScreeningProfile, str]] = []

        for cand in self.candidates:
            is_elig, reason = evaluate_shortlist_eligibility(cand)
            if is_elig:
                eligible.append(cand)
            else:
                ineligible.append((cand, reason))

        eligible.sort(key=candidate_comparison_key, reverse=True)
        return eligible, ineligible

    def get_top_n(self) -> list[CandidateScreeningProfile]:
        """
        Returns up to shortlist_size candidates from the ELIGIBLE population only.
        If fewer eligible candidates exist, empty slots remain empty!
        """
        eligible, _ = self.partition_candidates()
        return eligible[: self.shortlist_size]

    def get_cutoff(self) -> Optional[CandidateScreeningProfile]:
        """
        Returns the cutoff threshold (the lowest ranked candidate inside Top-N)
        ONLY IF the Top-N pool is at full capacity.
        If empty positions remain, there is no cutoff threshold yet.
        """
        top_n = self.get_top_n()
        if len(top_n) >= self.shortlist_size:
            return top_n[-1]
        return None

    def get_excluded(self) -> list[tuple[CandidateScreeningProfile, str]]:
        """
        Returns all excluded candidates with structured reasons:
        - Eligible candidates who missed the cutoff due to shortlist capacity limits
        - Ineligible candidates who failed the eligibility gate
        """
        eligible, ineligible = self.partition_candidates()
        cutoff_excluded = [
            (
                cand,
                f"Rank {self.shortlist_size + idx + 1}: Excluded due to shortlist capacity limit (Top-{self.shortlist_size}).",
            )
            for idx, cand in enumerate(eligible[self.shortlist_size :])
        ]
        return cutoff_excluded + ineligible

    def add_candidate(self, profile: CandidateScreeningProfile) -> dict[str, Any]:
        """
        Adds candidate to candidate population and recalculates dynamic Top-N.
        Logs whether candidate entered Top-N, displaced previous cutoff, or was excluded.
        """
        prev_top_n_ids = {c.application_id for c in self.get_top_n()}
        prev_cutoff = self.get_cutoff()
        had_reached_capacity = len(self.get_top_n()) >= self.shortlist_size

        self.candidates.append(profile)

        # Check eligibility
        is_elig, elig_reason = evaluate_shortlist_eligibility(profile)

        action_event: dict[str, Any] = {
            "application_id": str(profile.application_id),
            "candidate_name": profile.candidate_name,
            "shortlist_size": self.shortlist_size,
            "is_eligible": is_elig,
        }

        if not is_elig:
            action_event["action"] = "EXCLUDED"
            action_event["reason"] = elig_reason
            action_event["is_eligible"] = False
            msg = f"Candidate {profile.candidate_name} is not shortlist-eligible: {elig_reason}"
            self.selection_log.append(msg)
            action_event["message"] = msg
            return action_event

        # Re-partition eligible candidates
        eligible, _ = self.partition_candidates()
        curr_top_n = self.get_top_n()
        curr_top_n_ids = {c.application_id for c in curr_top_n}

        rank = eligible.index(profile) + 1
        profile.rank = rank
        action_event["rank"] = rank

        if profile.application_id in curr_top_n_ids:
            if had_reached_capacity and prev_cutoff and prev_cutoff.application_id not in curr_top_n_ids:
                msg = (
                    f"Candidate {profile.candidate_name} entered Top-{self.shortlist_size} at rank {rank}, "
                    f"displacing previous cutoff {prev_cutoff.candidate_name}."
                )
                action_event["action"] = "DISPLACED_CUTOFF"
                action_event["displaced_candidate"] = prev_cutoff.candidate_name
            else:
                msg = f"Candidate {profile.candidate_name} entered Top-{self.shortlist_size} at rank {rank}."
                action_event["action"] = "ENTERED_TOP_N"
        else:
            curr_cutoff = self.get_cutoff()
            cutoff_name = curr_cutoff.candidate_name if curr_cutoff else "threshold"
            msg = (
                f"Candidate {profile.candidate_name} placed at rank {rank}, "
                f"remaining outside Top-{self.shortlist_size} (below cutoff {cutoff_name})."
            )
            action_event["action"] = "EXCLUDED"
            action_event["cutoff_candidate"] = cutoff_name

        self.selection_log.append(msg)
        action_event["message"] = msg
        return action_event

    def to_job_top_n_result(self) -> JobTopNResult:
        """
        Builds the structured HR-facing Top-N result explaining ordering and cutoff reasons.
        Top-N is bounded by shortlist_size AND qualified eligibility.
        Empty positions remain empty if insufficient eligible candidates exist.
        """
        top_n_items: list[TopNCandidateItem] = []
        excluded_items: list[TopNCandidateItem] = []

        top_n_profiles = self.get_top_n()
        excluded_pairs = self.get_excluded()
        cutoff_profile = self.get_cutoff()

        for idx, cand in enumerate(top_n_profiles):
            rank = idx + 1
            cand.rank = rank
            cand.shortlist_status = "SHORTLISTED"

            hard_cov = cand.hard_requirement_coverage
            hard_met = hard_cov.get("met", 0)
            total_hard = hard_cov.get("total", 0)
            pref_met = sum(1 for r in cand.capability_results if not r.is_required and r.status == "MET")
            demo_count = cand.evidence_provenance.get("DEMONSTRATED", 0) + cand.evidence_provenance.get("VERIFIED", 0)
            strong_count = cand.evidence_strength.get("STRONG", 0)
            unknown_count = len(cand.unknown_capabilities) + len(cand.insufficient_capabilities)

            reason = (
                f"Rank {rank} in Top-{self.shortlist_size}: {hard_met}/{total_hard} hard requirements met, "
                f"{demo_count} demonstrated artifacts, {pref_met} preferred skills."
            )

            top_n_items.append(
                TopNCandidateItem(
                    rank=rank,
                    application_id=cand.application_id,
                    candidate_id=cand.candidate_id,
                    candidate_name=cand.candidate_name,
                    candidate_email=cand.candidate_email,
                    shortlist_status="SHORTLISTED",
                    hard_requirements_met=hard_met,
                    total_hard_requirements=total_hard,
                    preferred_requirements_met=pref_met,
                    demonstrated_evidence_count=demo_count,
                    strong_evidence_count=strong_count,
                    unknown_count=unknown_count,
                    summary_explanation=cand.summary_explanation,
                    selection_reason=reason,
                )
            )

        cutoff_item: Optional[TopNCandidateItem] = None
        if cutoff_profile and len(top_n_items) >= self.shortlist_size:
            cutoff_item = top_n_items[-1]

        for idx, (cand, reason) in enumerate(excluded_pairs):
            rank = len(top_n_profiles) + idx + 1
            cand.rank = rank
            cand.shortlist_status = "NOT_SHORTLISTED"

            hard_cov = cand.hard_requirement_coverage
            hard_met = hard_cov.get("met", 0)
            total_hard = hard_cov.get("total", 0)
            pref_met = sum(1 for r in cand.capability_results if not r.is_required and r.status == "MET")
            demo_count = cand.evidence_provenance.get("DEMONSTRATED", 0) + cand.evidence_provenance.get("VERIFIED", 0)
            strong_count = cand.evidence_strength.get("STRONG", 0)
            unknown_count = len(cand.unknown_capabilities) + len(cand.insufficient_capabilities)

            excluded_items.append(
                TopNCandidateItem(
                    rank=rank,
                    application_id=cand.application_id,
                    candidate_id=cand.candidate_id,
                    candidate_name=cand.candidate_name,
                    candidate_email=cand.candidate_email,
                    shortlist_status="NOT_SHORTLISTED",
                    hard_requirements_met=hard_met,
                    total_hard_requirements=total_hard,
                    preferred_requirements_met=pref_met,
                    demonstrated_evidence_count=demo_count,
                    strong_evidence_count=strong_count,
                    unknown_count=unknown_count,
                    summary_explanation=cand.summary_explanation,
                    selection_reason=f"Not Shortlisted: {reason}",
                )
            )

        return JobTopNResult(
            job_id=self.job_id,
            job_title=self.job_title,
            shortlist_size=self.shortlist_size,
            total_candidates_evaluated=len(self.candidates),
            top_n_candidates=top_n_items,
            cutoff_candidate=cutoff_item,
            excluded_candidates=excluded_items,
            selection_log=self.selection_log,
        )
