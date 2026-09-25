from typing import Any, Optional, TypedDict


class EvidenceResearchState(TypedDict, total=False):
    """
    Execution state for the LangGraph Evidence Research Agent workflow.
    """
    # Identifiers & tenant boundaries
    research_session_id: str
    application_id: str
    organization_id: str
    job_id: str
    job_title: str
    job_description: str

    # Capabilities & dynamic investigation states
    capabilities: list[dict[str, Any]]
    capability_states: dict[str, str]  # capability_id -> state (UNKNOWN, SUFFICIENT, etc.)
    unresolved_capability_ids: list[str]

    # Available & inspected candidate sources
    candidate_sources: list[dict[str, Any]]
    inspected_source_ids: list[str]

    # Current step pointers
    current_capability_id: Optional[str]
    current_source_id: Optional[str]
    current_decision: Optional[dict[str, Any]]

    # Observations & extraction results
    last_observation: Optional[dict[str, Any]]
    last_extraction: Optional[dict[str, Any]]

    # Execution controls & audit log
    iteration_count: int
    max_iterations: int
    actions_taken: list[dict[str, Any]]
    research_findings: list[dict[str, Any]]
    status: str  # "RUNNING", "COMPLETED", "FAILED"
    stop_reason: Optional[str]
    error: Optional[str]
