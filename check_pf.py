from database.database import get_connection


connection = get_connection()

rows = connection.execute(
    """
    SELECT
        employee_id,
        employee_name,
        month,
        year,
        pf_applicable,
        pf_rate,
        pf_wage,
        employee_pf,
        employer_pf,
        total_pf,
        pf_status
    FROM pf_records
    WHERE employee_id = ?
    """,
    ("EMP001",)
).fetchall()


print("=" * 70)
print("RAJESH SHARMA PF RECORDS")
print("=" * 70)

for row in rows:
    print(dict(row))

print()
print("COUNT:", len(rows))

connection.close()
