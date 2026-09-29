import cProfile
import pstats

from graph import dynamic_nodes as d

question = "Show GST for April 2025"

profiler = cProfile.Profile()

profiler.enable()

result = d.select_dynamic_dataset(
    {
        "question": question,
    }
)

profiler.disable()

print("--- RESULT ---")
print("DATASET =", result.get("dataset", {}).get("id"))
print("ERROR =", result.get("error"))

print()
print("--- CPROFILE TOP FUNCTIONS ---")

stats = pstats.Stats(profiler)

stats.sort_stats("cumulative")
stats.print_stats(30)
