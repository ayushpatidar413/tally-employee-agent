import time
from graph import dynamic_nodes as d

question = "Show GST for April 2025"
datasets = d.get_all_dataset_context()

print("--- SELECTOR INTERNAL PROFILE ---")

# 1. Detailed dataset identification
start = time.perf_counter()

detailed_transaction_datasets = []

for item in datasets:
    dataset = item.get("dataset", {})
    schema = item.get("schema", [])

    if d._is_detailed_transaction_dataset(
        dataset,
        schema,
    ):
        detailed_transaction_datasets.append(item)

elapsed = time.perf_counter() - start

print(
    f"DETAILED DATASET BUILD = {elapsed:.4f}s"
)

# 2. Score datasets
start = time.perf_counter()

score_results = []

for item in datasets:
    dataset = item.get("dataset", {})
    schema = item.get("schema", [])

    score = d._score_dataset(
        question,
        dataset,
        schema,
    )

    score_results.append(
        (
            score,
            dataset.get("id"),
            item,
        )
    )

elapsed = time.perf_counter() - start

print(
    f"SCORE ALL DATASETS = {elapsed:.4f}s"
)

# 3. Date filter extraction
start = time.perf_counter()

date_results = []

for item in datasets:
    dataset = item.get("dataset", {})
    schema = item.get("schema", [])

    dataset_id = dataset.get("id")

    t = time.perf_counter()

    filters = d._extract_date_filters(
        question,
        dataset,
        schema,
        [],
    )

    one_elapsed = time.perf_counter() - t

    date_results.append(
        (
            dataset_id,
            one_elapsed,
            filters,
        )
    )

elapsed = time.perf_counter() - start

print(
    f"DATE FILTER EXTRACTION ALL = {elapsed:.4f}s"
)

# 4. Date column resolution
start = time.perf_counter()

date_column_results = []

for item in datasets:
    dataset = item.get("dataset", {})
    schema = item.get("schema", [])

    dataset_id = dataset.get("id")

    t = time.perf_counter()

    column = d._find_date_column(
        dataset,
        schema,
        [],
    )

    one_elapsed = time.perf_counter() - t

    date_column_results.append(
        (
            dataset_id,
            one_elapsed,
            column,
        )
    )

elapsed = time.perf_counter() - start

print(
    f"DATE COLUMN RESOLUTION ALL = {elapsed:.4f}s"
)

print()
print("--- SLOW DATE FILTER EXTRACTIONS ---")

for dataset_id, elapsed, filters in sorted(
    date_results,
    key=lambda x: x[1],
    reverse=True,
)[:10]:
    print(
        f"ID={dataset_id} "
        f"TIME={elapsed:.4f}s "
        f"FILTERS={filters}"
    )

print()
print("--- SLOW DATE COLUMN RESOLUTIONS ---")

for dataset_id, elapsed, column in sorted(
    date_column_results,
    key=lambda x: x[1],
    reverse=True,
)[:10]:
    print(
        f"ID={dataset_id} "
        f"TIME={elapsed:.4f}s "
        f"COLUMN={column}"
    )

print()
print("--- TOTAL SELECTOR ---")

start = time.perf_counter()

result = d.select_dynamic_dataset(
    {
        "question": question,
    }
)

elapsed = time.perf_counter() - start

print(
    f"SELECT_DYNAMIC_DATASET = {elapsed:.4f}s"
)

print(
    "DATASET =",
    result.get("dataset", {}).get("id"),
)

print(
    "ERROR =",
    result.get("error"),
)
