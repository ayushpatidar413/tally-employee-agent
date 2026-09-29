import sqlite3
import json
from collections import Counter

con = sqlite3.connect("database/dynamic_data.db")
cur = con.cursor()

cur.execute("""
SELECT row_data_json
FROM dataset_rows
WHERE dataset_id = 22
""")

rows = cur.fetchall()

payment_modes = Counter()

for row in rows:
    data = json.loads(row[0])
    payment_mode = data.get("PaymentMode")

    if payment_mode is None:
        payment_mode = "<NULL>"

    payment_modes[str(payment_mode).strip()] += 1

print("TOTAL ROWS:", len(rows))
print()
print("PAYMENT MODES:")

for mode, count in payment_modes.most_common():
    print(f"{mode}: {count}")

con.close()
