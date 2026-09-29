import time
from graph import dynamic_nodes as d

original_column_loader = d.load_dataset_column_values
original_row_loader = d.load_dataset_rows

column_calls = []
row_calls = []

def timed_column_loader(dataset_id, column_name):
    start = time.perf_counter()

    result = original_column_loader(
        dataset_id,
        column_name,
    )

    elapsed = time.perf_counter() - start

    column_calls.append(
        (
            dataset_id,
            column_name,
            elapsed,
            len(result),
        )
    )

    return result


def timed_row_loader(dataset_id):
    start = time.perf_counter()

    result = original_row_loader(
        dataset_id,
    )

    elapsed = time.perf_counter() - start

    row_calls.append(
        (
            dataset_id,
            elapsed,
            len(result),
        )
    )

    return result


d.load_dataset_column_values = timed_column_loader
d.load_dataset_rows = timed_row_loader

question = "Show sales for August 2026"

start = time.perf_counter()

result = d.select_dynamic_dataset({
    "question": question
})

total = time.perf_counter() - start

print("--- SELECT DATASET DATABASE PROFILE ---")
print(f"TOTAL SELECT TIME = {total:.4f}s")

print()
print("--- COLUMN LOADS ---")

for dataset_id, column_name, elapsed, count in column_calls:
    print(
        f"ID={dataset_id} "
        f"COLUMN={column_name} "
        f"ROWS={count} "
        f"TIME={elapsed:.4f}s"
    )

print()
print(
    "TOTAL COLUMN LOAD TIME =",
    round(
        sum(item[2] for item in column_calls),
        4,
    ),
    "sec",
)

print()
print("--- FULL ROW LOADS ---")

for dataset_id, elapsed, count in row_calls:
    print(
        f"ID={dataset_id} "
        f"ROWS={count} "
        f"TIME={elapsed:.4f}s"
    )

print()
print(
    "TOTAL FULL ROW LOAD TIME =",
    round(
        sum(item[1] for item in row_calls),
        4,
    ),
    "sec",
)

print()
print(
    "SELECTED DATASET =",
    result.get("dataset", {}).get("id")
    if isinstance(result.get("dataset"), dict)
    else None,
)
