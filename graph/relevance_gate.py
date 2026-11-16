"""Relevance gate: if nothing in the plan is resolved, return DATA_NOT_AVAILABLE."""

NO_DATA_MESSAGE = (
    "Data related to this question is not available in the uploaded dataset. "
    "You can ask about sales, customers, products, GST and similar topics."
)


def is_plan_resolved(plan):
    plan = plan or {}
    metrics = plan.get("metrics") or plan.get("measures") or []
    filters = plan.get("filters") or []
    group_by = plan.get("group_by") or plan.get("dimensions") or []
    return bool(metrics or filters or group_by)


def planner_gate_node(state):
    plan = state.get("query_plan") or {}
    if not is_plan_resolved(plan):
        return {
            **state,
            "status": "DATA_NOT_AVAILABLE",
            "message": NO_DATA_MESSAGE,
            "rows": [],
            "chart": None,
        }
    return state


def route_after_gate(state):
    return "end" if state.get("status") == "DATA_NOT_AVAILABLE" else "executor"