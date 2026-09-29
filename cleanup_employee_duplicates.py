import sqlite3

DB_PATH = "database/hr_uploads.db"

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

print("=" * 70)
print("CLEANING DUPLICATE EMPLOYEE RECORDS")
print("=" * 70)

# Count before cleanup
before = cursor.execute(
    "SELECT COUNT(*) FROM uploaded_employees"
).fetchone()[0]

print(f"\nRecords before cleanup: {before}")

# Keep the latest record for every Employee ID.
# The highest id is treated as the latest uploaded record.
cursor.execute(
    """
    DELETE FROM uploaded_employees
    WHERE id NOT IN (
        SELECT MAX(id)
        FROM uploaded_employees
        WHERE employee_id IS NOT NULL
          AND TRIM(employee_id) != ''
        GROUP BY employee_id
    )
    """
)

deleted = cursor.rowcount

connection.commit()

# Count after cleanup
after = cursor.execute(
    "SELECT COUNT(*) FROM uploaded_employees"
).fetchone()[0]

print(f"Duplicate records deleted: {deleted}")
print(f"Records after cleanup: {after}")

# Check duplicates again
duplicates = cursor.execute(
    """
    SELECT employee_id, COUNT(*)
    FROM uploaded_employees
    GROUP BY employee_id
    HAVING COUNT(*) > 1
    """
).fetchall()

print()

if duplicates:
    print("DUPLICATES STILL EXIST:")
    for row in duplicates:
        print(row)
else:
    print("No duplicate Employee IDs remain.")

# Show some employees
print("\nSample employees:")

rows = cursor.execute(
    """
    SELECT employee_id, employee_name, monthly_salary, id
    FROM uploaded_employees
    ORDER BY id
    LIMIT 10
    """
).fetchall()

for row in rows:
    print(row)

connection.close()

print("\nCleanup completed.")