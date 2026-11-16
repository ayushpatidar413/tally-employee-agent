import pandas as pd
from pathlib import Path
from graph.analytics_extra import handle

path = Path("test_data") / "Vyapar_Style_Accessories_Sales_Report.xlsx"
df = pd.read_excel(path, sheet_name="Sale Invoices")

queries = [
    # 1. Relative dates
    "What were the total sales and total profit for the latest month available in the data?",
    "Show me the top 3 products by quantity sold in the last month.",
    "Compare total sales of last month with the current month.",
    "Give me the year-to-date (YTD) total sales and tax.",

    # 2. Date ranges
    "Show total sales and profit between 1st April 2026 and 31st August 2026.",
    "What is the total quantity sold from 15th August to 25th August?",
    "List the top 5 customers by invoice total between Jan 2026 and March 2026.",
    "Show month-wise profit between Q1 and Q2 of the current year.",

    # 3. Multi-metric and conditions
    "Show me the customers where the total profit is greater than 50000.",
    "What are the total sales for Cash payment mode between May and July 2026?",
    "Which products generated more than 10000 in sales but had less than 1000 in discount?",
    "Show me the average invoice total for transactions where the tax is above 500.",

    # 4. Grouping and calculations
    "Give me a month-wise breakdown of both sales and profit for the year 2026.",
    "Show customer-wise average discount and total profit for last month.",
    "Which payment mode has the highest average invoice total?",
    "Show the category-wise sales distribution for the last 3 months.",

    # 5. Edge cases
    "Show sales between 30th February and 10th March.",
    "What is the total profit for the next month?",
    "Show me the total profit between 2020 and 2021.",
]

print("DATASET SHAPE:", df.shape)
print("DATE RANGE:")
if "Date" in df.columns:
    dates = pd.to_datetime(df["Date"], errors="coerce").dropna()
    print("Earliest:", dates.min(), "| Latest:", dates.max())

for i, q in enumerate(queries, start=1):
    print("\n" + "=" * 100)
    print(f"TEST {i}/{len(queries)}: {q}")

    try:
        response = handle(q, df)

        if not response:
            print("STATUS: NO RESULT")
            continue

        result = response.get("result", {})
        if not isinstance(result, dict):
            print("STATUS: UNEXPECTED RESULT TYPE")
            print(repr(result)[:1200])
            continue

        table = result.get("table", [])
        print("STATUS: RESULT RETURNED")
        print("RESULT KEYS:", list(result.keys()))
        print("FILTERED ROWS:", result.get("filtered_rows"))
        print("VALUE:", result.get("value"))
        print("TOTAL VALUE:", result.get("total_value"))
        print("ANSWER:", str(result.get("engine_answer", ""))[:500])
        print("TABLE ROWS:", len(table) if isinstance(table, list) else "not a list")

        if isinstance(table, list) and table:
            print("SAMPLE:")
            print(pd.DataFrame(table).head(5).to_string(index=False))

    except Exception as exc:
        print("STATUS: EXCEPTION")
        print("ERROR:", type(exc).__name__, str(exc))

print("\n" + "=" * 100)
print("DIAGNOSTIC RUN COMPLETE")
