import pandas as pd
import sqlite3
from pathlib import Path
from datetime import datetime, date
import re


DATABASE_PATH = Path("data/hr_payroll.db")


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# UPLOAD HISTORY
# ============================================================

def create_upload_history_table():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS upload_history (

            upload_id INTEGER PRIMARY KEY AUTOINCREMENT,

            file_name TEXT NOT NULL,

            file_type TEXT,

            data_type TEXT,

            uploaded_at TEXT,

            records_inserted INTEGER,

            status TEXT,

            message TEXT
        )
    """)

    connection.commit()
    connection.close()


# ============================================================
# READ CSV / EXCEL
# ============================================================

def read_file(file_path):

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    extension = file_path.suffix.lower()

    if extension == ".csv":

        df = pd.read_csv(file_path)

    elif extension in [".xlsx", ".xls"]:

        df = pd.read_excel(file_path)

    else:

        raise ValueError(
            "Unsupported file type. "
            "Only CSV and Excel files are supported."
        )

    return df


# ============================================================
# NORMALIZE COLUMNS
# ============================================================

def normalize_columns(df):

    df = df.copy()

    normalized_columns = []

    for column in df.columns:

        column = str(column).strip()

        column = re.sub(
            r"\s+",
            " ",
            column
        )

        normalized_columns.append(column)

    df.columns = normalized_columns

    return df


# ============================================================
# DETECT DATA TYPE
# ============================================================

def detect_data_type(df):

    columns = {
        str(column).lower().strip()
        for column in df.columns
    }

    # Attendance
    attendance_columns = {
        "employee id",
        "attendance status",
        "date"
    }

    if attendance_columns.issubset(columns):

        return "attendance"

    # Monthly Summary
    summary_columns = {
        "employee id",
        "attendance percentage",
        "total experience"
    }

    if summary_columns.issubset(columns):

        return "monthly_summary"

    # Leave
    leave_columns = {
        "leave id",
        "employee id",
        "leave date",
        "leave type"
    }

    if leave_columns.issubset(columns):

        return "leave"

    # PF
    pf_columns = {
        "employee id",
        "month",
        "year",
        "pf applicable",
        "pf wage",
        "employee pf",
        "employer pf"
    }

    if pf_columns.issubset(columns):

        return "pf"

    # Salary
    salary_columns = {
        "employee id",
        "month",
        "year",
        "monthly salary",
        "net salary"
    }

    if salary_columns.issubset(columns):

        return "salary"

    # Employee
    employee_columns = {
        "employee id",
        "employee name",
        "department",
        "designation",
        "joining date",
        "monthly salary",
        "employment status"
    }

    if employee_columns.issubset(columns):

        return "employee"

    return "unknown"


# ============================================================
# TABLE MAPPING
# ============================================================

TABLE_MAPPING = {

    "employee": "employees",

    "attendance": "attendance",

    "leave": "leaves",

    "salary": "salary",

    "pf": "pf_records",

    "monthly_summary": "monthly_summary"
}


# ============================================================
# VALIDATION
# ============================================================

def validate_data(df, data_type):

    if df.empty:

        return False, "Uploaded file is empty."

    if data_type == "unknown":

        return False, (
            "Unable to identify the uploaded file."
        )

    required_columns = {

        "employee": [
            "Employee ID",
            "Employee Name",
            "Monthly Salary"
        ],

        "attendance": [
            "Employee ID",
            "Date",
            "Attendance Status"
        ],

        "leave": [
            "Leave ID",
            "Employee ID",
            "Leave Date"
        ],

        "salary": [
            "Employee ID",
            "Monthly Salary",
            "Net Salary"
        ],

        "pf": [
            "Employee ID",
            "Employee PF",
            "Employer PF"
        ],

        "monthly_summary": [
            "Employee ID",
            "Attendance Percentage",
            "Total Experience"
        ]
    }

    required = required_columns[data_type]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:

        return False, (
            f"Missing columns: {missing}"
        )

    return True, "Validation successful."


# ============================================================
# SQLITE VALUE CONVERSION
# ============================================================

def convert_for_sqlite(value):

    if value is None:

        return None

    try:

        if pd.isna(value):

            return None

    except (TypeError, ValueError):

        pass

    if isinstance(value, pd.Timestamp):

        return value.strftime("%Y-%m-%d")

    if isinstance(value, datetime):

        return value.strftime("%Y-%m-%d")

    if isinstance(value, date):

        return value.strftime("%Y-%m-%d")

    if hasattr(value, "item"):

        try:

            return value.item()

        except Exception:

            pass

    return value


# ============================================================
# COLUMN MAPPING
# ============================================================

COLUMN_MAPPING = {

    "Employee ID": "employee_id",

    "Employee Name": "employee_name",

    "Department": "department",

    "Designation": "designation",

    "Employment Type": "employment_type",

    "Joining Date": "joining_date",

    "Monthly Salary": "monthly_salary",

    "Previous Experience Years":
        "previous_experience_years",

    "Current Company Experience":
        "current_company_experience",

    "Total Experience":
        "total_experience",

    "PF Applicable":
        "pf_applicable",

    "PF Rate":
        "pf_rate",

    "Employee PF":
        "employee_pf",

    "Employer PF":
        "employer_pf",

    "Employment Status":
        "employment_status",

    "Date":
        "date",

    "Day":
        "day",

    "Attendance Status":
        "attendance_status",

    "Check In":
        "check_in",

    "Check Out":
        "check_out",

    "Working Hours":
        "working_hours",

    "Leave Type":
        "leave_type",

    "Remarks":
        "remarks",

    "Leave ID":
        "leave_id",

    "Leave Date":
        "leave_date",

    "Paid/Unpaid":
        "paid_unpaid",

    "Leave Days":
        "leave_days",

    "Approval Status":
        "approval_status",

    "Reason":
        "reason",

    "Month":
        "month",

    "Year":
        "year",

    "Working Days":
        "working_days",

    "Present Days":
        "present_days",

    "Absent Days":
        "absent_days",

    "Half Days":
        "half_days",

    "Free Leave Days":
        "free_leave_days",

    "Unpaid Absence Days":
        "unpaid_absence_days",

    "Per Day Salary":
        "per_day_salary",

    "Gross Salary":
        "gross_salary",

    "Absence Deduction":
        "absence_deduction",

    "Leave Deduction":
        "leave_deduction",

    "Other Deduction":
        "other_deduction",

    "Net Salary":
        "net_salary",

    "PF Wage":
        "pf_wage",

    "Total PF":
        "total_pf",

    "PF Status":
        "pf_status",

    "Attendance Percentage":
        "attendance_percentage",

    "Free Leave Allowed":
        "free_leave_allowed"
}


# ============================================================
# PREPARE DATA
# ============================================================

def prepare_dataframe(df, data_type):

    df = df.rename(
        columns=COLUMN_MAPPING
    )

    connection = get_connection()
    cursor = connection.cursor()

    table_name = TABLE_MAPPING[data_type]

    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    database_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    connection.close()

    existing_columns = [

        column

        for column in df.columns

        if column in database_columns
    ]

    if not existing_columns:

        raise ValueError(
            f"No matching database columns found "
            f"for table '{table_name}'."
        )

    df = df[existing_columns]

    records = []

    for row in df.itertuples(
        index=False,
        name=None
    ):

        converted_row = tuple(

            convert_for_sqlite(value)

            for value in row

        )

        records.append(converted_row)

    return existing_columns, records


# ============================================================
# DELETE EXISTING RECORD
# ============================================================

def delete_existing_record(
    cursor,
    data_type,
    record,
    columns
):

    def get_value(column_name):

        if column_name not in columns:

            return None

        index = columns.index(column_name)

        return record[index]


    # --------------------------------------------------------
    # EMPLOYEE
    # --------------------------------------------------------

    if data_type == "employee":

        employee_id = get_value(
            "employee_id"
        )

        cursor.execute(
            """
            DELETE FROM employees
            WHERE employee_id = ?
            """,
            (employee_id,)
        )


    # --------------------------------------------------------
    # ATTENDANCE
    # Employee + Date
    # --------------------------------------------------------

    elif data_type == "attendance":

        employee_id = get_value(
            "employee_id"
        )

        attendance_date = get_value(
            "date"
        )

        cursor.execute(
            """
            DELETE FROM attendance

            WHERE employee_id = ?

            AND date = ?
            """,
            (
                employee_id,
                attendance_date
            )
        )


    # --------------------------------------------------------
    # LEAVE
    # Leave ID
    # --------------------------------------------------------

    elif data_type == "leave":

        leave_id = get_value(
            "leave_id"
        )

        cursor.execute(
            """
            DELETE FROM leaves

            WHERE leave_id = ?
            """,
            (leave_id,)
        )


    # --------------------------------------------------------
    # SALARY
    # Employee + Month + Year
    # --------------------------------------------------------

    elif data_type == "salary":

        employee_id = get_value(
            "employee_id"
        )

        month = get_value(
            "month"
        )

        year = get_value(
            "year"
        )

        cursor.execute(
            """
            DELETE FROM salary

            WHERE employee_id = ?

            AND month = ?

            AND year = ?
            """,
            (
                employee_id,
                month,
                year
            )
        )


    # --------------------------------------------------------
    # PF
    # Employee + Month + Year
    # --------------------------------------------------------

    elif data_type == "pf":

        employee_id = get_value(
            "employee_id"
        )

        month = get_value(
            "month"
        )

        year = get_value(
            "year"
        )

        cursor.execute(
            """
            DELETE FROM pf_records

            WHERE employee_id = ?

            AND month = ?

            AND year = ?
            """,
            (
                employee_id,
                month,
                year
            )
        )


    # --------------------------------------------------------
    # MONTHLY SUMMARY
    # Employee + Month
    # --------------------------------------------------------

    elif data_type == "monthly_summary":

        employee_id = get_value(
            "employee_id"
        )

        month = get_value(
            "month"
        )

        cursor.execute(
            """
            DELETE FROM monthly_summary

            WHERE employee_id = ?

            AND month = ?
            """,
            (
                employee_id,
                month
            )
        )


# ============================================================
# INSERT DATA
# ============================================================

def insert_data(df, data_type):

    table_name = TABLE_MAPPING[data_type]

    columns, records = prepare_dataframe(
        df,
        data_type
    )

    connection = get_connection()
    cursor = connection.cursor()

    column_string = ",".join(columns)

    placeholders = ",".join(
        ["?"] * len(columns)
    )

    query = f"""
        INSERT INTO {table_name}
        ({column_string})
        VALUES ({placeholders})
    """

    inserted_count = 0

    try:

        for record in records:

            delete_existing_record(
                cursor,
                data_type,
                record,
                columns
            )

            cursor.execute(
                query,
                record
            )

            inserted_count += 1

        connection.commit()

    except Exception:

        connection.rollback()

        connection.close()

        raise

    connection.close()

    return inserted_count


# ============================================================
# UPLOAD HISTORY
# ============================================================

def save_upload_history(
    file_name,
    file_type,
    data_type,
    records,
    status,
    message
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO upload_history (

            file_name,

            file_type,

            data_type,

            uploaded_at,

            records_inserted,

            status,

            message

        )

        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,

        (
            file_name,

            file_type,

            data_type,

            datetime.now().isoformat(),

            records,

            status,

            message
        )
    )

    connection.commit()

    connection.close()


# ============================================================
# MAIN FILE PROCESSOR
# ============================================================

def process_uploaded_file(file_path):

    create_upload_history_table()

    file_path = Path(file_path)

    try:

        print("\n" + "=" * 70)

        print(
            "DYNAMIC HR FILE PROCESSING"
        )

        print("=" * 70)

        print(
            f"\nFile: {file_path.name}"
        )


        # ----------------------------------------------------
        # READ FILE
        # ----------------------------------------------------

        df = read_file(file_path)

        print(
            f"Records found: {len(df)}"
        )


        # ----------------------------------------------------
        # NORMALIZE
        # ----------------------------------------------------

        df = normalize_columns(df)


        # ----------------------------------------------------
        # SHOW COLUMNS
        # ----------------------------------------------------

        print("\nColumns detected:")

        for column in df.columns:

            print(
                f"  ✓ {column}"
            )


        # ----------------------------------------------------
        # DETECT DATA TYPE
        # ----------------------------------------------------

        data_type = detect_data_type(df)

        print(
            f"\nDetected data type: {data_type}"
        )


        # ----------------------------------------------------
        # VALIDATE
        # ----------------------------------------------------

        valid, message = validate_data(
            df,
            data_type
        )

        if not valid:

            save_upload_history(

                file_path.name,

                file_path.suffix,

                data_type,

                0,

                "FAILED",

                message
            )

            return {

                "success": False,

                "message": message,

                "data_type": data_type
            }


        # ----------------------------------------------------
        # INSERT / REPLACE
        # ----------------------------------------------------

        records = insert_data(
            df,
            data_type
        )


        # ----------------------------------------------------
        # SAVE HISTORY
        # ----------------------------------------------------

        save_upload_history(

            file_path.name,

            file_path.suffix,

            data_type,

            records,

            "SUCCESS",

            "Data inserted successfully."
        )


        print(
            f"\n✓ {records} records stored in database."
        )

        print(
            "\nDatabase:"
        )

        print(
            DATABASE_PATH
        )

        print(
            "\n" + "=" * 70
        )


        return {

            "success": True,

            "message":
                "File processed successfully.",

            "data_type":
                data_type,

            "records_inserted":
                records,

            "database":
                str(DATABASE_PATH)
        }


    except Exception as e:

        save_upload_history(

            file_path.name,

            file_path.suffix,

            "unknown",

            0,

            "FAILED",

            str(e)
        )

        return {

            "success": False,

            "message": str(e)
        }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:

        print("\nUsage:")

        print(
            "python -m tools.dynamic_file_loader "
            "your_file.csv"
        )

        sys.exit()

    file_path = sys.argv[1]

    result = process_uploaded_file(
        file_path
    )

    print("\nRESULT:")

    print(result)