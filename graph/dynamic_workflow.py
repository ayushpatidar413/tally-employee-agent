from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from graph.dynamic_nodes import (
    DynamicAgentState,
    detect_dynamic_intent,
    select_dynamic_dataset,
    load_dynamic_data,
    execute_dynamic_query,
    generate_dynamic_answer,
)


# ============================================================
# BUILD WORKFLOW
# ============================================================

def build_dynamic_workflow():

    workflow = StateGraph(
        DynamicAgentState
    )

    # --------------------------------------------------------
    # NODES
    # --------------------------------------------------------

    workflow.add_node(
        "detect_intent",
        detect_dynamic_intent,
    )

    workflow.add_node(
        "select_dataset",
        select_dynamic_dataset,
    )

    workflow.add_node(
        "load_data",
        load_dynamic_data,
    )

    workflow.add_node(
        "execute_query",
        execute_dynamic_query,
    )

    workflow.add_node(
        "generate_answer",
        generate_dynamic_answer,
    )

    # --------------------------------------------------------
    # EDGES
    # --------------------------------------------------------

    workflow.add_edge(
        START,
        "detect_intent",
    )

    workflow.add_edge(
        "detect_intent",
        "select_dataset",
    )

    workflow.add_edge(
        "select_dataset",
        "load_data",
    )

    workflow.add_edge(
        "load_data",
        "execute_query",
    )

    workflow.add_edge(
        "execute_query",
        "generate_answer",
    )

    workflow.add_edge(
        "generate_answer",
        END,
    )

    # --------------------------------------------------------
    # COMPILE
    # --------------------------------------------------------

    return workflow.compile()


# ============================================================
# GLOBAL AGENT
# ============================================================

dynamic_graph = (
    build_dynamic_workflow()
)

dynamic_agent = dynamic_graph