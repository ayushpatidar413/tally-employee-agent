from database.database import get_connection


def get_employee_monthly_summary(employee_name):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM monthly_summary
        WHERE LOWER(employee_name) LIKE LOWER(?)
        """,
        (f"%{employee_name}%",)
    )

    row = cursor.fetchone()
    connection.close()

    if row is None:
        return None

    return dict(row)


def get_all_employee_summaries():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM monthly_summary
        ORDER BY employee_name
        """
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def get_low_attendance_employees(limit=20):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM monthly_summary
        WHERE attendance_percentage < 80
        ORDER BY attendance_percentage ASC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def get_most_experienced_employees(limit=10):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM monthly_summary
        ORDER BY total_experience DESC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


if __name__ == "__main__":
    print("=" * 70)
    print("MONTHLY SUMMARY DATABASE TOOL TEST")
    print("=" * 70)

    records = get_all_employee_summaries()

    print("\nTotal employees:", len(records))

    if records:
        employee_name = records[0]["employee_name"]

        print("\nFirst employee:")
        print(get_employee_monthly_summary(employee_name))

    print("\nEmployees below 80% attendance:")

    low_attendance = get_low_attendance_employees()

    for employee in low_attendance[:10]:
        print(
            employee["employee_name"],
            "=>",
            employee["attendance_percentage"]
        )

    print("\nMost experienced employees:")

    experienced = get_most_experienced_employees()

    for employee in experienced:
        print(
            employee["employee_name"],
            "=>",
            employee["total_experience"]
        )

    print("\n" + "=" * 70)
    print("SUMMARY TOOL TEST COMPLETED")
    print("=" * 70)