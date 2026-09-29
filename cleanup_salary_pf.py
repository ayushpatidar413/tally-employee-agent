from database.database import get_connection


def cleanup_salary():
    connection = get_connection()

    print("=" * 70)
    print("CLEANING SALARY TABLE")
    print("=" * 70)

    # Remove malformed salary records where:
    # month contains "August 2026" and year is NULL
    deleted = connection.execute(
        """
        DELETE FROM salary
        WHERE year IS NULL
        AND LOWER(TRIM(month)) = 'august 2026'
        """
    ).rowcount

    connection.commit()

    print(f"Removed malformed salary records: {deleted}")

    count = connection.execute(
        "SELECT COUNT(*) FROM salary"
    ).fetchone()[0]

    print(f"Salary records remaining: {count}")

    connection.close()


def cleanup_pf():
    connection = get_connection()

    print()
    print("=" * 70)
    print("CLEANING PF TABLE")
    print("=" * 70)

    # Remove PF records where month/year are missing.
    deleted = connection.execute(
        """
        DELETE FROM pf_records
        WHERE month IS NULL
           OR year IS NULL
        """
    ).rowcount

    connection.commit()

    print(f"Removed malformed PF records: {deleted}")

    count = connection.execute(
        "SELECT COUNT(*) FROM pf_records"
    ).fetchone()[0]

    print(f"PF records remaining: {count}")

    connection.close()


def show_final_counts():
    connection = get_connection()

    print()
    print("=" * 70)
    print("FINAL DATABASE COUNTS")
    print("=" * 70)

    employees = connection.execute(
        "SELECT COUNT(*) FROM employees"
    ).fetchone()[0]

    attendance = connection.execute(
        "SELECT COUNT(*) FROM attendance"
    ).fetchone()[0]

    salary = connection.execute(
        "SELECT COUNT(*) FROM salary"
    ).fetchone()[0]

    pf = connection.execute(
        "SELECT COUNT(*) FROM pf_records"
    ).fetchone()[0]

    print(f"Employees   : {employees}")
    print(f"Attendance  : {attendance}")
    print(f"Salary      : {salary}")
    print(f"PF          : {pf}")

    connection.close()


if __name__ == "__main__":
    cleanup_salary()
    cleanup_pf()
    show_final_counts()