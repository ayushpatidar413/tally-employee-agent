from database.database import get_connection


connection = get_connection()
cursor = connection.cursor()

print("=" * 70)
print("ATTENDANCE DUPLICATE CLEANUP")
print("=" * 70)


# ---------------------------------------------------------
# CHECK RECORD COUNT BEFORE CLEANUP
# ---------------------------------------------------------

cursor.execute("""
    SELECT COUNT(*)
    FROM attendance
    WHERE employee_id = 'EMP001'
    AND date LIKE '2026-08%'
""")

before_count = cursor.fetchone()[0]

print(f"\nRecords before cleanup: {before_count}")


# ---------------------------------------------------------
# REMOVE DUPLICATES
# Keep the first record for each employee + date
# ---------------------------------------------------------

cursor.execute("""
    DELETE FROM attendance
    WHERE employee_id = 'EMP001'
    AND date LIKE '2026-08%'
    AND rowid NOT IN (
        SELECT MIN(rowid)
        FROM attendance
        WHERE employee_id = 'EMP001'
        AND date LIKE '2026-08%'
        GROUP BY employee_id, date
    )
""")

deleted_count = cursor.rowcount

connection.commit()


# ---------------------------------------------------------
# CHECK RECORD COUNT AFTER CLEANUP
# ---------------------------------------------------------

cursor.execute("""
    SELECT COUNT(*)
    FROM attendance
    WHERE employee_id = 'EMP001'
    AND date LIKE '2026-08%'
""")

after_count = cursor.fetchone()[0]


print(f"Duplicate records deleted: {deleted_count}")
print(f"Records after cleanup: {after_count}")


# ---------------------------------------------------------
# SHOW FINAL ATTENDANCE SUMMARY
# ---------------------------------------------------------

cursor.execute("""
    SELECT
        SUM(
            CASE
                WHEN attendance_status = 'Present'
                THEN 1 ELSE 0
            END
        ) AS present_days,

        SUM(
            CASE
                WHEN attendance_status = 'Absent'
                THEN 1 ELSE 0
            END
        ) AS absent_days,

        SUM(
            CASE
                WHEN attendance_status = 'Leave'
                THEN 1 ELSE 0
            END
        ) AS leave_days,

        SUM(
            CASE
                WHEN attendance_status = 'Half Day'
                THEN 1 ELSE 0
            END
        ) AS half_days,

        SUM(
            CASE
                WHEN attendance_status = 'Weekly Off'
                THEN 1 ELSE 0
            END
        ) AS weekly_offs

    FROM attendance

    WHERE employee_id = 'EMP001'
    AND date LIKE '2026-08%'
""")

summary = cursor.fetchone()

print("\nAugust 2026 Attendance:")
print(f"Present Days : {summary['present_days'] or 0}")
print(f"Absent Days  : {summary['absent_days'] or 0}")
print(f"Leave Days   : {summary['leave_days'] or 0}")
print(f"Half Days    : {summary['half_days'] or 0}")
print(f"Weekly Offs  : {summary['weekly_offs'] or 0}")

print("\n" + "=" * 70)
print("CLEANUP COMPLETED")
print("=" * 70)

connection.close()