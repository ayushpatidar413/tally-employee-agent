from database.database import get_connection


def get_employee_leaves(employee_name):
    """
    Get all leave records for an employee.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM leaves
        WHERE LOWER(employee_name) LIKE LOWER(?)
        ORDER BY leave_date
        """,
        (f"%{employee_name}%",)
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


def get_leave_summary(employee_name):
    """
    Get paid and unpaid leave summary.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_leave_records,

            COALESCE(
                SUM(
                    CASE
                        WHEN LOWER(paid_unpaid) = 'paid'
                        THEN leave_days
                        ELSE 0
                    END
                ),
                0
            ) AS paid_leave_days,

            COALESCE(
                SUM(
                    CASE
                        WHEN LOWER(paid_unpaid) = 'unpaid'
                        THEN leave_days
                        ELSE 0
                    END
                ),
                0
            ) AS unpaid_leave_days

        FROM leaves

        WHERE LOWER(employee_name) LIKE LOWER(?)
        """,
        (f"%{employee_name}%",)
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)


def get_unpaid_leaves():
    """
    Get all unpaid leave records.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM leaves
        WHERE LOWER(paid_unpaid) = 'unpaid'
        ORDER BY employee_name
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]

def get_leave_ranking(limit=5, order="DESC"):
    """
    Rank employees by total leave days.

    DESC = highest leave first
    ASC  = lowest leave first
    """

    if order.upper() not in ("ASC", "DESC"):
        order = "DESC"

    limit = max(1, int(limit))

    connection = get_connection()
    cursor = connection.cursor()

    query = f"""
        SELECT
            employee_name,
            COUNT(*) AS leave_records,
            COALESCE(SUM(leave_days), 0) AS total_leave_days
        FROM leaves
        GROUP BY employee_name
        ORDER BY total_leave_days {order}
        LIMIT ?
    """

    cursor.execute(query, (limit,))

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]

def get_employees_by_leave_days(leave_days):
    """
    Get employees whose total leave days exactly match
    the requested number of leave days.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            employee_name,
            COUNT(*) AS leave_records,
            COALESCE(SUM(leave_days), 0) AS total_leave_days
        FROM leaves
        GROUP BY employee_name
        HAVING SUM(leave_days) = ?
        ORDER BY employee_name
        """,
        (leave_days,)
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


if __name__ == "__main__":

    print("=" * 70)
    print("LEAVE DATABASE TOOL TEST")
    print("=" * 70)

    print("\nTesting unpaid leave records...")

    records = get_unpaid_leaves()

    print("Total unpaid leave records:", len(records))

    print("\nFirst 5 records:")

    for record in records[:5]:
        print(record)

    print("\n" + "=" * 70)
    print("LEAVE TOOL TEST COMPLETED")
    print("=" * 70)