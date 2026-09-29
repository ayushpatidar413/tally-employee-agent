import sqlite3

connection = sqlite3.connect("database/hr_uploads.db")

cursor = connection.cursor()

query = """
SELECT
    employee_id,
    length(employee_id),
    hex(employee_id),
    employee_name
FROM uploaded_employees
WHERE employee_name = ?
"""

cursor.execute(query, ("Pooja Chopra",))

rows = cursor.fetchall()

print("\nDATABASE RESULT")
print("=" * 60)

for row in rows:
    print("Employee ID :", repr(row[0]))
    print("Length      :", row[1])
    print("HEX         :", row[2])
    print("Employee    :", row[3])

connection.close()