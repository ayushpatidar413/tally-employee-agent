from typing import Any

from database.dynamic_data_db import (
    get_dataset,
    get_datasets,
    get_dataset_rows,
    get_dataset_schema,
    get_all_dataset_schemas,
    get_dataset_column_values,
)


# ============================================================
# DATASET ROWS
# ============================================================

def load_dataset_rows(
    dataset_id: int,
) -> list[dict[str, Any]]:
    """
    Load persisted rows for a dataset.

    Database rows are stored as wrappers:
    {
        "id": ...,
        "dataset_id": ...,
        "row_number": ...,
        "data": {...}
    }

    This function returns only the actual row data.
    """

    rows = get_dataset_rows(dataset_id)

    return [
        row.get("data", row)
        for row in rows
    ]
    
def load_dataset_column_values(
    dataset_id: int,
    column_name: str,
) -> list[Any]:
    """
    Load only one column from persisted dataset rows.

    This is used for lightweight operations such as
    checking whether a dataset contains a requested
    date/month/year without loading every column.
    """

    return get_dataset_column_values(
        dataset_id,
        column_name,
    )

def check_dataset_has_matching_dates(
    dataset_id: int,
    column_name: str,
    date_filters: list[dict[str, Any]],
) -> bool:

    return dataset_has_matching_dates(
        dataset_id,
        column_name,
        date_filters,
    )
# ============================================================
# DATASET INFORMATION
# ============================================================

def get_dataset_context(
    dataset_id: int,
) -> dict[str, Any] | None:

    dataset = get_dataset(dataset_id)

    if not dataset:
        return None

    schema = get_dataset_schema(dataset_id)

    rows = load_dataset_rows(dataset_id)

    return {
        "dataset": dataset,
        "schema": schema,
        "rows": rows,
    }


# ============================================================
# ALL DATASETS
# ============================================================

def get_all_dataset_context() -> list[dict[str, Any]]:

    datasets = get_datasets()

    all_schemas = get_all_dataset_schemas()

    results = []

    for dataset in datasets:

        dataset_id = int(
            dataset["id"]
        )

        results.append(
            {
                "dataset": dataset,
                "schema": all_schemas.get(
                    dataset_id,
                    [],
                ),
            }
        )

    return results


# ============================================================
# FIND DATASETS BY TYPE
# ============================================================

def find_datasets_by_type(
    dataset_type: str,
) -> list[dict[str, Any]]:

    dataset_type = (
        str(dataset_type)
        .strip()
        .lower()
    )

    datasets = get_datasets()

    return [
        dataset
        for dataset in datasets
        if str(
            dataset.get("data_type", "")
        ).strip().lower()
        == dataset_type
    ]


# ============================================================
# GET ROWS BY DATASET TYPE
# ============================================================

def get_rows_by_dataset_type(
    dataset_type: str,
) -> list[dict[str, Any]]:

    datasets = find_datasets_by_type(
        dataset_type
    )

    if not datasets:
        return []

    # get_datasets() returns newest first
    latest_dataset = datasets[0]

    return load_dataset_rows(
        latest_dataset["id"]
    )


# ============================================================
# SEARCH ROWS
# ============================================================

def search_rows(
    rows: list[dict[str, Any]],
    search_text: str,
) -> list[dict[str, Any]]:

    search_text = (
        str(search_text)
        .strip()
        .lower()
    )

    if not search_text:
        return rows

    results = []

    for row in rows:

        for value in row.values():

            if search_text in str(value).lower():

                results.append(row)

                break

    return results


# ============================================================
# FILTER BY COLUMN
# ============================================================

def filter_rows_by_column(
    rows: list[dict[str, Any]],
    column_name: str,
    value: Any,
) -> list[dict[str, Any]]:

    normalized_column = (
        str(column_name)
        .strip()
        .lower()
    )

    normalized_value = (
        str(value)
        .strip()
        .lower()
    )

    results = []

    for row in rows:

        for key, row_value in row.items():

            if (
                str(key).strip().lower()
                == normalized_column
            ):

                if (
                    str(row_value)
                    .strip()
                    .lower()
                    == normalized_value
                ):

                    results.append(row)

                break

    return results


# ============================================================
# NUMBER CONVERSION
# ============================================================

