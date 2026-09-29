import sqlite3
from pathlib import Path


DATABASE_PATH = Path("data/hr_payroll.db")


def check_database():

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    tables = [
        "employees",
        "attendance",
        "leaves",
        "salary",
        "pf_records",
        "monthly_summary",
        "upload_history"
    ]

    print("=" * 70)
    print("HR PAYROLL DATABASE VERIFICATION")
    print("=" * 70)

    for table in tables:

        try:
            cursor.execute(
                f"SELECT COUNT(*) FROM {table}"
            )

            count = cursor.fetchone()[0]

            print(
                f"{table:<20} : {count} records"
            )

        except sqlite3.Error as error:

            print(
                f"{table:<20} : ERROR - {error}"
            )

    connection.close()

    print("=" * 70)


if __name__ == "__main__":
    check_database()