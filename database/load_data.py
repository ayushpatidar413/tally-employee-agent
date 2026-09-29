import pandas as pd
from database import get_connection
from pathlib import Path


DATA_FOLDER = Path("documents/tally")


def load_data():

    connection = get_connection()

    print("=" * 70)
    print("LOADING HR DATA INTO SQLITE")
    print("=" * 70)

    # --------------------------------------------------
    # EMPLOYEES
    # --------------------------------------------------

    employee_file = DATA_FOLDER / "employee_master.csv"

    employees = pd.read_csv(
        employee_file
    )

    employees = employees.rename(
        columns={
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
            "PF Applicable": "pf_applicable",
            "PF Rate": "pf_rate",
            "Employee PF": "employee_pf",
            "Employer PF": "employer_pf",
            "Employment Status":
                "employment_status"
        }
    )

    employees.to_sql(
        "employees",
        connection,
        if_exists="append",
        index=False
    )

    print(
        f"Employees loaded: {len(employees)}"
    )

    # --------------------------------------------------
    # ATTENDANCE
    # --------------------------------------------------

    attendance = pd.read_csv(
        DATA_FOLDER / "tally_attendance.csv"
    )

    attendance = attendance.rename(
        columns={
            "Employee ID": "employee_id",
            "Employee Name": "employee_name",
            "Department": "department",
            "Date": "date",
            "Day": "day",
            "Attendance Status":
                "attendance_status",
            "Check In": "check_in",
            "Check Out": "check_out",
            "Working Hours":
                "working_hours",
            "Leave Type":
                "leave_type",
            "Remarks":
                "remarks"
        }
    )

    attendance.to_sql(
        "attendance",
        connection,
        if_exists="append",
        index=False
    )

    print(
        f"Attendance loaded: {len(attendance)}"
    )

    # --------------------------------------------------
    # LEAVE
    # --------------------------------------------------

    leaves = pd.read_csv(
        DATA_FOLDER / "leave_records.csv"
    )

    leaves = leaves.rename(
        columns={
            "Leave ID": "leave_id",
            "Employee ID": "employee_id",
            "Employee Name": "employee_name",
            "Leave Date": "leave_date",
            "Leave Type": "leave_type",
            "Paid/Unpaid": "paid_unpaid",
            "Leave Days": "leave_days",
            "Approval Status":
                "approval_status",
            "Reason": "reason"
        }
    )

    leaves.to_sql(
        "leaves",
        connection,
        if_exists="append",
        index=False
    )

    print(
        f"Leave records loaded: {len(leaves)}"
    )

    # --------------------------------------------------
    # SALARY
    # --------------------------------------------------

    salary = pd.read_csv(
        DATA_FOLDER / "salary_records.csv"
    )

    salary = salary.rename(
        columns={
            "Employee ID": "employee_id",
            "Employee Name": "employee_name",
            "Month": "month",
            "Year": "year",
            "Monthly Salary":
                "monthly_salary",
            "Working Days":
                "working_days",
            "Present Days":
                "present_days",
            "Absent Days":
                "absent_days",
            "Leave Days":
                "leave_days",
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
            "Employee PF":
                "employee_pf",
            "Other Deduction":
                "other_deduction",
            "Net Salary":
                "net_salary"
        }
    )

    salary.to_sql(
        "salary",
        connection,
        if_exists="append",
        index=False
    )

    print(
        f"Salary records loaded: {len(salary)}"
    )

    # --------------------------------------------------
    # PF
    # --------------------------------------------------

    pf = pd.read_csv(
        DATA_FOLDER / "pf_records.csv"
    )

    pf = pf.rename(
        columns={
            "Employee ID":
                "employee_id",
            "Employee Name":
                "employee_name",
            "Month":
                "month",
            "Year":
                "year",
            "PF Applicable":
                "pf_applicable",
            "PF Rate":
                "pf_rate",
            "PF Wage":
                "pf_wage",
            "Employee PF":
                "employee_pf",
            "Employer PF":
                "employer_pf",
            "Total PF":
                "total_pf",
            "PF Status":
                "pf_status"
        }
    )

    pf.to_sql(
        "pf_records",
        connection,
        if_exists="append",
        index=False
    )

    print(
        f"PF records loaded: {len(pf)}"
    )

    # --------------------------------------------------
    # MONTHLY SUMMARY
    # --------------------------------------------------

    summary = pd.read_csv(
        DATA_FOLDER / "monthly_summary.csv"
    )

    summary = summary.rename(
        columns={
            "Employee ID":
                "employee_id",
            "Employee Name":
                "employee_name",
            "Department":
                "department",
            "Month":
                "month",
            "Working Days":
                "working_days",
            "Present Days":
                "present_days",
            "Absent Days":
                "absent_days",
            "Leave Days":
                "leave_days",
            "Half Days":
                "half_days",
            "Attendance Percentage":
                "attendance_percentage",
            "Free Leave Allowed":
                "free_leave_allowed",
            "Free Leave Used":
                "free_leave_used",
            "Unpaid Absence Days":
                "unpaid_absence_days",
            "Monthly Salary":
                "monthly_salary",
            "Absence Deduction":
                "absence_deduction",
            "Employee PF":
                "employee_pf",
            "Employer PF":
                "employer_pf",
            "Total PF":
                "total_pf",
            "Net Salary":
                "net_salary",
            "Current Company Experience":
                "current_company_experience",
            "Previous Experience":
                "previous_experience",
            "Total Experience":
                "total_experience"
        }
    )

    summary.to_sql(
        "monthly_summary",
        connection,
        if_exists="append",
        index=False
    )

    print(
        f"Monthly summary loaded: {len(summary)}"
    )

    connection.close()

    print("\n" + "=" * 70)
    print("ALL DATA LOADED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    load_data()