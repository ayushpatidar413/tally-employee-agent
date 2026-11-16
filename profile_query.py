import cProfile
import pstats

from graph.dynamic_workflow import dynamic_agent

cProfile.runctx(
    "dynamic_agent.invoke({'question': 'Show quantity and sales product wise'})",
    globals(),
    locals(),
    "profile.stats",
)

p = pstats.Stats("profile.stats")
p.strip_dirs().sort_stats("cumulative").print_stats(25)
