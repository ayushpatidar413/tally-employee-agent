import pandas as pd
from pathlib import Path
from graph.analytics_extra import handle

df = pd.read_excel(
    Path("test_data") / "Vyapar_Style_Accessories_Sales_Report.xlsx",
    sheet_name="Sale Invoices"
)

queries = [
    "Show total sales between 15-08-2026 to 30-08-2026",
    "Show sales for 15 August 2026",
    "Show total sales month wise",
    "Show quantity and sales product wise",
    "Show invoice count and discount year wise",
]

for q in queries:
    print("\n" + "=" * 90)
    print("QUERY:", q)

    r = handle(q, df)

    if not r:
        print("NO RESULT")
        continue

    result = r.get("result", {})
    print("Filtered rows:", result.get("filtered_rows"))
    print("Result keys:", list(result.keys()))

    table = result.get("table", [])
    if table:
        print(pd.DataFrame(table).to_string(index=False))
    else:
        print("No table rows returned")
