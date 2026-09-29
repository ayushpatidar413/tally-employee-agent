from database.database import get_connection


def get_attendance_summary(
    employee_id: str,
    month: int = None,
    year: int = None
):
    """
    Get attendance summary for an employee.

    If month and year are provided,
    return attendance only for that month.

    Example:
    get_attendance_summary("EMP001", 8, 2026)
    """

    connection = get_connection()
    cursor = connection.cursor()

    query = """
        SELECT
            COUNT(*) AS total_records,

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

        WHERE employee_id = ?
    """

    parameters = [employee_id]

    # ---------------------------------------------------------
    # MONTH FILTER
    # ---------------------------------------------------------

    if month is not None and year is not None:

        query += """
            AND strftime('%m', date) = ?
            AND strftime('%Y', date) = ?
        """

        parameters.append(f"{month:02d}")
        parameters.append(str(year))

    cursor.execute(query, parameters)

    row = cursor.fetchone()

    connection.close()

    if not row:
        return {
            "success": False,
            "message": f"No attendance data found for {employee_id}."
        }

    return {
        "success": True,
        "employee_id": employee_id,
        "month": month,
        "year": year,
        "total_records": row["total_records"] or 0,
        "present_days": row["present_days"] or 0,
        "absent_days": row["absent_days"] or 0,
        "leave_days": row["leave_days"] or 0,
        "half_days": row["half_days"] or 0,
        "weekly_offs": row["weekly_offs"] or 0
    }


def get_employee_attendance(
    employee_id: str,
    month: int = None,
    year: int = None
):
    """
    Get detailed attendance records for an employee.
    Optional month/year filtering is supported.
    """

    connection = get_connection()
    cursor = connection.cursor()

    query = """
        SELECT
            employee_id,
            employee_name,
            department,
            date,
            day,
            attendance_status,
            check_in,
            check_out,
            working_hours,
            leave_type,
            remarks

        FROM attendance

        WHERE employee_id = ?
    """

    parameters = [employee_id]

    if month is not None and year is not None:

        query += """
            AND strftime('%m', date) = ?
            AND strftime('%Y', date) = ?
        """

        parameters.append(f"{month:02d}")
        parameters.append(str(year))

    query += """
        ORDER BY date
    """

    cursor.execute(query, parameters)

    rows = cursor.fetchall()

    connection.close()

    records = []

    for row in rows:

        records.append({
            "employee_id": row["employee_id"],
            "employee_name": row["employee_name"],
            "department": row["department"],
            "date": row["date"],
            "day": row["day"],
            "attendance_status": row["attendance_status"],
            "check_in": row["check_in"],
            "check_out": row["check_out"],
            "working_hours": row["working_hours"],
            "leave_type": row["leave_type"],
            "remarks": row["remarks"]
        })

    return {
        "success": True,
        "employee_id": employee_id,
        "month": month,
        "year": year,
        "count": len(records),
        "attendance": records
    }


def get_attendance_by_date(
    employee_id: str,
    attendance_date: str
):
    """
    Get attendance for an employee on a specific date.

    Example:
    get_attendance_by_date(
        "EMP001",
        "2026-08-15"
    )
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            employee_id,
            employee_name,
            department,
            date,
            day,
            attendance_status,
            check_in,
            check_out,
            working_hours,
            leave_type,
            remarks

        FROM attendance

        WHERE employee_id = ?
        AND date = ?
        """,
        (
            employee_id,
            attendance_date
        )
    )

    rows = cursor.fetchall()

    connection.close()

    if not rows:

        return {
            "success": False,
            "message": (
                f"No attendance found for "
                f"{employee_id} on {attendance_date}."
            )
        }

    records = []

    for row in rows:

        records.append({
            "employee_id": row["employee_id"],
            "employee_name": row["employee_name"],
            "department": row["department"],
            "date": row["date"],
            "day": row["day"],
            "attendance_status": row["attendance_status"],
            "check_in": row["check_in"],
            "check_out": row["check_out"],
            "working_hours": row["working_hours"],
            "leave_type": row["leave_type"],
            "remarks": row["remarks"]
        })

    return {
        "success": True,
        "employee_id": employee_id,
        "date": attendance_date,
        "attendance": records
    }