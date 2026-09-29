from typing import Any

from graph.workflow import hr_graph
from graph.dynamic_workflow import dynamic_graph

from agents.research_agent import research_agent

from services.agent_router import route_query
from services.dynamic_dataset_service import has_uploaded_dataset


INFORMATION_NOT_AVAILABLE = (
    "The information is not available in the uploaded file."
)


# ============================================================
# SUPERVISOR ROUTER NODE
# ============================================================

def supervisor_router_node(
    state: dict[str, Any],
) -> dict[str, Any]:

    query = state.get(
        "user_query",
        "",
    ).strip()

    if not query:
        return {
            "success": False,
            "route": "dynamic",
            "final_answer": "Please enter a question.",
        }

    # ========================================================
    # IMPORTANT:
    # If a document is uploaded, uploaded data has priority.
    # ========================================================

    if has_uploaded_dataset():
        route = route_query(query)

        # Explicit HR queries can still use the existing
        # HR Agent.
        if route == "hr":
            selected_route = "hr"

        # Every other question must be checked against
        # the uploaded document.
        else:
            selected_route = "dynamic"

        return {
            "success": True,
            "route": selected_route,
            "document_uploaded": True,
        }

    # ========================================================
    # NO DOCUMENT UPLOADED
    # ========================================================

    route = route_query(query)

    return {
        "success": True,
        "route": route,
        "document_uploaded": False,
    }


# ============================================================
# HR AGENT NODE
# ============================================================

def supervisor_hr_node(
    state: dict[str, Any],
) -> dict[str, Any]:

    query = state.get(
        "user_query",
        "",
    )

    conversation_history = state.get(
        "conversation_history",
        [],
    )

    conversation_id = state.get(
        "conversation_id",
        "supervisor",
    )

    try:

        result = hr_graph.invoke(
            {
                "user_query": query,
                "conversation_history": conversation_history,
            },
            config={
                "configurable": {
                    "thread_id": conversation_id,
                }
            },
        )

        answer = result.get(
            "final_answer"
        )

        if not answer:
            answer = "I could not generate an answer."

        return {
            "success": True,
            "agent_result": result,
            "agent_answer": str(answer),
        }

    except Exception as error:

        return {
            "success": False,
            "agent_result": {
                "success": False,
                "error": str(error),
            },
            "agent_answer": (
                "I could not generate an answer."
            ),
        }


# ============================================================
# DYNAMIC DATA AGENT NODE
# ============================================================

def supervisor_dynamic_node(
    state: dict[str, Any],
) -> dict[str, Any]:

    query = state.get(
        "user_query",
        "",
    )

    # Optional dataset selection.
    #
    # If dataset_id is provided:
    #     Dynamic Agent uses that exact dataset.
    #
    # If dataset_id is not provided:
    #     Dynamic Agent keeps using the latest dataset.
    dataset_id = state.get(
        "dataset_id"
    )

    try:

        dynamic_state = {
            "user_query": query,
        }

        if dataset_id is not None:
            dynamic_state["dataset_id"] = dataset_id

        result = dynamic_graph.invoke(
            dynamic_state
        )

        answer = result.get(
            "final_answer"
        )

        if not answer:
            answer = INFORMATION_NOT_AVAILABLE

        return {
            "success": True,
            "agent_result": result,
            "agent_answer": str(answer),
        }

    except Exception as error:

        return {
            "success": False,
            "agent_result": {
                "success": False,
                "error": str(error),
            },
            "agent_answer": INFORMATION_NOT_AVAILABLE,
        }


# ============================================================
# RESEARCH AGENT NODE
# ============================================================

def supervisor_research_node(
    state: dict[str, Any],
) -> dict[str, Any]:

    query = state.get(
        "user_query",
        "",
    )

    try:

        result = research_agent(query)

        if not isinstance(result, dict):

            return {
                "success": False,
                "agent_result": {
                    "success": False,
                    "error": "Invalid research response.",
                },
                "agent_answer": (
                    "I could not generate an answer."
                ),
            }

        answer = result.get(
            "message"
        )

        if not answer:
            answer = "I could not generate an answer."

        return {
            "success": bool(
                result.get("success", False)
            ),
            "agent_result": result,
            "agent_answer": str(answer),
        }

    except Exception as error:

        return {
            "success": False,
            "agent_result": {
                "success": False,
                "error": str(error),
            },
            "agent_answer": (
                "I could not generate an answer."
            ),
        }


