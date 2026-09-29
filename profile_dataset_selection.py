import time
from graph import dynamic_nodes as d

question = "Show sales for August 2026"

datasets = d.get_all_dataset_context()

print("--- DATASET SELECTION PROFILE ---")

start = time.perf_counter()

scores = []

for item in datasets:
    dataset = item.get("dataset", {})
    schema = item.get("schema", [])

    t = time.perf_counter()

    score = d._score_dataset(
        question,
        dataset,
        schema,
    )

    elapsed = time.perf_counter() - t

    scores.append(
        (
            score,
            dataset.get("id"),
            elapsed,
        )
    )

print(
    "ALL _score_dataset TIME =",
    round(time.perf_counter() - start, 4),
    "sec",
)

print()
print("TOP SCORES:")

for score, dataset_id, elapsed in sorted(
    scores,
    reverse=True,
)[:10]:
    print(
        f"ID={dataset_id} "
        f"SCORE={score} "
        f"TIME={elapsed:.4f}s"
    )

print()
print("--- DATE FILTER EXTRACTION ---")

for item in datasets:
    dataset = item.get("dataset", {})
    schema = item.get("schema", [])

    t = time.perf_counter()

    filters = d._extract_date_filters(
        question,
        dataset,
        schema,
        [],
    )

    elapsed = time.perf_counter() - t

    if filters:
        print(
            f"ID={dataset.get('id')} "
            f"TIME={elapsed:.4f}s "
            f"FILTERS={filters}"
        )

print()
print(
    "TOTAL PROFILE TIME =",
    round(time.perf_counter() - start, 4),
    "sec",
)
