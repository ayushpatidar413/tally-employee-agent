from tools.uploaded_employee_tools import (
    find_uploaded_employee,
    find_uploaded_employee_by_id,
    get_all_uploaded_employees,
)


# ============================================================
# EMPLOYEE AGENT
# ============================================================

def employee_agent(
    query: str,
    employee_name: str = "",
    employee_id: str = "",
    intent: str = "employee_details",
):
    """
    Employee Agent

    Handles:
    - Employee details
    - Employee ID
    - Employee count
    - Employee list
    - Employee lookup by name
    - Employee lookup by ID
    """

    # ========================================================
    # EMPLOYEE COUNT
    # ========================================================

    if intent == "employee_count":
        result = get_all_uploaded_employees()

        if not result.get("success"):
            return {
                "success": False,
                "message": "Employee information is not available.",
                "data": None,
            }

        count = result.get("count", 0)

        return {
            "success": True,
            "message": f"Total uploaded employees: {count}",
            "data": {
                "count": count
            },
        }

    # ========================================================
    # EMPLOYEE LIST
    # ========================================================

    if intent == "employee_list":
        result = get_all_uploaded_employees()

        if not result.get("success"):
            return {
                "success": False,
                "message": "Employee information is not available.",
                "data": None,
            }

        employees = result.get("employees", [])

        if not employees:
            return {
                "success": False,
                "message": "No uploaded employees were found.",
                "data": None,
            }

        employee_names = []

        for employee in employees:
            name = employee.get("employee_name")

            if name:
                employee_names.append(str(name))

        return {
            "success": True,
            "message": "Employee list retrieved successfully.",
            "data": {
                "employees": employees,
                "employee_names": employee_names,
                "count": len(employees),
            },
        }

    # ========================================================
    # FIND EMPLOYEE BY ID
    # ========================================================

    if employee_id:
        result = find_uploaded_employee_by_id(employee_id)

        if not result.get("success"):
            return {
                "success": False,
                "message": (
                    f"No uploaded employee found with ID "
                    f"{employee_id}."
                ),
                "data": None,
            }

        employees = result.get("employees", [])

        if not employees:
            return {
                "success": False,
                "message": (
                    f"No uploaded employee found with ID "
                    f"{employee_id}."
                ),
                "data": None,
            }

        return {
            "success": True,
            "message": "Employee found successfully.",
            "data": employees[0],
        }

    # ========================================================
    # FIND EMPLOYEE BY NAME
    # ========================================================

    if employee_name:
        result = find_uploaded_employee(employee_name)

        if not result.get("success"):
            return {
                "success": False,
                "message": (
                    f"No uploaded employee named "
                    f"{employee_name} was found."
                ),
                "data": None,
            }

        employees = result.get("employees", [])

        if not employees:
            return {
                "success": False,
                "message": (
                    f"No uploaded employee named "
                    f"{employee_name} was found."
                ),
                "data": None,
            }

        # If multiple employees match, return all matches.
        if len(employees) > 1:
            return {
                "success": True,
                "message": "Multiple employees found.",
                "data": {
                    "employees": employees,
                    "count": len(employees),
                },
            }

        return {
            "success": True,
            "message": "Employee found successfully.",
            "data": employees[0],
        }

    # ========================================================
    # TRY TO FIND EMPLOYEE FROM QUERY
    # ========================================================

    if query:
        result = find_uploaded_employee(query)

        if result.get("success"):
            employees = result.get("employees", [])

            if len(employees) == 1:
                return {
                    "success": True,
                    "message": "Employee found successfully.",
                    "data": employees[0],
                }

            if len(employees) > 1:
                return {
                    "success": True,
                    "message": "Multiple employees found.",
                    "data": {
                        "employees": employees,
                        "count": len(employees),
                    },
                }

    # ========================================================
    # EMPLOYEE NOT AVAILABLE
    # ========================================================

    return {
        "success": False,
        "message": (
            "Employee information is not available "
            "in the uploaded employee data."
        ),
        "data": None,
    }


# ============================================================
# FORMAT COMPLETE EMPLOYEE DETAILS
# ============================================================

def format_employee_details(employee):
    """
    Convert employee database record into a readable HR response.
    """

    if not employee:
        return "Employee information is not available."

    def value(key, default="Information not available"):
        current = employee.get(key)

        if current is None or str(current).strip() == "":
            return default

        return current

    salary = employee.get("monthly_salary")

    if salary is not None:
        try:
            salary_text = f"₹{float(salary):,.0f}"
        except (ValueError, TypeError):
            salary_text = str(salary)
    else:
        salary_text = "Information not available"

    pf_rate = employee.get("pf_rate")

    if pf_rate is not None:
        try:
            rate = float(pf_rate)

            # Handle both 0.12 and 12 formats.
            if rate <= 1:
                rate *= 100

            pf_rate_text = f"{rate:g}%"
        except (ValueError, TypeError):
            pf_rate_text = str(pf_rate)
    else:
        pf_rate_text = "Information not available"

    employee_pf = employee.get("employee_pf")

    if employee_pf is not None:
        try:
            employee_pf_text = f"₹{float(employee_pf):,.0f}"
        except (ValueError, TypeError):
            employee_pf_text = str(employee_pf)
    else:
        employee_pf_text = "Information not available"

    employer_pf = employee.get("employer_pf")

    if employer_pf is not None:
        try:
            employer_pf_text = f"₹{float(employer_pf):,.0f}"
        except (ValueError, TypeError):
            employer_pf_text = str(employer_pf)
    else:
        employer_pf_text = "Information not available"

    previous_experience = value("previous_experience_years")
    current_experience = value("current_company_experience")
    total_experience = value("total_experience")

    return f"""Employee Details

Name: {value("employee_name")}
Employee ID: {value("employee_id")}
Department: {value("department")}
Designation: {value("designation")}
Employment Type: {value("employment_type")}
Joining Date: {value("joining_date")}
Employment Status: {value("employment_status")}

Salary: {salary_text}
PF Applicable: {value("pf_applicable")}
PF Rate: {pf_rate_text}
Employee PF: {employee_pf_text}
Employer PF: {employer_pf_text}

Previous Experience: {previous_experience} years
Current Company Experience: {current_experience} years
Total Experience: {total_experience} years

Attendance: Attendance information is not available.
Leave: Leave information is not available.
"""