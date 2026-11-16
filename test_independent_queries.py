import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from graph.dynamic_workflow import dynamic_agent

queries = [
    "Which individual party/customer contributed the highest revenue percentage to the Smart Watch product overall, and what was their exact spending amount on that product?",
    "Which single calendar month recorded the highest total gross sales in the entire dataset, and what were the top 2 revenue-generating categories in that specific month?",
    "Track the quarter-over-quarter gross sales revenue of B2B Dealers across all 4 quarters of FY2025-26 Q1 Q2 Q3 Q4 and specify which quarter had the highest revenue drop compared to its preceding quarter"
]

for i, q in enumerate(queries, 1):
    print("\n" + "=" * 100)
    print(f"QUERY {i}: {q}")

    try:
        r = dynamic_agent.invoke({"question": q})

        print("\nANSWER:", r.get("answer"))
        print("\nRESULT:", r.get("result"))
        print("\nINTENT:", r.get("intent"))
        print("\nGROUP_BY:", r.get("group_by"))
        print("\nAGGREGATE:", r.get("aggregate_function"))

    except Exception as e:
        print("\nQUERY ERROR:", repr(e))
