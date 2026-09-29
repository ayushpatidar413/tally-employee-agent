import sqlite3

DB_PATH = "database/hr_uploads.db"

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

# Check duplicate Employee IDs
duplicates = cursor.execute(
    """
    SELECT employee_id, COUNT(*)
    FROM uploaded_employees
    GROUP BY employee_id
    HAVING COUNT(*) > 1
    """
).fetchall()

print("DUPLICATES:", duplicates)

if duplicates:
    print()
    print("Duplicate Employee IDs exist.")
    print("Do not create the unique index yet.")
    print("Send me this output.")
else:
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_uploaded_employee_id
        ON uploaded_employees(employee_id)
        """
    )

    connection.commit()

    print()
    print("UNIQUE INDEX CREATED")

    indexes = cursor.execute(
        "PRAGMA index_list('uploaded_employees')"
    ).fetchall()

    print("INDEXES:")
    for index in indexes:
        print(index)

connection.close()