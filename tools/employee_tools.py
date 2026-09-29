from document_loader import load_csv_files


def get_employee(employee_name=None, employee_id=None):
    """
    Find an employee using employee name or employee ID.
    """

    data = load_csv_files()
    df = data["employee_master"]

    if employee_id:
        result = df[
            df["Employee ID"].astype(str).str.upper()
            == employee_id.upper()
        ]

    elif employee_name:
        result = df[
            df["Employee Name"]
            .astype(str)
            .str.lower()
            .str.contains(employee_name.lower(), na=False)
        ]

    else:
        raise ValueError(
            "Please provide employee_name or employee_id"
        )

    return result


def get_employee_salary(employee_name):
    """
    Get an employee's monthly salary.
    """

    data = load_csv_files()
    df = data["employee_master"]

    result = df[
        df["Employee Name"]
        .astype(str)
        .str.lower()
        == employee_name.lower()
    ]

    if result.empty:
        return None

    employee = result.iloc[0]

    return {
        "employee_id": employee["Employee ID"],
        "employee_name": employee["Employee Name"],
        "monthly_salary": employee["Monthly Salary"]
    }


def get_employee_experience(employee_name):
    """
    Get previous, current and total experience.
    """

    data = load_csv_files()
    df = data["employee_master"]

    result = df[
        df["Employee Name"]
        .astype(str)
        .str.lower()
        == employee_name.lower()
    ]

    if result.empty:
        return None

    employee = result.iloc[0]

    return {
        "employee_id": employee["Employee ID"],
        "employee_name": employee["Employee Name"],
        "previous_experience": employee[
            "Previous Experience Years"
        ],
        "current_company_experience": employee[
            "Current Company Experience"
        ],
        "total_experience": employee[
            "Total Experience"
        ]
    }


if __name__ == "__main__":

    print("\nEMPLOYEE TEST")
    print("=" * 60)

    result = get_employee(employee_id="EMP001")

    print(result)

    print("\nSALARY TEST")
    print("=" * 60)

    if not result.empty:

        name = result.iloc[0]["Employee Name"]

        print(
            get_employee_salary(name)
        )

        print("\nEXPERIENCE TEST")
        print("=" * 60)

        print(
            get_employee_experience(name)
        )