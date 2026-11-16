# import time
# from graph.analytics_engine import wrap_execute, wrap_chart, wrap_answer
# from graph.analytics_extra import run as run_analytics_extra
# from graph.guards import relevance_guard, report_shape, answer_passthrough
# from services.query_spellcheck import correct_query_typos
# from langgraph.graph import StateGraph, START, END

# from graph.dynamic_nodes import (
#     DynamicAgentState,
#     detect_dynamic_intent,
#     select_dynamic_dataset,
#     load_dynamic_data,
#     execute_dynamic_query,
#     build_dynamic_chart,
#     universal_query_planner,
#     generate_dynamic_answer,
# )


# # ============================================================
# # NODE TIMING WRAPPER
# # ============================================================
# def timed_node(name, node_function):
#     def wrapper(state):
#         start = time.perf_counter()
#         result = node_function(state)
#         elapsed = time.perf_counter() - start
#         print(f"[TIMING] {name:<22} : {elapsed:.2f} sec")
#         return result
#     return wrapper


# def correct_spelling_node(state):
#     """
#     Preserve the exact user query.

#     Do not run an English-only spellchecker over Hinglish words,
#     customer names, product names, or other entity values.
#     Query interpretation is handled by the semantic planner.
#     """
#     raw_question = (
#         state.get("raw_question")
#         or state.get("original_question")
#         or state.get("question")
#         or ""
#     )
#     raw_question = str(raw_question)

#     print(
#         f"[QUERY-INPUT] original query preserved: "
#         f"{raw_question!r}"
#     )

#     return {
#         **state,
#         "raw_question": raw_question,
#         "original_question": raw_question,
#         "question": raw_question,
#     }


# def debug_plan(node_function):
#     def wrapper(state):
#         result = node_function(state)
#         result = result or {}
#         plan = result.get("query_plan") or {}
#         print("[DEBUG-PLAN] question:", result.get("raw_question") or result.get("original_question") or state.get("question"))
#         print("[DEBUG-PLAN] status  :", plan.get("status"), "| reason:", plan.get("reason"))
#         print("[DEBUG-PLAN] metric  :", plan.get("aggregate_column"), "| group_by:", plan.get("group_by"), "| filters:", plan.get("filters"))
#         return result
#     return wrapper


# def route_after_planner(state):
#     """Only definitive no-data plans bypass execution.

#     FALLBACK means the planner could not express the query in the
#     universal plan; it must still reach the deterministic engines.
#     """
#     plan = state.get("query_plan") or {}
#     status = str(plan.get("status") or "").strip().upper()

#     if status == "DATA_NOT_AVAILABLE":
#         return "generate_answer"

#     return "load_data"


# def _has_final_result(state):
#     """Return True only when the primary executor produced a usable result."""
#     if not isinstance(state, dict):
#         return False
#     result = state.get("result")
#     if not isinstance(result, dict):
#         return False
#     status = str(result.get("status") or "").strip().upper()
#     if status == "DATA_NOT_AVAILABLE":
#         return True  # authoritative: do not let another engine invent a substitute
#     if result.get("engine_answer"):
#         return True
#     if any(k in result for k in ("value", "total_value", "rows", "table", "chart_spec")):
#         return True
#     return False


# def execute_query_pipeline(state):
#     """Single execution priority: universal executor -> analytics engine -> extra fallback.

#     Each fallback runs only when the previous stage did not produce a usable result.
#     The original query and state are retained for every stage.
#     """
#     primary = execute_dynamic_query(state)
#     if _has_final_result(primary):
#         return primary

#     # Existing analytics_engine remains a fallback for temporal and
#     # specialized deterministic operations not handled by the universal plan.
#     secondary = wrap_execute(execute_dynamic_query)(state)
#     if _has_final_result(secondary):
#         return secondary

#     # analytics_extra is the last-resort compatibility handler, not a planner
#     # that can pre-empt the universal planner.
#     try:
#         extra = run_analytics_extra(state)
#     except Exception as exc:
#         print("[ANALYTICS-EXTRA-FALLBACK]", type(exc).__name__, exc)
#         extra = None

#     if isinstance(extra, dict) and isinstance(extra.get("result"), dict):
#         if extra["result"].get("status") != "DATA_NOT_AVAILABLE":
#             return {
#                 **state,
#                 "result": extra["result"],
#                 "answer": extra.get("answer") or extra["result"].get("engine_answer"),
#                 "error": None,
#             }

#     return secondary if isinstance(secondary, dict) else primary


# def build_dynamic_workflow():
#     workflow = StateGraph(DynamicAgentState)

#     workflow.add_node("correct_spelling", timed_node("correct_spelling", correct_spelling_node))
#     workflow.add_node("detect_intent", timed_node("detect_intent", detect_dynamic_intent))
#     workflow.add_node("select_dataset", timed_node("select_dataset", select_dynamic_dataset))
#     workflow.add_node("load_data", timed_node("load_data", load_dynamic_data))
#     workflow.add_node(
#         "execute_query",
#         timed_node("execute_query", execute_query_pipeline),
#     )
#     workflow.add_node(
#         "build_chart",
#         timed_node("build_chart", report_shape(wrap_chart(build_dynamic_chart))),
#     )
#     workflow.add_node(
#         "generate_answer",
#         timed_node("generate_answer", answer_passthrough(wrap_answer(generate_dynamic_answer))),
#     )
#     workflow.add_node(
#         "universal_query_planner",
#         timed_node(
#             "universal_query_planner",
#             relevance_guard(debug_plan(universal_query_planner)),
#         ),
#     )

