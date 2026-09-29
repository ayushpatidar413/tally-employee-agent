import sqlite3
from pathlib import Path


DATABASE_FOLDER = Path("data")
DATABASE_PATH = DATABASE_FOLDER / "hr_payroll.db"


def get_connection():
    """
    Create and return a SQLite database connection.
    """

    DATABASE_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


if __name__ == "__main__":

    connection = get_connection()

    print("=" * 70)
    print("DATABASE CONNECTION")
    print("=" * 70)

    print(f"Database created at:")
    print(DATABASE_PATH)

    connection.close()

    print("\nDatabase connection successful.")