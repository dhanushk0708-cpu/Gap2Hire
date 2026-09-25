from langgraph.graph import END, START, StateGraph

from app.agents.evidence_research.nodes import (
    act_node,
    decide_route,
    identify_unresolved_node,
    load_context_node,
    observe_node,
    should_act,
    should_start_research,
    think_node,
    update_state_node,
)
from app.agents.evidence_research.state import EvidenceResearchState


def create_evidence_research_graph() -> StateGraph:
    """
    Constructs the LangGraph Evidence Research workflow graph:
    START -> LOAD_CONTEXT -> IDENTIFY_UNRESOLVED -> (THINK <-> ACT -> OBSERVE -> UPDATE_STATE) -> END
    """
    workflow = StateGraph(EvidenceResearchState)

    # Register Nodes
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("identify_unresolved", identify_unresolved_node)
    workflow.add_node("think", think_node)
    workflow.add_node("act", act_node)
    workflow.add_node("observe", observe_node)
    workflow.add_node("update_state", update_state_node)

    # Entry edges
    workflow.add_edge(START, "load_context")
    workflow.add_edge("load_context", "identify_unresolved")

    # Conditional edge from identify_unresolved to think or END
    workflow.add_conditional_edges(
        "identify_unresolved",
        should_start_research,
        {
            "continue": "think",
            "complete": END,
        },
    )

    # Conditional edge from think to act or END
    workflow.add_conditional_edges(
        "think",
        should_act,
        {
            "act": "act",
            "complete": END,
        },
    )

    # Sequential edges for action execution and observation
    workflow.add_edge("act", "observe")
    workflow.add_edge("observe", "update_state")

    # Dynamic loop condition: continue research (think) or finalize (END)
    workflow.add_conditional_edges(
        "update_state",
        decide_route,
        {
            "think": "think",
            "complete": END,
        },
    )

    return workflow


# Compiled singleton for efficient execution
evidence_research_app = create_evidence_research_graph().compile()
