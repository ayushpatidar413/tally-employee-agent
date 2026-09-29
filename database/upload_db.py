import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "hr_uploads.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_upload_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# ============================================================
# HELPERS
# ============================================================

def normalize_column_name(column):
    """
    Convert different Excel column names into a common format.

    Examples:

    Employee Name
    employee name
    Employee_Name
    Employee Full Name

    can all be recognized more easily.
    """

    text = str(column).strip().lower()

    text = text.replace("_", " ")
    text = text.replace("-", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def clean_value(value):
    """
    Convert pandas/Excel values into database-safe values.
    """

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y-%m-%d")
        except Exception:
            pass

    if isinstance(value, float):
        if value.is_integer():
            return int(value)

    return value


def normalize_for_json(value):
    """
    Convert a value into something JSON can store.
    """

    value = clean_value(value)

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


# ============================================================
# COLUMN ALIASES
# ============================================================

COLUMN_ALIASES = {

    # --------------------------------------------------------
    # EMPLOYEE ID
    # --------------------------------------------------------

    "employee id": "employee_id",
    "emp id": "employee_id",
    "employee code": "employee_id",
    "emp code": "employee_id",
    "employee number": "employee_id",
    "emp number": "employee_id",
    "employee no": "employee_id",
    "emp no": "employee_id",

    # --------------------------------------------------------
    # EMPLOYEE NAME
    # --------------------------------------------------------

    "employee name": "employee_name",
    "name": "employee_name",
    "employee full name": "employee_name",
    "full name": "employee_name",
    "emp name": "employee_name",
    "employee": "employee_name",

    # --------------------------------------------------------
    # BASIC EMPLOYEE INFORMATION
    # --------------------------------------------------------

    "department": "department",
    "dept": "department",

    "designation": "designation",
    "job title": "designation",
    "position": "designation",

    "employment type": "employment_type",
    "employee type": "employment_type",
    "job type": "employment_type",

    "joining date": "joining_date",
    "join date": "joining_date",
    "date of joining": "joining_date",
    "doj": "joining_date",

    "employment status": "employment_status",
    "employee status": "employment_status",
    "status": "employment_status",

    # --------------------------------------------------------
    # SALARY
    # --------------------------------------------------------

    "monthly salary": "monthly_salary",
    "salary": "monthly_salary",
    "monthly pay": "monthly_salary",
    "monthly income": "monthly_salary",
    "pay": "monthly_salary",

    # --------------------------------------------------------
    # EXPERIENCE
    # --------------------------------------------------------

    "previous experience years":
        "previous_experience_years",

    "previous experience":
        "previous_experience_years",

    "prior experience":
        "previous_experience_years",

    "current company experience":
        "current_company_experience",

    "company experience":
        "current_company_experience",

    "current experience":
        "current_company_experience",

    "total experience":
        "total_experience",

    "experience":
        "total_experience",

    "total experience years":
        "total_experience",

    # --------------------------------------------------------
    # PF
    # --------------------------------------------------------

    "pf applicable": "pf_applicable",
    "pf": "pf_applicable",
    "provident fund": "pf_applicable",

    "pf rate": "pf_rate",
    "pf percentage": "pf_rate",

    "employee pf": "employee_pf",
    "employee provident fund": "employee_pf",

    "employer pf": "employer_pf",
    "employer provident fund": "employer_pf",

    # --------------------------------------------------------
    # OUTSTANDING
    # --------------------------------------------------------

    "outstanding": "outstanding",
    "outstanding amount": "outstanding",
    "pending amount": "outstanding",
    "pending payment": "outstanding",
    "amount due": "outstanding",
    "due amount": "outstanding",
    "balance due": "outstanding",

}


# ============================================================
# NORMALIZE DATAFRAME COLUMNS
# ============================================================

def normalize_dataframe_columns(dataframe):
    """
    Normalize known columns.

    Unknown columns are preserved and stored as extra data.
    """

    renamed_columns = {}

    for original_column in dataframe.columns:

        normalized = normalize_column_name(original_column)

        if normalized in COLUMN_ALIASES:
            renamed_columns[original_column] = COLUMN_ALIASES[
                normalized
            ]
        else:
            # Preserve unknown column.
            renamed_columns[original_column] = str(
                original_column
            ).strip()

    dataframe = dataframe.rename(
        columns=renamed_columns
    )

    return dataframe


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

def create_upload_table():

    connection = get_upload_connection()
    cursor = connection.cursor()

    # --------------------------------------------------------
    # EMPLOYEE TABLE
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS uploaded_employees (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            employee_id TEXT UNIQUE,
            employee_name TEXT,

            department TEXT,
            designation TEXT,
            employment_type TEXT,
            joining_date TEXT,

            monthly_salary REAL,

            previous_experience_years REAL,
            current_company_experience REAL,
            total_experience REAL,

            pf_applicable TEXT,
            pf_rate REAL,
            employee_pf REAL,
            employer_pf REAL,

            employment_status TEXT,

            extra_data TEXT DEFAULT '{}',

            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # --------------------------------------------------------
    # MIGRATE EXISTING DATABASE
    # --------------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(uploaded_employees)"
    )

    existing_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    if "extra_data" not in existing_columns:

        cursor.execute(
            """
            ALTER TABLE uploaded_employees
            ADD COLUMN extra_data TEXT DEFAULT '{}'
            """
        )

    # --------------------------------------------------------
    # UPLOAD HISTORY TABLE
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS upload_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            original_filename TEXT NOT NULL,

            stored_filename TEXT NOT NULL,

            file_path TEXT NOT NULL,

            file_type TEXT,

            file_size INTEGER,

            records_uploaded INTEGER DEFAULT 0,

            status TEXT DEFAULT 'SUCCESS',

            error_message TEXT,

            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()
    connection.close()


# ============================================================
# INSERT / UPDATE EMPLOYEE
# ============================================================

def insert_employee(employee):

    create_upload_table()

    connection = get_upload_connection()
    cursor = connection.cursor()

    employee_id = str(
        employee.get("employee_id", "")
    ).strip()

    employee_name = employee.get(
        "employee_name"
    )

    # --------------------------------------------------------
    # EMPLOYEE ID
    # --------------------------------------------------------

    if not employee_id:

        # If there is no employee ID, we cannot safely
        # perform an update/insert using employee_id.
        connection.close()
        return False

    # --------------------------------------------------------
    # EXTRA DATA
    # --------------------------------------------------------

    extra_data = employee.get(
        "extra_data",
        {}
    )

    if not isinstance(extra_data, dict):
        extra_data = {}

    extra_data = {
        str(key): normalize_for_json(value)
        for key, value in extra_data.items()
    }

    extra_data_json = json.dumps(
        extra_data,
        ensure_ascii=False
    )

    uploaded_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # --------------------------------------------------------
    # INSERT / UPDATE
    # --------------------------------------------------------

    cursor.execute(
        """
        INSERT INTO uploaded_employees (

            employee_id,
            employee_name,

            department,
            designation,
            employment_type,
            joining_date,

            monthly_salary,

            previous_experience_years,
            current_company_experience,
            total_experience,

            pf_applicable,
            pf_rate,
            employee_pf,
            employer_pf,

            employment_status,

            extra_data,

            uploaded_at
        )

        VALUES (
            ?, ?,
            ?, ?, ?, ?,
            ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?,
            ?,
            ?
        )

        ON CONFLICT(employee_id)
        DO UPDATE SET

            employee_name =
                excluded.employee_name,

            department =
                excluded.department,

            designation =
                excluded.designation,

            employment_type =
                excluded.employment_type,

            joining_date =
                excluded.joining_date,

            monthly_salary =
                excluded.monthly_salary,

            previous_experience_years =
                excluded.previous_experience_years,

            current_company_experience =
                excluded.current_company_experience,

            total_experience =
                excluded.total_experience,

            pf_applicable =
                excluded.pf_applicable,

            pf_rate =
                excluded.pf_rate,

            employee_pf =
                excluded.employee_pf,

            employer_pf =
                excluded.employer_pf,

            employment_status =
                excluded.employment_status,

            extra_data =
                excluded.extra_data,

            uploaded_at =
                excluded.uploaded_at
        """,
        (
            employee_id,
            employee_name,

            employee.get("department"),
            employee.get("designation"),
            employee.get("employment_type"),
            employee.get("joining_date"),

            employee.get("monthly_salary"),

            employee.get(
                "previous_experience_years"
            ),

            employee.get(
                "current_company_experience"
            ),

            employee.get(
                "total_experience"
            ),

            employee.get("pf_applicable"),
            employee.get("pf_rate"),
            employee.get("employee_pf"),
            employee.get("employer_pf"),

            employee.get("employment_status"),

            extra_data_json,

            uploaded_at,
        ),
    )

    connection.commit()
    connection.close()

    return True


# ============================================================
# CONVERT DATABASE ROW
# ============================================================

def _row_to_employee(row):

    employee = dict(row)

    extra_data = employee.get(
        "extra_data"
    )

    if extra_data:

        try:
            extra_data = json.loads(
                extra_data
            )

            if isinstance(extra_data, dict):

                for key, value in extra_data.items():

                    # Do not overwrite known database
                    # fields.
                    if key not in employee:
                        employee[key] = value

        except (
            json.JSONDecodeError,
            TypeError
        ):
            pass

    return employee


# ============================================================
# RECORD FILE UPLOAD
# ============================================================

def record_upload(
    original_filename,
    stored_filename,
    file_path,
    file_type,
    file_size,
    records_uploaded,
    status="SUCCESS",
    error_message=None,
):

    create_upload_table()

    connection = get_upload_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO upload_history (

            original_filename,
            stored_filename,
            file_path,
            file_type,
            file_size,
            records_uploaded,
            status,
            error_message,
            uploaded_at

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            original_filename,
            stored_filename,
            file_path,
            file_type,
            file_size,
            records_uploaded,
            status,
            error_message,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        ),
    )

    connection.commit()

    upload_id = cursor.lastrowid

    connection.close()

    return upload_id


