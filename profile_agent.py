import cProfile
import pstats

from graph.dynamic_workflow import dynamic_agent

profiler = cProfile.Profile()

profiler.enable()

result = dynamic_agent.invoke({
    "question": "Show total sales"
})

profiler.disable()

print("\n========== RESULT ==========")
print("DATASET =", (result.get("dataset") or {}).get("id"))
print("ANSWER =", result.get("answer") or result.get("final_answer"))
print("ERROR =", result.get("error"))

print("\n========== PROFILE ==========")
import cProfile
import pstats

from graph.dynamic_workflow import dynamic_agent


profiler = cProfile.Profile()

profiler.enable()

result = dynamic_agent.invoke({
    "question": "Show total sales"
})

profiler.disable()

print("\n========== RESULT ==========")
print(
    "DATASET =",
    (result.get("dataset") or {}).get("id")
)
print(
    "ANSWER =",
    result.get("answer")
    or result.get("final_answer")
)
print(
    "ERROR =",
    result.get("error")
)

print("\n========== PROFILE ==========")

stats = pstats.Stats(profiler)

stats.sort_stats("cumulative")

stats.print_stats(30)
stats = pstats.Stats(profiler)

stats.sort_stats("cumulative")

stats.print_stats(30)
