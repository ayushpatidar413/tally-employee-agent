
from graph.dynamic_workflow import dynamic_agent

queries = [
    "Show total sales year wise",
    "Show invoice count year wise",
    "Show discount year wise"
]

for q in queries:
    print("\n===== ", q, " =====")
    r = dynamic_agent.invoke({"question": q})

    for key in ["operation", "metrics", "aggregate", "group_by", "result", "answer"]:
        print(key.upper(), ":", r.get(key))