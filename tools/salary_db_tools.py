from database.database import get_connection


# ============================================================
# GET SALARY RECORD
# ============================================================

def get_salary_record(
    employee_name,
    month=None,
    year=None
):
    """
    Get salary record for an employee.

    If month and year are provided,
    the salary record is filtered by month and year.

    If month/year are not provided,
    the latest available salary record is returned.
    """

    connection = get_connection()
    cursor = connection.cursor()

    # --------------------------------------------------------
    # Month + Year filter
    # --------------------------------------------------------

    if month is not None and year is not None:

        cursor.execute(
            """
            SELECT *
            FROM salary
            WHERE LOWER(employee_name) LIKE LOWER(?)
            AND LOWER(month) = LOWER(?)
            AND year = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                f"%{employee_name}%",
                str(month),
                year
            )
        )

    # --------------------------------------------------------
    # Employee only
    # --------------------------------------------------------

    else:

        cursor.execute(
            """
            SELECT *
            FROM salary
            WHERE LOWER(employee_name) LIKE LOWER(?)
            ORDER BY year DESC, id DESC
            LIMIT 1
            """,
            (
                f"%{employee_name}%",
            )
        )

    row = cursor.fetchone()

    connection.close()

    if row is None:

        return None

    return dict(row)


# ============================================================
# GET SALARY SUMMARY
# ============================================================

def get_salary_summary(
    employee_name,
    month=None,
    year=None
):
    """
    Get salary summary for an employee.

    Optional month/year filtering is supported.
    """

    record = get_salary_record(
        employee_name,
        month,
        year
    )

    if record is None:

        return None

    return {
        "employee_id": record["employee_id"],
        "employee_name": record["employee_name"],
        "month": record["month"],
        "year": record["year"],
        "monthly_salary": record["monthly_salary"],
        "working_days": record["working_days"],
        "present_days": record["present_days"],
        "absent_days": record["absent_days"],
        "leave_days": record["leave_days"],
        "half_days": record["half_days"],
        "free_leave_days": record["free_leave_days"],
        "unpaid_absence_days": record["unpaid_absence_days"],
        "per_day_salary": record["per_day_salary"],
        "gross_salary": record["gross_salary"],
        "absence_deduction": record["absence_deduction"],
        "leave_deduction": record["leave_deduction"],
        "employee_pf": record["employee_pf"],
        "other_deduction": record["other_deduction"],
        "net_salary": record["net_salary"],
    }


# ============================================================
# SALARY DEDUCTION REASON
# ============================================================

def get_salary_deduction_reason(
    employee_name,
    month=None,
    year=None
):
    """
    Explain salary deductions.

    Optional month/year filtering is supported.
    """

    salary = get_salary_summary(
        employee_name,
        month,
        year
    )

    if salary is None:

        return None

    total_deduction = (
        float(salary["absence_deduction"] or 0)
        + float(salary["leave_deduction"] or 0)
        + float(salary["employee_pf"] or 0)
        + float(salary["other_deduction"] or 0)
    )

    return {
        "employee_name": salary["employee_name"],
        "monthly_salary": salary["monthly_salary"],
        "month": salary["month"],
        "year": salary["year"],
        "absent_days": salary["absent_days"],
        "free_leave_days": salary["free_leave_days"],
        "unpaid_absence_days": salary["unpaid_absence_days"],
        "absence_deduction": salary["absence_deduction"],
        "leave_deduction": salary["leave_deduction"],
        "employee_pf": salary["employee_pf"],
        "other_deduction": salary["other_deduction"],
        "total_deductions": total_deduction,
        "net_salary": salary["net_salary"],
    }


# ============================================================
# HIGHEST SALARY EMPLOYEE
# ============================================================

def get_highest_salary_employee():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM salary
        ORDER BY monthly_salary DESC
        LIMIT 1
        """
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:

        return None

    return dict(row)
def get_salary_ranking(limit=5, order="DESC"):
    """
    Get employees ranked by monthly salary.

    limit:
        Number of employees to return.

    order:
        DESC = highest salary first
        ASC  = lowest salary first
    """

    if order.upper() not in ("ASC", "DESC"):
        order = "DESC"

    limit = max(1, int(limit))

    connection = get_connection()
    cursor = connection.cursor()

    query = f"""
        SELECT
            employee_id,
            employee_name,
            month,
            year,
            monthly_salary,
            gross_salary,
            employee_pf,
            net_salary
        FROM salary
        ORDER BY monthly_salary {order}
        LIMIT ?
    """

    cursor.execute(query, (limit,))

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("SALARY DATABASE TOOL TEST")
    print("=" * 70)

    print("\nRajesh Sharma - August 2026:")

    print(
        get_salary_record(
            "Rajesh Sharma",
            "August",
            2026
        )
    )

    print("\nSalary Summary:")

    print(
        get_salary_summary(
            "Rajesh Sharma",
            "August",
            2026
        )
    )

    print("\nHighest salary employee:")

    print(
        get_highest_salary_employee()
    )

    print("\n" + "=" * 70)
    print("SALARY TOOL TEST COMPLETED")
    print("=" * 70)