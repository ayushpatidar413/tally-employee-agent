import sqlite3
import json

from graph.dynamic_nodes import _extract_aggregate

con = sqlite3.connect("database/dynamic_data.db")
cur = con.cursor()

# Dataset metadata
cur.execute("""
SELECT *
FROM datasets
WHERE id = 22
""")

dataset_row = cur.fetchone()
dataset_columns = [desc[0] for desc in cur.description]
dataset = dict(zip(dataset_columns, dataset_row))

# Schema
cur.execute("""
SELECT *
FROM dataset_schema
WHERE dataset_id = 22
""")

schema_rows = cur.fetchall()
schema_columns = [desc[0] for desc in cur.description]

schema = [
    dict(zip(schema_columns, row))
    for row in schema_rows
]

# Data rows
cur.execute("""
SELECT row_data_json
FROM dataset_rows
WHERE dataset_id = 22
""")

rows = [
    json.loads(row[0])
    for row in cur.fetchall()
]

questions = [
    "Show total profit",
    "Show profit for April 2025",
    "Show total profit for April 2025",
]

print("DATASET =", dataset.get("original_filename"))
print("ROWS =", len(rows))
print()

for question in questions:
    result = _extract_aggregate(
        question,
        dataset,
        schema,
        rows,
    )

    print(question)
    print("AGGREGATE =", result)
    print()

con.close()
