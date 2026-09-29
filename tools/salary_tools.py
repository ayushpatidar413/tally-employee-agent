from document_loader import load_csv_files


def get_salary_record(employee_name):
    """
    Get complete salary record for an employee.
    """

    data = load_csv_files()
    df = data["salary"]

    result = df[
        df["Employee Name"]
        .astype(str)
        .str.lower()
        == employee_name.lower()
    ].copy()

    if result.empty:
        return None

    return result.iloc[0].to_dict()


def get_salary_summary(employee_name):
    """
    Return important payroll information
    for an employee.
    """

    data = load_csv_files()
    df = data["salary"]

    result = df[
        df["Employee Name"]
        .astype(str)
        .str.lower()
        == employee_name.lower()
    ].copy()

    if result.empty:
        return None

    row = result.iloc[0]

    return {
        "employee_id": row["Employee ID"],
        "employee_name": row["Employee Name"],
        "month": row["Month"],
        "year": row["Year"],
        "monthly_salary": row["Monthly Salary"],
        "working_days": row["Working Days"],
        "present_days": row["Present Days"],
        "absent_days": row["Absent Days"],
        "leave_days": row["Leave Days"],
        "half_days": row["Half Days"],
        "free_leave_days": row["Free Leave Days"],
        "unpaid_absence_days": row["Unpaid Absence Days"],
        "per_day_salary": row["Per Day Salary"],
        "gross_salary": row["Gross Salary"],
        "absence_deduction": row["Absence Deduction"],
        "leave_deduction": row["Leave Deduction"],
        "employee_pf": row["Employee PF"],
        "other_deduction": row["Other Deduction"],
        "net_salary": row["Net Salary"],
    }


def get_salary_deduction_reason(employee_name):
    """
    Explain why an employee's salary was reduced.
    """

    salary = get_salary_summary(employee_name)

    if salary is None:
        return None

    total_deduction = (
        float(salary["absence_deduction"])
        + float(salary["leave_deduction"])
        + float(salary["employee_pf"])
        + float(salary["other_deduction"])
    )

    return {
        "employee_name": salary["employee_name"],
        "monthly_salary": salary["monthly_salary"],
        "absent_days": salary["absent_days"],
        "free_leave_days": salary["free_leave_days"],
        "unpaid_absence_days": salary["unpaid_absence_days"],
        "absence_deduction": salary["absence_deduction"],
        "leave_deduction": salary["leave_deduction"],
        "employee_pf": salary["employee_pf"],
        "other_deduction": salary["other_deduction"],
        "total_deductions": total_deduction,
        "net_salary": salary["net_salary"],
    }


def get_employees_below_attendance_salary_data():
    """
    Get salary records where attendance is relatively low.
    """

    data = load_csv_files()

    salary_df = data["salary"]
    attendance_df = data["attendance"]

    attendance_df = attendance_df.copy()

    # Count attendance statuses
    summary = (
        attendance_df
        .groupby(["Employee ID", "Employee Name"])
        ["Attendance Status"]
        .value_counts()
        .unstack(fill_value=0)
    )

    if "Present" not in summary.columns:
        summary["Present"] = 0

    if "Weekly Off" not in summary.columns:
        summary["Weekly Off"] = 0

    summary["attendance_percentage"] = (
        summary["Present"]
        /
        (
            len(attendance_df["Date"].unique())
            - summary["Weekly Off"]
        )
        * 100
    )

    summary = summary.reset_index()

    result = salary_df.merge(
        summary[
            [
                "Employee ID",
                "attendance_percentage"
            ]
        ],
        on="Employee ID",
        how="left"
    )

    return result[
        result["attendance_percentage"] < 80
    ].sort_values(
        "attendance_percentage"
    )


def get_highest_salary_employee():
    """
    Find employee with highest monthly salary.
    """

    data = load_csv_files()
    df = data["salary"]

    row = df.loc[
        df["Monthly Salary"].idxmax()
    ]

    return row.to_dict()


if __name__ == "__main__":

    data = load_csv_files()

    employee_df = data["employee_master"]

    if not employee_df.empty:

        employee_name = employee_df.iloc[0][
            "Employee Name"
        ]

        print("\n")
        print("=" * 70)
        print("SALARY SUMMARY")
        print("=" * 70)

        print(
            get_salary_summary(employee_name)
        )

        print("\n")
        print("=" * 70)
        print("SALARY DEDUCTION REASON")
        print("=" * 70)

        print(
            get_salary_deduction_reason(
                employee_name
            )
        )

    print("\n")
    print("=" * 70)
    print("HIGHEST SALARY EMPLOYEE")
    print("=" * 70)

    print(
        get_highest_salary_employee()
    )