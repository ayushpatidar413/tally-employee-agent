from database.database import get_connection


# ============================================================
# GET PF RECORD
# ============================================================

def get_pf_record(
    employee_name,
    month=None,
    year=None
):
    """
    Get PF record for an employee.

    If month and year are provided,
    the PF record is filtered by month and year.

    If month/year are not provided,
    the latest available PF record is returned.
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
            FROM pf_records
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
            FROM pf_records
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
# GET PF SUMMARY
# ============================================================

def get_pf_summary(
    employee_name,
    month=None,
    year=None
):
    """
    Get PF summary for an employee.

    Optional month/year filtering is supported.
    """

    record = get_pf_record(
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
        "pf_applicable": record["pf_applicable"],
        "pf_rate": record["pf_rate"],
        "pf_wage": record["pf_wage"],
        "employee_pf": record["employee_pf"],
        "employer_pf": record["employer_pf"],
        "total_pf": record["total_pf"],
        "pf_status": record["pf_status"],
    }


# ============================================================
# GET TOTAL PF
# ============================================================

def get_total_pf():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            SUM(employee_pf) AS employee_pf_total,
            SUM(employer_pf) AS employer_pf_total,
            SUM(total_pf) AS total_pf
        FROM pf_records
        """
    )

    row = cursor.fetchone()

    connection.close()

    return dict(row)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("PF DATABASE TOOL TEST")
    print("=" * 70)

    print("\nRajesh Sharma - August 2026:")

    print(
        get_pf_record(
            "Rajesh Sharma",
            "August",
            2026
        )
    )

    print("\nPF Summary:")

    print(
        get_pf_summary(
            "Rajesh Sharma",
            "August",
            2026
        )
    )

    print("\nTotal PF:")

    print(
        get_total_pf()
    )

    print("\n" + "=" * 70)
    print("PF TOOL TEST COMPLETED")
    print("=" * 70)