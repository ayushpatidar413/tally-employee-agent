from langgraph.graph import StateGraph, START, END

from graph.supervisor_state import SupervisorState

from graph.supervisor_nodes import (
    supervisor_router_node,
    supervisor_hr_node,
    supervisor_dynamic_node,
    supervisor_research_node,
    validator_node,
    supervisor_final_node,
)


# ============================================================
# ROUTE AFTER SUPERVISOR
# ============================================================

def route_after_supervisor(
    state: dict,
) -> str:

    route = state.get(
        "route",
        "research",
    )

    if route == "hr":
        return "hr_agent"

    if route == "dynamic":
        return "dynamic_agent"

    return "research_agent"


# ============================================================
# BUILD SUPERVISOR GRAPH
# ============================================================

def build_supervisor_graph():

    graph = StateGraph(
        SupervisorState
    )

    # --------------------------------------------------------
    # Nodes
    # --------------------------------------------------------

    graph.add_node(
        "supervisor",
        supervisor_router_node,
    )

    graph.add_node(
        "hr_agent",
        supervisor_hr_node,
    )

    graph.add_node(
        "dynamic_agent",
        supervisor_dynamic_node,
    )

    graph.add_node(
        "research_agent",
        supervisor_research_node,
    )

    graph.add_node(
        "validator",
        validator_node,
    )

    graph.add_node(
        "final",
        supervisor_final_node,
    )

    # --------------------------------------------------------
    # Start
    # --------------------------------------------------------

    graph.add_edge(
        START,
        "supervisor",
    )

    # --------------------------------------------------------
    # Supervisor → Agent
    # --------------------------------------------------------

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "hr_agent": "hr_agent",
            "dynamic_agent": "dynamic_agent",
            "research_agent": "research_agent",
        },
    )

    # --------------------------------------------------------
    # Agents → Validator
    # --------------------------------------------------------

    graph.add_edge(
        "hr_agent",
        "validator",
    )

    graph.add_edge(
        "dynamic_agent",
        "validator",
    )

    graph.add_edge(
        "research_agent",
        "validator",
    )

    # --------------------------------------------------------
    # Validator → Final
    # --------------------------------------------------------

    graph.add_edge(
        "validator",
        "final",
    )

    # --------------------------------------------------------
    # Final → END
    # --------------------------------------------------------

    graph.add_edge(
        "final",
        END,
    )

    return graph.compile()


# ============================================================
# SUPERVISOR GRAPH INSTANCE
# ============================================================

supervisor_graph = build_supervisor_graph()