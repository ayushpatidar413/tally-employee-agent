from services.dynamic_data_service import (
    calculate_numeric,
    dataframe_to_records,
)


INFORMATION_NOT_AVAILABLE = (
    "The information is not available in the uploaded file."
)


# ============================================================
# APPLY FILTER
# ============================================================

def apply_filter(dataframe, filter_info):

    if not filter_info:
        return dataframe

    column = filter_info.get("column")
    operator = filter_info.get("operator")
    value = filter_info.get("value")

    if not column or column not in dataframe.columns:
        return None

    result = dataframe.copy()

    series = result[column]

    # --------------------------------------------------------
    # NUMERIC FILTER
    # --------------------------------------------------------

    if operator in {">", ">=", "<", "<=", "="}:

        numeric_series = series

        try:
            numeric_value = float(value)
            numeric_series = numeric_series.astype(float)

            if operator == ">":
                mask = numeric_series > numeric_value

            elif operator == ">=":
                mask = numeric_series >= numeric_value

            elif operator == "<":
                mask = numeric_series < numeric_value

            elif operator == "<=":
                mask = numeric_series <= numeric_value

            else:
                mask = numeric_series == numeric_value

            return result[mask]

        except (
            ValueError,
            TypeError,
        ):
            # ------------------------------------------------
            # TEXT EQUALITY
            # ------------------------------------------------

            if operator != "=":
                return None

            mask = (
                series.astype(str)
                .str.strip()
                .str.lower()
                == str(value).strip().lower()
            )

            return result[mask]

    return None


# ============================================================
# ROW COUNT
# ============================================================

def execute_row_count(dataframe):

    return {
        "success": True,
        "operation": "row_count",
        "count": int(len(dataframe)),
    }


# ============================================================
# DATASET INFO
# ============================================================

def execute_dataset_info(dataframe):

    return {
        "success": True,
        "operation": "dataset_info",
        "row_count": int(len(dataframe)),
        "column_count": int(len(dataframe.columns)),
        "columns": list(dataframe.columns),
    }


# ============================================================
# NUMERIC OPERATION
# ============================================================

def execute_numeric_operation(
    dataframe,
    operation,
    column,
):

    if not column or column not in dataframe.columns:
        return {
            "success": False,
            "message": INFORMATION_NOT_AVAILABLE,
        }

    result = calculate_numeric(
        dataframe,
        column,
        operation,
    )

    if isinstance(result, dict):
        return result

    return {
        "success": True,
        "operation": operation,
        "column": column,
        "value": result,
    }


# ============================================================
# GROUP OPERATION
# ============================================================

def execute_group_operation(
    dataframe,
    operation,
    column,
    group_column,
):

    if not group_column:
        return {
            "success": False,
            "message": INFORMATION_NOT_AVAILABLE,
        }

    if group_column not in dataframe.columns:
        return {
            "success": False,
            "message": INFORMATION_NOT_AVAILABLE,
        }

    # --------------------------------------------------------
    # COUNT BY GROUP
    # --------------------------------------------------------

    if operation == "count":

        grouped = (
            dataframe
            .groupby(group_column)
            .size()
            .to_dict()
        )

        return {
            "success": True,
            "operation": "count",
            "group_column": group_column,
            "values": grouped,
        }

    # --------------------------------------------------------
    # Other grouped numeric operations
    # --------------------------------------------------------

    if not column or column not in dataframe.columns:
        return {
            "success": False,
            "message": INFORMATION_NOT_AVAILABLE,
        }

    try:

        if operation == "sum":

            grouped = (
                dataframe
                .groupby(group_column)[column]
                .sum()
                .to_dict()
            )

        elif operation == "average":

            grouped = (
                dataframe
                .groupby(group_column)[column]
                .mean()
                .to_dict()
            )

        elif operation == "min":

            grouped = (
                dataframe
                .groupby(group_column)[column]
                .min()
                .to_dict()
            )

        elif operation == "max":

            grouped = (
                dataframe
                .groupby(group_column)[column]
                .max()
                .to_dict()
            )

        else:

            return {
                "success": False,
                "message": INFORMATION_NOT_AVAILABLE,
            }

        return {
            "success": True,
            "operation": operation,
            "column": column,
            "group_column": group_column,
            "values": grouped,
        }

    except (
        ValueError,
        TypeError,
    ):

        return {
            "success": False,
            "message": INFORMATION_NOT_AVAILABLE,
        }


# ============================================================
# FILTER ONLY
# ============================================================

