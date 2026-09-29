import time
from graph import dynamic_nodes as d

question = "Show GST for April 2025"

original_rows = d.load_dataset_rows
original_column = d.load_dataset_column_values

row_calls = []
column_calls = []

def profile_rows(dataset_id):
    start = time.perf_counter()

    result = original_rows(dataset_id)

    elapsed = time.perf_counter() - start

    row_calls.append(
        (
            dataset_id,
            len(result) if isinstance(result, list) else -1,
            elapsed,
        )
    )

    return result


def profile_column(dataset_id, column_name):
    start = time.perf_counter()

    result = original_column(
        dataset_id,
        column_name,
    )

    elapsed = time.perf_counter() - start

    column_calls.append(
        (
            dataset_id,
            column_name,
            len(result) if isinstance(result, list) else -1,
            elapsed,
        )
    )

    return result


d.load_dataset_rows = profile_rows
d.load_dataset_column_values = profile_column

start = time.perf_counter()

result = d.select_dynamic_dataset(
    {
        "question": question,
    }
)

total = time.perf_counter() - start

print("--- SELECTOR DATABASE PROFILE ---")
print(
    f"TOTAL SELECTOR TIME = {total:.4f}s"
)

print()
print("--- FULL ROW LOAD CALLS ---")

if row_calls:
    for dataset_id, count, elapsed in row_calls:
        print(
            f"ID={dataset_id} "
            f"ROWS={count} "
            f"TIME={elapsed:.4f}s"
        )
else:
    print("NONE")

print()
print("--- COLUMN LOAD CALLS ---")

if column_calls:
    for dataset_id, column_name, count, elapsed in column_calls:
        print(
            f"ID={dataset_id} "
            f"COLUMN={column_name} "
            f"VALUES={count} "
            f"TIME={elapsed:.4f}s"
        )
else:
    print("NONE")

print()
print("--- RESULT ---")
print(
    "DATASET =",
    result.get("dataset", {}).get("id"),
)
print(
    "ERROR =",
    result.get("error"),
)

d.load_dataset_rows = original_rows
d.load_dataset_column_values = original_column
