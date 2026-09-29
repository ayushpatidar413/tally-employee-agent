from document_loader import load_csv_files


def get_employee_leaves(employee_name):
    """
    Get all leave records for an employee.
    """

    data = load_csv_files()
    df = data["leave"]

    result = df[
        df["Employee Name"]
        .astype(str)
        .str.lower()
        == employee_name.lower()
    ].copy()

    return result


def get_leave_summary(employee_name):
    """
    Get leave breakdown for an employee.
    """

    data = load_csv_files()
    df = data["leave"]

    result = df[
        df["Employee Name"]
        .astype(str)
        .str.lower()
        == employee_name.lower()
    ].copy()

    if result.empty:
        return None

    leave_type_counts = (
        result["Leave Type"]
        .value_counts()
        .to_dict()
    )

    paid_count = len(
        result[
            result["Paid/Unpaid"]
            .astype(str)
            .str.lower()
            == "paid"
        ]
    )

    unpaid_count = len(
        result[
            result["Paid/Unpaid"]
            .astype(str)
            .str.lower()
            == "unpaid"
        ]
    )

    return {
        "employee_name": employee_name,
        "total_leave_records": len(result),
        "leave_types": leave_type_counts,
        "paid_leave_records": paid_count,
        "unpaid_leave_records": unpaid_count,
    }


def get_unpaid_leave_employees():
    """
    Find employees who have unpaid leave.
    """

    data = load_csv_files()
    df = data["leave"]

    result = df[
        df["Paid/Unpaid"]
        .astype(str)
        .str.lower()
        == "unpaid"
    ].copy()

    return result


if __name__ == "__main__":

    data = load_csv_files()

    employee_df = data["employee_master"]

    if not employee_df.empty:

        name = employee_df.iloc[0]["Employee Name"]

        print("\nLEAVE SUMMARY")
        print("=" * 60)

        print(
            get_leave_summary(name)
        )

        print("\nLEAVE RECORDS")
        print("=" * 60)

        print(
            get_employee_leaves(name)
        )

    print("\nUNPAID LEAVE EMPLOYEES")
    print("=" * 60)

    print(
        get_unpaid_leave_employees().head(20)
    )