from document_loader import load_csv_files


def get_employee_attendance(employee_name):
    """
    Get all attendance records for an employee.
    """

    data = load_csv_files()
    df = data["attendance"]

    result = df[
        df["Employee Name"]
        .astype(str)
        .str.lower()
        == employee_name.lower()
    ].copy()

    return result


def get_attendance_summary(employee_name):
    """
    Calculate attendance summary for an employee.
    """

    data = load_csv_files()
    df = data["attendance"]

    result = df[
        df["Employee Name"]
        .astype(str)
        .str.lower()
        == employee_name.lower()
    ].copy()

    if result.empty:
        return None

    status_counts = (
        result["Attendance Status"]
        .value_counts()
        .to_dict()
    )

    return {
        "employee_name": employee_name,
        "total_records": len(result),
        "present_days": status_counts.get("Present", 0),
        "absent_days": status_counts.get("Absent", 0),
        "leave_days": status_counts.get("Leave", 0),
        "half_days": status_counts.get("Half Day", 0),
        "weekly_offs": status_counts.get("Weekly Off", 0),
    }


def get_attendance_by_date(employee_name, date):
    """
    Check attendance for an employee on a specific date.
    """

    data = load_csv_files()
    df = data["attendance"]

    result = df[
        (df["Employee Name"]
         .astype(str)
         .str.lower()
         == employee_name.lower())
        &
        (df["Date"].astype(str) == str(date))
    ]

    return result


if __name__ == "__main__":

    data = load_csv_files()

    employee_df = data["employee_master"]

    if not employee_df.empty:

        name = employee_df.iloc[0]["Employee Name"]

        print("\nATTENDANCE SUMMARY")
        print("=" * 60)

        print(
            get_attendance_summary(name)
        )

        print("\nFIRST 10 ATTENDANCE RECORDS")
        print("=" * 60)

        print(
            get_employee_attendance(name).head(10)
        )