import time
from graph import dynamic_nodes as d

question = "Show GST for April 2025"

original_extract_date_filters = d._extract_date_filters

def no_date_filters(*args, **kwargs):
    return []

d._extract_date_filters = no_date_filters

start = time.perf_counter()

result = d.select_dynamic_dataset(
    {
        "question": question,
    }
)

elapsed = time.perf_counter() - start

print("--- SELECTOR WITHOUT DATE SAFETY ---")
print(f"TIME = {elapsed:.4f}s")
print("DATASET =", result.get("dataset", {}).get("id"))
print("ERROR =", result.get("error"))

d._extract_date_filters = original_extract_date_filters
