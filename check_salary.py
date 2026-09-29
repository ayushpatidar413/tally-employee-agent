from database.database import get_connection


connection = get_connection()

rows = connection.execute(
    """
    SELECT
        employee_id,
        employee_name,
        month,
        year,
        net_salary
    FROM salary
    WHERE employee_id = ?
    """,
    ("EMP001",)
).fetchall()


print("=" * 70)
print("RAJESH SHARMA SALARY RECORDS")
print("=" * 70)

for row in rows:
    print(dict(row))

print()
print("COUNT:", len(rows))

connection.close()