# ============================================================
# GET UPLOAD HISTORY
# ============================================================

def get_upload_history(limit=1000):

    create_upload_table()

    connection = get_upload_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM upload_history
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# SEARCH EMPLOYEE
# ============================================================

def search_uploaded_employee(search_text):

    create_upload_table()

    connection = get_upload_connection()
    cursor = connection.cursor()

    search_text = str(
        search_text
    ).strip()

    cursor.execute(
        """
        SELECT *
        FROM uploaded_employees
        WHERE

            LOWER(
                TRIM(
                    COALESCE(
                        employee_id,
                        ''
                    )
                )
            ) LIKE LOWER(?)

            OR

            LOWER(
                TRIM(
                    COALESCE(
                        employee_name,
                        ''
                    )
                )
            ) LIKE LOWER(?)

        ORDER BY id DESC
        """,
        (
            f"%{search_text}%",
            f"%{search_text}%",
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        _row_to_employee(row)
        for row in rows
    ]


# ============================================================
# GET EMPLOYEES
# ============================================================

def get_uploaded_employees(limit=10000):

    create_upload_table()

    connection = get_upload_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM uploaded_employees
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        _row_to_employee(row)
        for row in rows
    ]


# ============================================================
# COUNT EMPLOYEES
# ============================================================

def count_uploaded_employees():

    create_upload_table()

    connection = get_upload_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM uploaded_employees
        """
    )

    count = cursor.fetchone()[0]

    connection.close()

    return count


# ============================================================
# UPLOAD EMPLOYEE FILE
# ============================================================

def upload_employee_file(file_path):
    """
    Read CSV/Excel file.

    Known columns are normalized.

    Unknown columns are preserved inside extra_data.

    Example:

        Employee Name
        Name
        Employee Full Name

    are recognized as employee_name.

    Extra columns such as:

        Outstanding
        Bonus
        Location
        Manager

    are preserved.
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    # --------------------------------------------------------
    # READ FILE
    # --------------------------------------------------------

    suffix = file_path.suffix.lower()

    if suffix == ".csv":

        dataframe = pd.read_csv(
            file_path
        )

    elif suffix in [".xlsx", ".xls"]:

        dataframe = pd.read_excel(
            file_path
        )

    else:

        raise ValueError(
            "Only CSV, XLSX and XLS files are supported."
        )

    if dataframe.empty:
        return {
            "records_uploaded": 0
        }

    # --------------------------------------------------------
    # CLEAN COLUMN NAMES
    # --------------------------------------------------------

    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    # --------------------------------------------------------
    # NORMALIZE COLUMNS
    # --------------------------------------------------------

    dataframe = normalize_dataframe_columns(
        dataframe
    )

    # --------------------------------------------------------
    # INSERT EMPLOYEES
    # --------------------------------------------------------

    records_uploaded = 0

    known_columns = {
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
    }

    for _, row in dataframe.iterrows():

        employee = {}

        # ----------------------------------------------------
        # KNOWN COLUMNS
        # ----------------------------------------------------

        for column in known_columns:

            if column in dataframe.columns:

                value = clean_value(
                    row[column]
                )

                employee[column] = value

            else:

                employee[column] = None

        # ----------------------------------------------------
        # EXTRA COLUMNS
        # ----------------------------------------------------

        extra_data = {}

        for column in dataframe.columns:

            if column in known_columns:
                continue

            value = clean_value(
                row[column]
            )

            if value is not None:

                extra_data[str(column)] = value

        employee["extra_data"] = extra_data

        # ----------------------------------------------------
        # INSERT / UPDATE
        # ----------------------------------------------------

        if insert_employee(employee):

            records_uploaded += 1

    return {
        "records_uploaded": records_uploaded
    }


