import sqlite3
from pathlib import Path


DATABASE_PATH = Path("data/hr_payroll.db")


def cleanup():

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    print("=" * 70)
    print("CLEANING INCORRECTLY UPLOADED DATA")
    print("=" * 70)

    # --------------------------------------------------------
    # Remove incorrect PF records created from employee_master
    # --------------------------------------------------------

    cursor.execute("""
        DELETE FROM pf_records
        WHERE pf_wage IS NULL
    """)

    pf_deleted = cursor.rowcount

    print(
        f"\nIncorrect PF records removed: {pf_deleted}"
    )

    # --------------------------------------------------------
    # Remove incorrect salary records created from
    # monthly_summary
    # --------------------------------------------------------

    cursor.execute("""
        DELETE FROM salary
        WHERE gross_salary IS NULL
    """)

    salary_deleted = cursor.rowcount

    print(
        f"Incorrect salary records removed: {salary_deleted}"
    )

    connection.commit()

    connection.close()

    print("\n" + "=" * 70)
    print("CLEANUP COMPLETED")
    print("=" * 70)


if __name__ == "__main__":

    cleanup()