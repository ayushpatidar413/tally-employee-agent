from pathlib import Path
import importlib.util
import pandas as pd


WORKBOOK = Path(
    r"C:\Users\91930\Desktop\project\tally-employee-agent-backup-20261021-152323\test_data\Vyapar_Style_Accessories_Sales_Report.xlsx"
)

PLAN_FILE = Path("tests/test_query_understanding.py")


def load_query_module():
    spec = importlib.util.spec_from_file_location(
        "query_understanding",
        PLAN_FILE,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_dataset():
    df = pd.read_excel(
        WORKBOOK,
        sheet_name="Sale Invoices",
    )

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce",
        )

    return df


def apply_filters(df, filters):
    result = df.copy()

    for condition in filters or []:
        column = condition["column"]
        operator = condition["operator"]
        value = condition["value"]

        if column not in result.columns:
            raise ValueError(f"Missing filter column: {column}")

        numeric = pd.to_numeric(
            result[column],
            errors="coerce",
        )

        if operator == ">":
            mask = numeric > value
        elif operator == ">=":
            mask = numeric >= value
        elif operator == "<":
            mask = numeric < value
        elif operator == "<=":
            mask = numeric <= value
        elif operator in ("=", "=="):
            mask = numeric == value
        elif operator in ("!=", "<>"):
            mask = numeric != value
        else:
            raise ValueError(
                f"Unsupported operator: {operator}"
            )

        result = result.loc[mask]

    return result


def apply_date_filter(df, date_filter):
    if not date_filter:
        return df.copy()

    column = date_filter["column"]

    if column not in df.columns:
        raise ValueError(f"Missing date column: {column}")

    dates = pd.to_datetime(
        df[column],
        errors="coerce",
    )

    start = pd.Timestamp(date_filter["start_date"])
    end = pd.Timestamp(date_filter["end_date"])

    return df.loc[dates.between(start, end)].copy()


def aggregate_data(df, metrics, operations, group_by=None):
    if df.empty:
        return pd.DataFrame()

    for metric in metrics:
        if metric not in df.columns:
            raise ValueError(f"Missing metric column: {metric}")

    if group_by:
        if group_by not in df.columns:
            raise ValueError(f"Missing grouping column: {group_by}")

        grouped = df.groupby(
            group_by,
            dropna=False,
        )

        result = grouped.size().to_frame("RecordCount")

        for metric in metrics:
            values = pd.to_numeric(
                df[metric],
                errors="coerce",
            )

            temp = df.assign(_metric_value=values)

            operation = operations.get(metric, "sum")

            if operation == "sum":
                calculated = temp.groupby(
                    group_by,
                    dropna=False,
                )["_metric_value"].sum(min_count=1)

            elif operation == "average":
                calculated = temp.groupby(
                    group_by,
                    dropna=False,
                )["_metric_value"].mean()

            else:
                raise ValueError(
                    f"Unsupported operation: {operation}"
                )

            result[metric] = calculated

        return result.reset_index()

    result = {}

    for metric in metrics:
        values = pd.to_numeric(
            df[metric],
            errors="coerce",
        )

        operation = operations.get(metric, "sum")

        if operation == "sum":
            result[metric] = values.sum(min_count=1)
        elif operation == "average":
            result[metric] = values.mean()
        else:
            raise ValueError(
                f"Unsupported operation: {operation}"
            )

    return pd.DataFrame([result])


def execute_plan(df, plan):
    filtered = apply_filters(
        df,
        plan.get("filters", []),
    )

    filtered = apply_date_filter(
        filtered,
        plan.get("date_filter"),
    )

    metrics = plan.get("metrics") or []

    if not metrics and plan.get("metric"):
        metrics = [plan["metric"]]

    preview_limit = int(plan.get("preview_limit", 10))

    if preview_limit < 1:
        raise ValueError("preview_limit must be at least 1")

    
        
    if filtered.empty:
        return {
            "status": "no_data",
            "source_rows": len(df),
            "filtered_rows": 0,
            "metrics": metrics,
            "group_by": plan.get("group_by"),
            "total_matching_rows": 0,
            "preview_limit": preview_limit,
            "preview_rows": [],
            "rows": [],
        }
    if not metrics:
        return {
            "status": "filtered_data" if not filtered.empty else "no_data",
            "source_rows": len(df),
            "filtered_rows": len(filtered),
            "total_matching_rows": len(filtered),
            "preview_limit": preview_limit,
            "preview_rows": filtered.head(
                preview_limit
            ).to_dict("records"),
            "rows": filtered.head(
                preview_limit
            ).to_dict("records"),
        }

    operations = plan.get("metric_operations", {})

    result = aggregate_data(
        filtered,
        metrics,
        operations,
        plan.get("group_by"),
    )

    ranking_metric = plan.get("ranking_metric")

    if ranking_metric:
        if ranking_metric not in result.columns:
            raise ValueError(
                f"Ranking metric '{ranking_metric}' "
                "is not available in the aggregated result. "
                f"Available columns: {result.columns.tolist()}"
            )

        ascending = plan.get("ranking") == "ascending"

        result = result.sort_values(
            ranking_metric,
            ascending=ascending,
        )

    limit = plan.get("limit")

    if limit:
        result = result.head(limit)

    return {
        "status": "success" if not filtered.empty else "no_data",
        "source_rows": len(df),
        "filtered_rows": len(filtered),
        "metrics": metrics,
        "group_by": plan.get("group_by"),
        "total_matching_rows": len(filtered),
        "preview_limit": preview_limit,
        "rows": result.to_dict("records"),
    }


def main():
    query_module = load_query_module()
    df = load_dataset()
    columns = df.columns.tolist()

    questions = [
        "Which product has highest quantity sold?",
        "Show total sales and profit where unit price is greater than 1500",
        "Top 5 products by profit in Q3 FY2025-26",
        "Show average quantity and total profit",
        "Show products where unit price is greater than 1000 and quantity less than 10",
    ]

    print("DATASET ROWS:", len(df))
    print("DATE RANGE:", df["Date"].min(), "TO", df["Date"].max())

    for question in questions:
        print("\n" + "=" * 75)
        print("QUESTION:", question)

        plan = query_module.build_query_plan(
            question,
            columns,
        )

        print("PLAN:", plan)

        result = execute_plan(df, plan)

        print("STATUS:", result["status"])
        print("SOURCE ROWS:", result["source_rows"])
        print("FILTERED ROWS:", result["filtered_rows"])

        print("TOTAL MATCHING ROWS:",
              result.get("total_matching_rows", result["filtered_rows"]))

        print("RESULT:")

        if result["status"] == "filtered_data":
            preview_rows = result.get("preview_rows", [])

            print("PREVIEW LIMIT:", result.get("preview_limit", 10))
            print("SHOWING:", len(preview_rows), "OF",
                  result.get("total_matching_rows", 0))

            for index, row in enumerate(preview_rows, start=1):
                print(f"\nRecord {index}:")

                for key, value in row.items():
                    print(f"  {key}: {value}")

        elif result["status"] == "no_data":
            print("Information is not available in the uploaded file.")

        else:
            for row in result.get("rows", []):
                print(row)


if __name__ == "__main__":
    main()