#     workflow.add_edge(START, "correct_spelling")
#     workflow.add_edge("correct_spelling", "detect_intent")
#     workflow.add_edge("detect_intent", "select_dataset")
#     workflow.add_edge("select_dataset", "universal_query_planner")
#     workflow.add_conditional_edges(
#         "universal_query_planner",
#         route_after_planner,
#         {"generate_answer": "generate_answer", "load_data": "load_data"},
#     )
#     workflow.add_edge("load_data", "execute_query")
#     workflow.add_edge("execute_query", "build_chart")
#     workflow.add_edge("build_chart", "generate_answer")
#     workflow.add_edge("generate_answer", END)
#     return workflow.compile()


# # ============================================================
# # GLOBAL AGENT
# # ============================================================
# dynamic_graph = build_dynamic_workflow()
# dynamic_agent = dynamic_graph
import time
from graph.analytics_engine import wrap_execute, wrap_chart, wrap_answer
from graph.analytics_extra import wrap_extra, wrap_planner
from graph.guards import relevance_guard, report_shape, answer_passthrough
from services.query_spellcheck import correct_query_typos
from langgraph.graph import StateGraph, START, END

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
        print(f"[TIMING] {name:<22} : {elapsed:.2f} sec")
        return result
    return wrapper


def correct_spelling_node(state):
    """
    Preserve the exact user query.

    Do not run an English-only spellchecker over Hinglish words,
    customer names, product names, or other entity values.
    Query interpretation is handled by the semantic planner.
    """
    raw_question = (
        state.get("raw_question")
        or state.get("original_question")
        or state.get("question")
        or ""
    )
    raw_question = str(raw_question)

    print(
        f"[QUERY-INPUT] original query preserved: "
        f"{raw_question!r}"
    )

    return {
        **state,
        "raw_question": raw_question,
        "original_question": raw_question,
        "question": raw_question,
    }


def debug_plan(node_function):
    def wrapper(state):
        result = node_function(state)
        result = result or {}
        plan = result.get("query_plan") or {}
        print("[DEBUG-PLAN] question:", result.get("raw_question") or result.get("original_question") or state.get("question"))
        print("[DEBUG-PLAN] status  :", plan.get("status"), "| reason:", plan.get("reason"))
        print("[DEBUG-PLAN] metric  :", plan.get("aggregate_column"), "| group_by:", plan.get("group_by"), "| filters:", plan.get("filters"))
        return result
    return wrapper


def route_after_planner(state):
    """Only definitive no-data plans bypass dataset execution."""
    plan = state.get("query_plan") or {}
    status = str(plan.get("status") or "").strip().upper()

    if status == "DATA_NOT_AVAILABLE":
        return "generate_answer"

    # FALLBACK and other unresolved plans must reach
    # the existing deterministic execution engines.
    return "load_data"


def build_dynamic_workflow():
    workflow = StateGraph(DynamicAgentState)

    workflow.add_node("correct_spelling", timed_node("correct_spelling", correct_spelling_node))
    workflow.add_node("detect_intent", timed_node("detect_intent", detect_dynamic_intent))
    workflow.add_node("select_dataset", timed_node("select_dataset", select_dynamic_dataset))
    workflow.add_node("load_data", timed_node("load_data", load_dynamic_data))
    workflow.add_node(
        "execute_query",
        timed_node("execute_query", wrap_extra(wrap_execute(execute_dynamic_query))),
    )
    workflow.add_node(
        "build_chart",
        timed_node("build_chart", report_shape(wrap_chart(build_dynamic_chart))),
    )
    workflow.add_node(
        "generate_answer",
        timed_node("generate_answer", answer_passthrough(wrap_answer(generate_dynamic_answer))),
    )
    workflow.add_node(
        "universal_query_planner",
        timed_node(
            "universal_query_planner",
            relevance_guard(debug_plan(wrap_planner(universal_query_planner))),
        ),
    )

    workflow.add_edge(START, "correct_spelling")
    workflow.add_edge("correct_spelling", "detect_intent")
    workflow.add_edge("detect_intent", "select_dataset")
    workflow.add_edge("select_dataset", "universal_query_planner")
    workflow.add_conditional_edges(
        "universal_query_planner",
        route_after_planner,
        {"generate_answer": "generate_answer", "load_data": "load_data"},
    )
    workflow.add_edge("load_data", "execute_query")
    workflow.add_edge("execute_query", "build_chart")
    workflow.add_edge("build_chart", "generate_answer")
    workflow.add_edge("generate_answer", END)
    return workflow.compile()


# ============================================================
# GLOBAL AGENT
# ============================================================
dynamic_graph = build_dynamic_workflow()
dynamic_agent = dynamic_graph
