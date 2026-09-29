from graph.dynamic_workflow import dynamic_agent

q = "Show product quantity for 08-2026"
r = dynamic_agent.invoke({"question": q})

print("INTENT            :", r.get("intent"))
print("AGGREGATE_FUNCTION:", r.get("aggregate_function"))
print("AGGREGATE_COLUMN  :", r.get("aggregate_column"))
print("REQUESTED_COLUMNS :", r.get("requested_columns"))
print("FILTERS           :", r.get("filters"))
print("ANSWER            :", r.get("answer"))
print("RESULT            :", r.get("result"))
