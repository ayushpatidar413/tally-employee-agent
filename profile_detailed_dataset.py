import time
from graph import dynamic_nodes as d

datasets = d.get_all_dataset_context()

start = time.perf_counter()

results = []

for item in datasets:
    dataset = item.get("dataset", {})
    schema = item.get("schema", [])

    t = time.perf_counter()

    value = d._is_detailed_transaction_dataset(
        dataset,
        schema,
    )

    elapsed = time.perf_counter() - t

    results.append(
        (
            dataset.get("id"),
            dataset.get("row_count"),
            value,
            elapsed,
        )
    )

total = time.perf_counter() - start

print("--- DETAILED DATASET CHECK PROFILE ---")
print(
    f"TOTAL TIME = {total:.4f}s"
)

for dataset_id, row_count, value, elapsed in results:
    print(
        f"ID={dataset_id} "
        f"ROWS={row_count} "
        f"DETAILED={value} "
        f"TIME={elapsed:.4f}s"
    )