def to_number(
    value: Any,
) -> float | None:

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = (
        str(value)
        .strip()
        .replace(",", "")
        .replace("₹", "")
        .replace("â‚¹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("â‚¬", "")
    )

    if not text:
        return None

    try:
        return float(text)

    except (ValueError, TypeError):
        return None


# ============================================================
# SUM COLUMN
# ============================================================

def sum_column(
    rows: list[dict[str, Any]],
    column_name: str,
) -> float:

    normalized_column = (
        str(column_name)
        .strip()
        .lower()
    )

    total = 0.0

    for row in rows:

        for key, value in row.items():

            if (
                str(key).strip().lower()
                == normalized_column
            ):

                number = to_number(value)

                if number is not None:
                    total += number

                break

    return total


# ============================================================
# COUNT ROWS
# ============================================================

def count_rows(
    rows: list[dict[str, Any]],
) -> int:

    return len(rows)


# ============================================================
# GROUP AND SUM
# ============================================================

def group_and_sum(
    rows: list[dict[str, Any]],
    group_column: str,
    value_column: str,
) -> list[dict[str, Any]]:
    """
    Group rows by one column and sum another column.

    Example result:

    [
        {
            "group": "Monitor",
            "total": 22000
        },
        {
            "group": "Keyboard",
            "total": 15000
        }
    ]
    """

    normalized_group = (
        str(group_column)
        .strip()
        .lower()
    )

    normalized_value = (
        str(value_column)
        .strip()
        .lower()
    )

    groups: dict[str, float] = {}

    for row in rows:

        group_value = None
        numeric_value = None

        for key, value in row.items():

            normalized_key = (
                str(key)
                .strip()
                .lower()
            )

            if normalized_key == normalized_group:

                group_value = value

            elif normalized_key == normalized_value:

                numeric_value = to_number(value)

        if group_value is None:
            continue

        if numeric_value is None:
            numeric_value = 0.0

        group_key = str(
            group_value
        ).strip()

        groups.setdefault(
            group_key,
            0.0,
        )

        groups[group_key] += numeric_value

    results = []

    for group, total in groups.items():

        results.append(
            {
                "group": group,
                "total": total,
            }
        )

    results.sort(
        key=lambda item: item["total"],
        reverse=True,
    )

    return results


# ============================================================
# HIGHEST VALUE
# ============================================================

def highest_value(
    rows: list[dict[str, Any]],
    column_name: str,
) -> dict[str, Any] | None:
    """
    Return the row having the highest value
    in the specified numeric column.
    """

    normalized_column = (
        str(column_name)
        .strip()
        .lower()
    )

    best_row = None
    best_value = None

    for row in rows:

        for key, value in row.items():

            if (
                str(key).strip().lower()
                == normalized_column
            ):

                number = to_number(value)

                if number is None:
                    continue

                if (
                    best_value is None
                    or number > best_value
                ):

                    best_value = number
                    best_row = row

                break

    return best_row


# ============================================================
# FIND INVOICE
# ============================================================

def find_invoice(
    rows: list[dict[str, Any]],
    invoice_number: str,
) -> list[dict[str, Any]]:

    invoice_number = (
        str(invoice_number)
        .strip()
        .upper()
    )

    results = []

    for row in rows:

        for key, value in row.items():

            normalized_key = (
                str(key)
                .strip()
                .lower()
            )

            if normalized_key in {
                "invoice no",
                "invoice number",
                "invoice",
                "invoice_number",
            }:

                if (
                    str(value)
                    .strip()
                    .upper()
                    == invoice_number
                ):

                    results.append(row)

                break

    return results


# ============================================================
# FIND CUSTOMER TRANSACTIONS
# ============================================================

def find_customer_transactions(
    rows: list[dict[str, Any]],
    customer: str,
) -> list[dict[str, Any]]:

    results = []

    customer = (
        str(customer)
        .strip()
        .lower()
    )

    for row in rows:

        for key, value in row.items():

            normalized_key = (
                str(key)
                .strip()
                .lower()
            )

            if normalized_key in {
                "party name",
                "customer",
                "party",
                "customer name",
                "customer_name",
            }:

                if customer in str(value).lower():

                    results.append(row)

                break

    return results


# ============================================================
# DATASET SUMMARY
# ============================================================

def dataset_summary(
    dataset_id: int,
) -> dict[str, Any] | None:

    context = get_dataset_context(
        dataset_id
    )

    if not context:
        return None

    dataset = context["dataset"]

    rows = context["rows"]

    return {
        "dataset_id": dataset_id,
        "filename": dataset[
            "original_filename"
        ],
        "data_type": dataset[
            "data_type"
        ],
        "row_count": len(rows),
        "column_count": dataset[
            "column_count"
        ],
        "columns": dataset[
            "columns"
        ],
    }