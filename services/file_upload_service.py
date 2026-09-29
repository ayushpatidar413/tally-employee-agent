
import pandas as pd

from database.upload_db import (
    create_upload_table,
    insert_employee,
)


REQUIRED_COLUMNS = [
    "employee_id",
    "employee_name",
    "department",
    "designation",
    "employment_type",
    "joining_date",
    "monthly_salary",
    "previous_experience_years",
    "current_company_experience",
    "total_experience",
    "pf_applicable",
    "pf_rate",
    "employee_pf",
    "employer_pf",
    "employment_status",
]


def read_employee_file(file_path):

    file_path = str(file_path)

    if file_path.lower().endswith(".csv"):

        dataframe = pd.read_csv(file_path)

    elif file_path.lower().endswith((".xlsx", ".xls")):

        dataframe = pd.read_excel(file_path)

    else:

        raise ValueError(
            "Only CSV and Excel files are supported."
        )

    return dataframe


def validate_columns(dataframe):

    dataframe.columns = (
        dataframe.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:

        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing_columns)
        )

    return dataframe


def clean_value(value):

    # ---------------------------------------------------------
    # Handle empty Excel cells
    # ---------------------------------------------------------

    if pd.isna(value):

        return None

    # ---------------------------------------------------------
    # Convert Pandas Timestamp / datetime to string
    # ---------------------------------------------------------

    if isinstance(
        value,
        (
            pd.Timestamp,
            pd.DatetimeIndex,
        )
    ):

        return value.strftime("%Y-%m-%d")

    # ---------------------------------------------------------
    # Convert Python datetime-like values
    # ---------------------------------------------------------

    if hasattr(value, "strftime"):

        try:

            return value.strftime("%Y-%m-%d")

        except Exception:

            pass

    # ---------------------------------------------------------
    # Convert Pandas numeric values to normal Python values
    # ---------------------------------------------------------

    if hasattr(value, "item"):

        try:

            return value.item()

        except Exception:

            pass

    return value


def upload_employee_file(file_path):

    create_upload_table()

    dataframe = read_employee_file(file_path)

    dataframe = validate_columns(dataframe)

    uploaded_count = 0

    for _, row in dataframe.iterrows():

        employee = {}

        for column in REQUIRED_COLUMNS:

            employee[column] = clean_value(
                row[column]
            )

        insert_employee(employee)

        uploaded_count += 1

    return {
        "success": True,
        "filename": str(file_path),
        "records_uploaded": uploaded_count,
    }

