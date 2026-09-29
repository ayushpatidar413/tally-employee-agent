from graph.dynamic_workflow import dynamic_agent

q = "Show product quantity for 08-2026"
r = dynamic_agent.invoke({"question": q})

print("INTENT            :", r.get("intent"))
print("AGGREGATE_FUNCTION:", r.get("aggregate_function"))
print("AGGREGATE_COLUMN  :", r.get("aggregate_column"))
print("REQUESTED_COLUMNS :", r.get("requested_columns"))
print("FILTERS           :", r.get("filters"))

result = r.get("result")
print("RESULT TYPE       :", type(result).__name__)

if isinstance(result, dict):
    print("RESULT KEYS       :", result.keys())
    print("OPERATION         :", result.get("operation"))
    print("COLUMN            :", result.get("column"))
    print("GROUP_BY          :", result.get("group_by"))
    print("VALUE             :", result.get("value"))
    print("FILTERED_ROWS     :", result.get("filtered_rows"))
    print("SOURCE_ROWS       :", result.get("source_rows"))
else:
    print("RESULT            :", result)
