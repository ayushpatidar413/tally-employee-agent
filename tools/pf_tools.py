from document_loader import load_csv_files


def get_pf_record(employee_name):
    """
    Get PF information for an employee.
    """

    data = load_csv_files()
    df = data["pf"]

    result = df[
        df["Employee Name"]
        .astype(str)
        .str.lower()
        == employee_name.lower()
    ].copy()

    if result.empty:
        return None

    return result.iloc[0].to_dict()


def get_pf_summary(employee_name):
    """
    Return employee and employer PF details.
    """

    record = get_pf_record(employee_name)

    if record is None:
        return None

    return {
        "employee_id": record["Employee ID"],
        "employee_name": record["Employee Name"],
        "month": record["Month"],
        "year": record["Year"],
        "pf_applicable": record["PF Applicable"],
        "pf_rate": record["PF Rate"],
        "pf_wage": record["PF Wage"],
        "employee_pf": record["Employee PF"],
        "employer_pf": record["Employer PF"],
        "total_pf": record["Total PF"],
        "pf_status": record["PF Status"],
    }


def get_total_pf():
    """
    Calculate total PF generated
    across all employees.
    """

    data = load_csv_files()
    df = data["pf"]

    return {
        "employee_pf_total": df["Employee PF"].sum(),
        "employer_pf_total": df["Employer PF"].sum(),
        "total_pf": df["Total PF"].sum(),
    }


def get_pf_applicable_employees():
    """
    Return employees for whom PF is applicable.
    """

    data = load_csv_files()
    df = data["pf"]

    result = df[
        df["PF Applicable"]
        .astype(str)
        .str.lower()
        == "yes"
    ].copy()

    return result


if __name__ == "__main__":

    data = load_csv_files()

    employee_df = data["employee_master"]

    if not employee_df.empty:

        employee_name = employee_df.iloc[0][
            "Employee Name"
        ]

        print("\n")
        print("=" * 70)
        print("PF SUMMARY")
        print("=" * 70)

        print(
            get_pf_summary(employee_name)
        )

    print("\n")
    print("=" * 70)
    print("TOTAL PF")
    print("=" * 70)

    print(
        get_total_pf()
    )

    print("\n")
    print("=" * 70)
    print("PF APPLICABLE EMPLOYEES")
    print("=" * 70)

    print(
        get_pf_applicable_employees().head(10)
    )