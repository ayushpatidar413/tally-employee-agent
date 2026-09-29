from graph.dynamic_workflow import dynamic_agent

questions = [
    "Show profit 15-08-2026",
    "Show product quantity for 08-2026",
]

for q in questions:
    print("\n" + "=" * 80)
    print("QUESTION:", q)
    print("=" * 80)

    r = dynamic_agent.invoke({"question": q})

    print("INTENT       :", r.get("intent"))
    print("GROUP_BY     :", r.get("group_by"))
    print("AGGREGATE    :", r.get("aggregate_function"))
    print("DATE_FILTERS :", r.get("date_filters"))
    print("COLUMN       :", r.get("column"))
    print("RESULT       :", r.get("result"))
