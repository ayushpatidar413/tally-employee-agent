from typing import Any, TypedDict


class DynamicState(TypedDict, total=False):
    """
    State used by the Dynamic Data AI Agent.

    This state is independent from the existing HRState,
    so the old employee HR workflow is not broken.
    """

    # --------------------------------------------------------
    # User input
    # --------------------------------------------------------

    user_query: str

    # --------------------------------------------------------
    # Uploaded dataset
    # --------------------------------------------------------

    dataset_id: int
    dataset_name: str
    dataset: dict[str, Any]
    dataframe: Any

    # --------------------------------------------------------
    # Query understanding
    # --------------------------------------------------------

    query_plan: dict[str, Any]

    # --------------------------------------------------------
    # Programmatic result
    # --------------------------------------------------------

    query_result: dict[str, Any]

    # --------------------------------------------------------
    # Final natural-language answer
    # --------------------------------------------------------

    final_answer: str

    # --------------------------------------------------------
    # Error handling
    # --------------------------------------------------------

    success: bool
    error: str