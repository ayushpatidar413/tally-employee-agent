import time
from graph.analytics_engine import wrap_execute, wrap_chart, wrap_answer
from graph.analytics_extra import wrap_extra

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
    build_dynamic_chart,
    universal_query_planner,
    generate_dynamic_answer,
)


# ============================================================
# NODE TIMING WRAPPER
# ============================================================

def timed_node(name, node_function):
    def wrapper(state):
        start = time.perf_counter()

        result = node_function(state)

        elapsed = time.perf_counter() - start

        print(
            f"[TIMING] {name:<22} : {elapsed:.2f} sec"
        )

        return result

    return wrapper


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
        timed_node(
            "detect_intent",
            detect_dynamic_intent,
        ),
    )

    workflow.add_node(
        "select_dataset",
        timed_node(
            "select_dataset",
            select_dynamic_dataset,
        ),
    )

    workflow.add_node(
        "load_data",
        timed_node(
            "load_data",
            load_dynamic_data,
        ),
    )

    workflow.add_node(
        "execute_query",
        timed_node(
            "execute_query",
            wrap_extra(wrap_execute(execute_dynamic_query)),
        ),
    )

    workflow.add_node(
        "build_chart",
        timed_node(
            "build_chart",
            wrap_chart(build_dynamic_chart),
        ),
    )

    workflow.add_node(
        "generate_answer",
        timed_node(
            "generate_answer",
            wrap_answer(generate_dynamic_answer),
        ),
    )

    workflow.add_node(
        "universal_query_planner",
        timed_node(
            "universal_query_planner",
            universal_query_planner,
        ),
    )

    # --------------------------------------------------------
    # EDGES
    # --------------------------------------------------------

    workflow.add_edge(
        START,
        "detect_intent",
    )

    workflow.add_edge("detect_intent", "select_dataset")
    workflow.add_edge(
        "select_dataset",
        "universal_query_planner",
    )
    workflow.add_edge(
        "universal_query_planner",
        "load_data",
    )
    workflow.add_edge(
        "load_data",
        "execute_query",
    )

    workflow.add_edge(
        "execute_query",
        "build_chart",
    )

    workflow.add_edge(
        "build_chart",
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

dynamic_graph = build_dynamic_workflow()

dynamic_agent = dynamic_graph