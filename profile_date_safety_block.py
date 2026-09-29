import time
from graph import dynamic_nodes as d

datasets = d.get_all_dataset_context()
question = "Show GST for April 2025"

print("--- DATE SAFETY BLOCK PROFILE ---")

for item in datasets:
    dataset = item.get("dataset", {})
    schema = item.get("schema", [])

    if not d._is_detailed_transaction_dataset(
        dataset,
        schema,
    ):
        continue

    dataset_id = int(dataset.get("id"))

    start = time.perf_counter()

    date_filters = d._extract_date_filters(
        question,
        dataset,
        schema,
        [],
    )

    if not date_filters:
        continue

    date_column = d._find_date_column(
        dataset,
        schema,
        [],
    )

    column_start = time.perf_counter()

    date_values = d.load_dataset_column_values(
        dataset_id,
        date_column,
    )

    column_time = time.perf_counter() - column_start

    parse_start = time.perf_counter()

    period_exists = False

    for raw_date in date_values:
        actual_date = d._parse_date(raw_date)

        if actual_date is None:
            continue

        matches = True

        for date_filter in date_filters:
            operator = date_filter.get("operator")
            value = date_filter.get("value")

            if operator == "year":
                if actual_date.year != int(value):
                    matches = False
                    break

            elif operator == "month":
                if actual_date.month != int(value):
                    matches = False
                    break

        if matches:
            period_exists = True
            break

    parse_time = time.perf_counter() - parse_start
    total_time = time.perf_counter() - start

    print(
        f"DATASET = {dataset_id}"
    )
    print(
        f"DATE COLUMN = {date_column}"
    )
    print(
        f"DATE VALUES = {len(date_values)}"
    )
    print(
        f"COLUMN LOAD = {column_time:.4f}s"
    )
    print(
        f"DATE PARSING/SCAN = {parse_time:.4f}s"
    )
    print(
        f"TOTAL BLOCK = {total_time:.4f}s"
    )
    print(
        f"PERIOD EXISTS = {period_exists}"
    )
