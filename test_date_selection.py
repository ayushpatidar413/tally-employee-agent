import time
from graph.dynamic_nodes import select_dynamic_dataset

queries = [
    "Show sales for August 2026",
    "Show sales for September 2026",
    "Show sales for September",
]

print("--- DATE SELECTION PERFORMANCE ---")

for question in queries:
    start = time.perf_counter()

    result = select_dynamic_dataset({
        "question": question
    })

    elapsed = time.perf_counter() - start

    dataset = result.get("dataset", {})

    if isinstance(dataset, dict):
        dataset_id = dataset.get("id")
    else:
        dataset_id = None

    print(f"QUESTION = {question}")
    print(f"DATASET = {dataset_id}")
    print(f"ERROR = {result.get('error')}")
    print(f"TIME = {elapsed:.4f}s")
    print("-" * 60)
