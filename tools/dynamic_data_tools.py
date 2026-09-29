
import json
from typing import Any

from database.dynamic_data_db import (
    get_datasets,
    get_dataset,
    get_dataset_rows,
    find_datasets_by_canonical_column,
)

from services.dynamic_data_service import (
    clean_value,
)


# ============================================================
# LIST DATASETS
# ============================================================

def list_dynamic_datasets() -> dict[str, Any]:
    """
    Return all uploaded dynamic datasets.

    Useful for questions such as:

        What files have been uploaded?
        Show my datasets.
        What data do you have?
    """

    try:

        datasets = get_datasets()

        return {
            "success": True,
            "count": len(datasets),
            "datasets": datasets,
        }

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to retrieve datasets."
            ),
            "error": str(error),
        }


# ============================================================
# GET DATASET DETAILS
# ============================================================

def get_dynamic_dataset(
    dataset_id: int,
) -> dict[str, Any]:
    """
    Return metadata and schema information
    for a specific dataset.
    """

    try:

        dataset = get_dataset(
            dataset_id
        )

        if not dataset:

            return {
                "success": False,
                "message": (
                    f"Dataset {dataset_id} "
                    "was not found."
                ),
            }

        rows = get_dataset_rows(
            dataset_id
        )

        return {
            "success": True,
            "dataset": dataset,
            "row_count": len(rows),
        }

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to retrieve dataset."
            ),
            "error": str(error),
        }


# ============================================================
# GET DATASET ROWS
# ============================================================

def get_dynamic_dataset_rows(
    dataset_id: int,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Return rows stored for a dataset.

    Example:

        Show the sales data.
    """

    try:

        rows = get_dataset_rows(
            dataset_id
        )

        limited_rows = rows[:limit]

        return {
            "success": True,
            "dataset_id": dataset_id,
            "total_rows": len(rows),
            "returned_rows": len(
                limited_rows
            ),
            "rows": limited_rows,
        }

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to retrieve dataset rows."
            ),
            "error": str(error),
        }


# ============================================================
# SEARCH DATASET ROWS
# ============================================================

def search_dynamic_dataset(
    dataset_id: int,
    search_text: str,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Search all values inside a dataset.

    Example:

        Find ABC Traders.

    This searches across every column.
    """

    try:

        rows = get_dataset_rows(
            dataset_id
        )

        search_text = str(
            search_text
        ).lower().strip()

        matched_rows = []

        for row in rows:

            data = row.get(
                "data",
                {}
            )

            found = False

            for value in data.values():

                if value is None:
                    continue

                value_text = str(
                    value
                ).lower()

                if search_text in value_text:

                    found = True
                    break

            if found:

                matched_rows.append(
                    row
                )

            if len(matched_rows) >= limit:
                break

        return {
            "success": True,
            "dataset_id": dataset_id,
            "search_text": search_text,
            "total_matches": len(
                matched_rows
            ),
            "rows": matched_rows,
        }

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to search dataset."
            ),
            "error": str(error),
        }


# ============================================================
# FILTER DATASET
# ============================================================

def filter_dynamic_dataset(
    dataset_id: int,
    column: str,
    value: Any,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Filter dataset rows using a column/value pair.

    Example:

        column = "Party Name"
        value = "ABC Traders"
    """

    try:

        rows = get_dataset_rows(
            dataset_id
        )

        target_value = str(
            value
        ).strip().lower()

        matched_rows = []

        for row in rows:

            data = row.get(
                "data",
                {}
            )

            if column not in data:
                continue

            current_value = data.get(
                column
            )

            if current_value is None:
                continue

            if (
                str(current_value)
                .strip()
                .lower()
                == target_value
            ):

                matched_rows.append(
                    row
                )

            if len(matched_rows) >= limit:
                break

        return {
            "success": True,
            "dataset_id": dataset_id,
            "column": column,
            "value": value,
            "total_matches": len(
                matched_rows
            ),
            "rows": matched_rows,
        }

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to filter dataset."
            ),
            "error": str(error),
        }


# ============================================================
# NUMERIC SUMMARY
# ============================================================

def summarize_dynamic_column(
    dataset_id: int,
    column: str,
) -> dict[str, Any]:
    """
    Calculate numeric statistics for a column.

    Returns:

        count
        total
        minimum
        maximum
        average
    """

    try:

        rows = get_dataset_rows(
            dataset_id
        )

        values = []

        for row in rows:

            data = row.get(
                "data",
                {}
            )

            if column not in data:
                continue

            value = data.get(
                column
            )

            if value is None:
                continue

            try:

                numeric_value = float(
                    value
                )

                values.append(
                    numeric_value
                )

            except (
                ValueError,
                TypeError,
            ):

                continue

        if not values:

            return {
                "success": False,
                "message": (
                    f"No numeric values "
                    f"found in column '{column}'."
                ),
                "dataset_id": dataset_id,
                "column": column,
            }

        total = sum(values)

        return {
            "success": True,
            "dataset_id": dataset_id,
            "column": column,
            "count": len(values),
            "total": total,
            "minimum": min(values),
            "maximum": max(values),
            "average": (
                total / len(values)
            ),
        }

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to summarize column."
            ),
            "error": str(error),
        }


# ============================================================
# SEARCH DATASETS BY CANONICAL COLUMN
# ============================================================

def find_dynamic_datasets_by_column(
    canonical_column: str,
) -> dict[str, Any]:
    """
    Find datasets containing a specific
    canonical business field.

    Example:

        transaction_date
        customer
        supplier
        amount
        product
    """

    try:

        datasets = (
            find_datasets_by_canonical_column(
                canonical_column
            )
        )

        return {
            "success": True,
            "canonical_column": (
                canonical_column
            ),
            "count": len(datasets),
            "datasets": datasets,
        }

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to find datasets "
                "by canonical column."
            ),
            "error": str(error),
        }


# ============================================================
# GENERIC DATASET REPORT
# ============================================================

def generate_dynamic_dataset_report(
    dataset_id: int,
) -> dict[str, Any]:
    """
    Generate a basic report for a dataset.

    Automatically identifies numeric columns
    and calculates their totals.
    """

    try:

        dataset = get_dataset(
            dataset_id
        )

        if not dataset:

            return {
                "success": False,
                "message": (
                    f"Dataset {dataset_id} "
                    "was not found."
                ),
            }

        rows = get_dataset_rows(
            dataset_id
        )

        if not rows:

            return {
                "success": False,
                "message": (
                    "Dataset contains no rows."
                ),
            }

        all_columns = set()

        for row in rows:

            data = row.get(
                "data",
                {}
            )

            all_columns.update(
                data.keys()
            )

        numeric_summary = {}

        for column in sorted(
            all_columns
        ):

            summary = (
                summarize_dynamic_column(
                    dataset_id,
                    column,
                )
            )

            if summary.get(
                "success"
            ):

                numeric_summary[
                    column
                ] = summary

        return {
            "success": True,
            "dataset": dataset,
            "total_rows": len(rows),
            "columns": sorted(
                all_columns
            ),
            "numeric_summary": (
                numeric_summary
            ),
        }

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to generate dataset report."
            ),
            "error": str(error),
        }


# ============================================================
# AGENT TOOL LIST
# ============================================================

DYNAMIC_DATA_TOOLS = [

    list_dynamic_datasets,

    get_dynamic_dataset,

    get_dynamic_dataset_rows,

    search_dynamic_dataset,

    filter_dynamic_dataset,

    summarize_dynamic_column,

    find_dynamic_datasets_by_column,

    generate_dynamic_dataset_report,

]
