from database.database import get_connection


connection = get_connection()

print("=" * 70)
print("SALARY RECORD ANALYSIS")
print("=" * 70)

rows = connection.execute(
    """
    SELECT
        employee_id,
        employee_name,
        month,
        year,
        COUNT(*) AS record_count
    FROM salary
    GROUP BY employee_id, month, year
    ORDER BY employee_id, year, month
    """
).fetchall()

print("Unique employee/month/year combinations:", len(rows))

print("\nFirst 20 salary combinations:")
for row in rows[:20]:
    print(dict(row))


print()
print("=" * 70)
print("PF RECORD ANALYSIS")
print("=" * 70)

rows = connection.execute(
    """
    SELECT
        employee_id,
        employee_name,
        month,
        year,
        COUNT(*) AS record_count
    FROM pf_records
    GROUP BY employee_id, month, year
    ORDER BY employee_id, year, month
    """
).fetchall()

print("Unique employee/month/year combinations:", len(rows))

print("\nFirst 20 PF combinations:")
for row in rows[:20]:
    print(dict(row))


print()
print("=" * 70)
print("EMP001 SALARY")
print("=" * 70)

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
    ORDER BY year, month
    """,
    ("EMP001",),
).fetchall()

for row in rows:
    print(dict(row))


print()
print("=" * 70)
print("EMP001 PF")
print("=" * 70)

rows = connection.execute(
    """
    SELECT
        employee_id,
        employee_name,
        month,
        year,
        employee_pf,
        employer_pf,
        total_pf
    FROM pf_records
    WHERE employee_id = ?
    ORDER BY year, month
    """,
    ("EMP001",),
).fetchall()

for row in rows:
    print(dict(row))


connection.close()