def execute_filter(
    dataframe,
    filter_info,
):

    filtered = apply_filter(
        dataframe,
        filter_info,
    )

    if filtered is None:
        return {
            "success": False,
            "message": INFORMATION_NOT_AVAILABLE,
        }

    records = dataframe_to_records(
        filtered
    )

    return {
        "success": True,
        "operation": "filter",
        "count": int(len(filtered)),
        "records": records,
    }


# ============================================================
# UNIQUE VALUES
# ============================================================

def execute_unique_values(
    dataframe,
    column,
):

    if not column or column not in dataframe.columns:
        return {
            "success": False,
            "message": INFORMATION_NOT_AVAILABLE,
        }

    values = (
        dataframe[column]
        .dropna()
        .unique()
        .tolist()
    )

    return {
        "success": True,
        "operation": "unique",
        "column": column,
        "values": values,
    }


# ============================================================
# COLUMN SUMMARY
# ============================================================

def execute_column_summary(
    dataframe,
    column,
):

    if not column or column not in dataframe.columns:
        return {
            "success": False,
            "message": INFORMATION_NOT_AVAILABLE,
        }

    series = dataframe[column]

    return {
        "success": True,
        "operation": "summary",
        "column": column,
        "count": int(series.count()),
        "unique": int(series.nunique()),
        "null_count": int(series.isna().sum()),
    }


# ============================================================
# MAIN QUERY EXECUTOR
# ============================================================

def execute_query(
    dataframe,
    operation=None,
    column=None,
    group_column=None,
    filter_info=None,
    query_plan=None,
):

    # --------------------------------------------------------
    # SUPPORT QUERY PLAN FROM DYNAMIC NODES
    # --------------------------------------------------------

    if query_plan is not None:

        operation = query_plan.get("operation")
        column = query_plan.get("column")
        group_column = query_plan.get("group_column")
        filter_info = query_plan.get("filter")

    working_dataframe = dataframe

    # --------------------------------------------------------
    # APPLY FILTER FIRST
    # --------------------------------------------------------

    if filter_info:

        working_dataframe = apply_filter(
            dataframe,
            filter_info,
        )

        if working_dataframe is None:
            return {
                "success": False,
                "message": INFORMATION_NOT_AVAILABLE,
            }

        # ----------------------------------------------------
        # NO MATCHING RECORDS
        # ----------------------------------------------------

        if len(working_dataframe) == 0:

            return {
                "success": True,
                "operation": operation,
                "count": 0,
                "records": [],
                "message": "No matching records were found in the uploaded file.",
            }

    # --------------------------------------------------------
    # ROW COUNT
    # --------------------------------------------------------

    if operation == "row_count":

        return execute_row_count(
            working_dataframe
        )

    # --------------------------------------------------------
    # DATASET INFO
    # --------------------------------------------------------

    if operation == "dataset_info":

        return execute_dataset_info(
            working_dataframe
        )

    # --------------------------------------------------------
    # GROUP OPERATION
    # --------------------------------------------------------

    if group_column:

        return execute_group_operation(
            working_dataframe,
            operation,
            column,
            group_column,
        )

    # --------------------------------------------------------
    # COUNT
    # --------------------------------------------------------

    if operation == "count":

        return {
            "success": True,
            "operation": "count",
            "column": column,
            "count": int(len(working_dataframe)),
        }

    # --------------------------------------------------------
    # FILTER
    # --------------------------------------------------------

    if operation == "filter":

        if filter_info:

            return execute_filter(
                dataframe,
                filter_info,
            )

        return {
            "success": True,
            "operation": "filter",
            "count": int(len(working_dataframe)),
            "records": dataframe_to_records(
                working_dataframe
            ),
        }

    # --------------------------------------------------------
    # NUMERIC OPERATIONS
    # --------------------------------------------------------

    if operation in {
        "sum",
        "average",
        "min",
        "max",
    }:

        return execute_numeric_operation(
            working_dataframe,
            operation,
            column,
        )

    # --------------------------------------------------------
    # UNIQUE
    # --------------------------------------------------------

    if operation == "unique":

        return execute_unique_values(
            working_dataframe,
            column,
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    if operation == "summary":

        return execute_column_summary(
            working_dataframe,
            column,
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    return {
        "success": False,
        "message": INFORMATION_NOT_AVAILABLE,
    }


# ============================================================
# QUERY PLAN EXECUTOR
# ============================================================

def execute_query_plan(
    dataframe,
    query_plan,
):

    if not query_plan.get("success", True):

        return {
            "success": False,
            "message": query_plan.get(
                "message",
                INFORMATION_NOT_AVAILABLE,
            ),
        }

    return execute_query(
        dataframe=dataframe,
        operation=query_plan.get("operation"),
        column=query_plan.get("column"),
        group_column=query_plan.get("group_column"),
        filter_info=query_plan.get("filter"),
    )