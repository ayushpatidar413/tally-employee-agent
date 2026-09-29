from tools.uploaded_employee_tools import (
    get_uploaded_employee_field_by_name,
    get_uploaded_employee_field_by_id,
)


def _format_salary(value):
    """Format salary as Indian currency."""

    try:
        amount = float(value)
        return f"₹{amount:,.0f}"
    except (TypeError, ValueError):
        return str(value)


def salary_agent(
    query,
    employee_name="",
    employee_id="",
):
    """
    Salary Agent.

    Employee-specific salary information is taken only
    from the uploaded employee data.
    """

    # =========================================================
    # 1. Get salary by employee ID
    # =========================================================

    if employee_id:

        result = get_uploaded_employee_field_by_id(
            employee_id,
            "salary",
        )

    # =========================================================
    # 2. Get salary by employee name
    # =========================================================

    elif employee_name:

        result = get_uploaded_employee_field_by_name(
            employee_name,
            "salary",
        )

    # =========================================================
    # 3. No employee supplied
    # =========================================================

    else:

        return {
            "success": False,
            "message": "Please provide an employee name or employee ID.",
            "data": {},
        }

    # =========================================================
    # 4. Employee not found
    # =========================================================

    if not result.get("employee_found"):

        return {
            "success": False,
            "message": "Employee was not found in the uploaded employee data.",
            "data": {},
        }

    # =========================================================
    # 5. Salary not available
    # =========================================================

    if not result.get("field_found"):

        return {
            "success": False,
            "message": (
                "Salary information is not available "
                "in the uploaded employee data."
            ),
            "data": {
                "employee": result.get("employee"),
            },
        }

    # =========================================================
    # 6. Get employee information
    # =========================================================

    employee = result.get("employee") or {}

    salary = result.get("value")

    employee_display_name = employee.get(
        "employee_name",
        employee_name or employee_id,
    )

    actual_employee_id = employee.get(
        "employee_id",
        employee_id,
    )

    # =========================================================
    # 7. Format salary
    # =========================================================

    formatted_salary = _format_salary(salary)

    # =========================================================
    # 8. Final response
    # =========================================================

    return {
        "success": True,
        "message": (
            f"The monthly salary of {employee_display_name} "
            f"is {formatted_salary}."
        ),
        "data": {
            "employee_name": employee_display_name,
            "employee_id": actual_employee_id,
            "salary": salary,
            "formatted_salary": formatted_salary,
        },
    }