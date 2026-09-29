from graph.workflow import hr_graph


print("=" * 70)
print("LANGGRAPH HR QUERY TEST")
print("=" * 70)


query = "Complete sales report"


print("\nUser Query:")
print(query)


result = hr_graph.invoke(
    {
        "user_query": query
    },
    config={
        "configurable": {
            "thread_id": "test-session"
        }
    }
)

print("\n" + "=" * 70)
print("GRAPH RESULT")
print("=" * 70)


print("\nEmployee ID:")
print(result.get("employee_id"))

print("\nEmployee Name:")
print(result.get("employee_name"))

print("\nIntent:")
print(result.get("intent"))

print("\nSalary Data:")
print(result.get("salary_data"))

print("\nFinal Answer:")
print(result.get("final_answer"))


print("\n" + "=" * 70)
print("TEST COMPLETED")
print("=" * 70)