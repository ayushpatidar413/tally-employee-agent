from document_loader import load_csv_files


def validate_data(data):

    print("\n")
    print("=" * 70)
    print("DATA VALIDATION")
    print("=" * 70)

    # --------------------------------------------------
    # Employee Master
    # --------------------------------------------------

    employee_df = data["employee_master"]

    print("\nEmployee Master")
    print("-" * 40)

    print("Employees:", len(employee_df))

    if len(employee_df) == 200:
        print("✓ 200 employees found")
    else:
        print("⚠ Expected 200 employees")

    required_employee_columns = [
        "Employee ID",
        "Employee Name",
        "Department",
        "Designation",
        "Joining Date",
        "Monthly Salary",
        "Previous Experience Years",
        "Current Company Experience",
        "Total Experience",
    ]

    for column in required_employee_columns:

        if column in employee_df.columns:
            print(f"✓ {column}")
        else:
            print(f"✗ Missing: {column}")

    # --------------------------------------------------
    # Attendance
    # --------------------------------------------------

    attendance_df = data["attendance"]

    print("\nAttendance")
    print("-" * 40)

    print("Attendance rows:", len(attendance_df))

    expected_attendance = 200 * 31

    if len(attendance_df) == expected_attendance:
        print(f"✓ {expected_attendance} attendance records found")
    else:
        print(
            f"⚠ Expected {expected_attendance} "
            f"attendance records"
        )

    # --------------------------------------------------
    # Leave
    # --------------------------------------------------

    leave_df = data["leave"]

    print("\nLeave Records")
    print("-" * 40)

    print("Leave records:", len(leave_df))

    # --------------------------------------------------
    # Salary
    # --------------------------------------------------

    salary_df = data["salary"]

    print("\nSalary Records")
    print("-" * 40)

    print("Salary records:", len(salary_df))

    # --------------------------------------------------
    # PF
    # --------------------------------------------------

    pf_df = data["pf"]

    print("\nPF Records")
    print("-" * 40)

    print("PF records:", len(pf_df))

    # --------------------------------------------------
    # Monthly Summary
    # --------------------------------------------------

    summary_df = data["monthly_summary"]

    print("\nMonthly Summary")
    print("-" * 40)

    print("Summary records:", len(summary_df))

    print("\n" + "=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":

    data = load_csv_files()

    validate_data(data)