# ============================================================
# DELETE UPLOAD HISTORY + PHYSICAL FILE
# ============================================================

def delete_upload(upload_id):
    """
    Delete one uploaded file from:

    1. Physical uploads folder
    2. upload_history database table

    Employee records are NOT deleted.
    """

    create_upload_table()

    connection = get_upload_connection()
    cursor = connection.cursor()

    # --------------------------------------------------------
    # FIND UPLOAD RECORD
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT *
        FROM upload_history
        WHERE id = ?
        """,
        (upload_id,),
    )

    row = cursor.fetchone()

    if not row:

        connection.close()

        return {
            "success": False,
            "message": "Upload record not found."
        }

    upload = dict(row)

    # --------------------------------------------------------
    # DELETE PHYSICAL FILE
    # --------------------------------------------------------

    file_path = Path(
        upload["file_path"]
    )

    if not file_path.is_absolute():

        file_path = (
            Path(__file__).resolve().parent.parent
            / file_path
        )

    file_deleted = False

    if file_path.exists():

        file_path.unlink()

        file_deleted = True

    # --------------------------------------------------------
    # DELETE DATABASE HISTORY
    # --------------------------------------------------------

    cursor.execute(
        """
        DELETE FROM upload_history
        WHERE id = ?
        """,
        (upload_id,),
    )

    connection.commit()
    connection.close()

    return {
        "success": True,
        "message": "Upload deleted successfully.",
        "upload_id": upload_id,
        "file_deleted": file_deleted,
        "filename": upload["original_filename"],
    }


# ============================================================
# CREATE TABLES WHEN MODULE LOADS
# ============================================================

create_upload_table()