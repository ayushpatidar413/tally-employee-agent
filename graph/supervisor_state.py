from typing import Any, TypedDict


class SupervisorState(TypedDict, total=False):
    # ========================================================
    # USER INPUT
    # ========================================================

    user_query: str

    # Optional dataset selected by the user.
    #
    # If None:
    #     Dynamic Agent uses the latest uploaded dataset.
    #
    # If provided:
    #     Dynamic Agent loads that exact dataset.
    dataset_id: int

    # ========================================================
    # CONVERSATION
    # ========================================================

    conversation_id: str

    conversation_history: list[dict[str, Any]]

    # ========================================================
    # ROUTING
    # ========================================================

    route: str

    # ========================================================
    # AGENT RESULT
    # ========================================================

    agent_result: dict[str, Any]

    agent_answer: str

    # ========================================================
    # VALIDATION
    # ========================================================

    validation_result: dict[str, Any]

    validated: bool

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    final_answer: str

    success: bool