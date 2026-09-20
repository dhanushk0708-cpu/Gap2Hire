from typing import Any, TypedDict


class InterviewState(TypedDict, total=False):
    session_id: str
    application_id: str
    job_id: str
    organization_id: str

    # Round information
    current_round_id: str | None
    current_round_type: str | None
    current_round_name: str | None
    round_sequence: int
    rounds_list: list[dict[str, Any]]

    # Capability information
    current_capability_id: str | None
    current_capability_name: str | None
    capabilities_list: list[dict[str, Any]]

    # Question & Template information
    current_template_id: str | None
    current_question_intent: str | None
    current_question_text: str | None
    current_question_id: str | None
    current_framed_question: str | None

    # Dialogue & Traceability History
    questions_asked: list[dict[str, Any]]
    candidate_answers: list[dict[str, Any]]
    evidence_observations: list[dict[str, Any]]
    claims_to_verify: list[dict[str, Any]]
    unknowns_remaining: list[dict[str, Any]]

    # Follow-up State
    follow_up_count: int
    max_followups: int

    # Latest Input & Analysis
    latest_candidate_answer: str | None
    answer_analysis: dict[str, Any] | None

    # Orchestration Control
    next_action: str | None
    round_status: str
    interview_status: str

    # Post Analysis
    rounds_summary: list[dict[str, Any]]
