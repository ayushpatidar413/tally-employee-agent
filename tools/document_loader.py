import pandas as pd
from pathlib import Path


DATA_FOLDER = Path("documents/tally")


def load_csv_files():
    """
    Load all six HR CSV files.
    """

    files = {
        "employee_master": "employee_master.csv",
        "attendance": "tally_attendance.csv",
        "leave": "leave_records.csv",
        "salary": "salary_records.csv",
        "pf": "pf_records.csv",
        "monthly_summary": "monthly_summary.csv",
    }

    data = {}

    for key, filename in files.items():

        file_path = DATA_FOLDER / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {file_path}"
            )

        print(f"Loading: {filename}")

        data[key] = pd.read_csv(file_path)

    return data


if __name__ == "__main__":

    print("=" * 70)
    print("TALLY HR & PAYROLL DATA LOADER")
    print("=" * 70)

    data = load_csv_files()

    print("\nDATA LOADED SUCCESSFULLY\n")

    for name, df in data.items():

        print("=" * 70)
        print(f"DATASET: {name}")
        print("=" * 70)

        print("Rows:", len(df))
        print("Columns:", len(df.columns))

        print("\nColumn names:")
        print(list(df.columns))

        print("\nFirst 3 records:")
        print(df.head(3))