# ============================================================
# VALIDATOR NODE
# ============================================================

def validator_node(
    state: dict[str, Any],
) -> dict[str, Any]:

    route = state.get("route")

    agent_result = state.get(
        "agent_result",
        {},
    )

    agent_answer = state.get(
        "agent_answer",
        "",
    )

        # ========================================================
    # DYNAMIC DATA VALIDATION
    # ========================================================

    if route == "dynamic":

        if not agent_result:

            return {
                "validated": False,
                "validation_result": {
                    "supported": False,
                    "reason": "No agent result.",
                },
                "final_answer": INFORMATION_NOT_AVAILABLE,
            }

        # ----------------------------------------------------
        # Missing information is a valid grounded response.
        # It means the requested information does not exist
        # in the uploaded file.
        # ----------------------------------------------------

        if agent_answer.strip() == INFORMATION_NOT_AVAILABLE:

            return {
                "validated": True,
                "validation_result": {
                    "supported": False,
                    "source": "uploaded_data",
                    "reason": "Information not available in uploaded file.",
                },
                "final_answer": INFORMATION_NOT_AVAILABLE,
            }

        query_result = agent_result.get(
            "query_result"
        )

        if query_result:

            if query_result.get("success"):

                return {
                    "validated": True,
                    "validation_result": {
                        "supported": True,
                        "source": "uploaded_data",
                    },
                    "final_answer": str(
                        agent_answer
                    ),
                }

            return {
                "validated": False,
                "validation_result": {
                    "supported": False,
                    "reason": query_result.get(
                        "message",
                        "Query failed.",
                    ),
                },
                "final_answer": INFORMATION_NOT_AVAILABLE,
            }

        return {
            "validated": False,
            "validation_result": {
                "supported": False,
                "reason": (
                    "No verified query result was produced."
                ),
            },
            "final_answer": INFORMATION_NOT_AVAILABLE,
        }

    # ========================================================
    # HR VALIDATION
    # ========================================================

    if route == "hr":

        if not agent_answer:

            return {
                "validated": False,
                "validation_result": {
                    "supported": False,
                    "reason": (
                        "HR agent returned no answer."
                    ),
                },
                "final_answer": (
                    "I could not generate an answer."
                ),
            }

        return {
            "validated": True,
            "validation_result": {
                "supported": True,
                "source": "hr_database",
            },
            "final_answer": str(
                agent_answer
            ),
        }

    # ========================================================
    # RESEARCH VALIDATION
    # ========================================================

    if route == "research":

        if not agent_result:

            return {
                "validated": False,
                "validation_result": {
                    "supported": False,
                    "reason": (
                        "Research agent returned no result."
                    ),
                },
                "final_answer": (
                    "I could not generate an answer."
                ),
            }

        if not agent_result.get("success", False):

            return {
                "validated": False,
                "validation_result": {
                    "supported": False,
                    "reason": "Research agent failed.",
                },
                "final_answer": (
                    "I could not generate an answer."
                ),
            }

        if not agent_answer:

            return {
                "validated": False,
                "validation_result": {
                    "supported": False,
                    "reason": (
                        "Research agent returned no answer."
                    ),
                },
                "final_answer": (
                    "I could not generate an answer."
                ),
            }

        return {
            "validated": True,
            "validation_result": {
                "supported": True,
                "source": "research_agent",
            },
            "final_answer": str(
                agent_answer
            ),
        }

    # ========================================================
    # UNKNOWN ROUTE
    # ========================================================

    return {
        "validated": False,
        "validation_result": {
            "supported": False,
            "reason": "Unknown agent route.",
        },
        "final_answer": INFORMATION_NOT_AVAILABLE,
    }


# ============================================================
# FINAL NODE
# ============================================================

def supervisor_final_node(
    state: dict[str, Any],
) -> dict[str, Any]:

    answer = state.get(
        "final_answer"
    )

    if answer:

        return {
            "success": True,
            "final_answer": str(answer),
        }

    return {
        "success": False,
        "final_answer": INFORMATION_NOT_AVAILABLE,
    }