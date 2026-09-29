import sqlite3
import json

con = sqlite3.connect("database/dynamic_data.db")
cur = con.cursor()

cur.execute("""
SELECT row_data_json
FROM dataset_rows
WHERE dataset_id = 22
""")

rows = [json.loads(row[0]) for row in cur.fetchall()]

april_rows = [
    row for row in rows
    if str(row.get("Date", "")).startswith("2025-04")
]

total_profit = sum(
    float(row.get("Profit", 0) or 0)
    for row in april_rows
)

print("APRIL ROWS =", len(april_rows))
print("APRIL PROFIT =", round(total_profit, 2))

con.close()
