from tools.uploaded_employee_tools import (
    get_uploaded_employee_field_by_name,
    get_uploaded_employee_field_by_id,
)


def _format_currency(value):
    """Format amount as Indian currency."""

    try:
        amount = float(value)
        return f"₹{amount:,.0f}"
    except (TypeError, ValueError):
        return str(value)


def outstanding_agent(
    query,
    employee_name="",
    employee_id="",
):
    """
    Outstanding Agent.

    Outstanding information is taken ONLY from the uploaded
    employee data.

    It must never calculate outstanding from salary or any
    other field.
    """

    # =========================================================
    # 1. Validate employee
    # =========================================================

    if not employee_name and not employee_id:
        return {
            "success": False,
            "message": "Please provide an employee name or employee ID.",
            "data": {},
        }

    # =========================================================
    # 2. Get outstanding from uploaded data
    # =========================================================

    if employee_id:

        result = get_uploaded_employee_field_by_id(
            employee_id,
            "outstanding",
        )

    else:

        result = get_uploaded_employee_field_by_name(
            employee_name,
            "outstanding",
        )

    # =========================================================
    # 3. Employee not found
    # =========================================================

    if not result.get("employee_found"):

        return {
            "success": False,
            "message": "Employee was not found in the uploaded employee data.",
            "data": {},
        }

    # =========================================================
    # 4. Outstanding not available
    # =========================================================

    if not result.get("field_found"):

        return {
            "success": False,
            "message": (
                "Outstanding information is not available "
                "in the uploaded employee data."
            ),
            "data": {
                "employee": result.get("employee"),
            },
        }

    # =========================================================
    # 5. Get employee information
    # =========================================================

    employee = result.get("employee") or {}

    employee_display_name = employee.get(
        "employee_name",
        employee_name or employee_id,
    )

    actual_employee_id = employee.get(
        "employee_id",
        employee_id,
    )

    outstanding = result.get("value")

    formatted_outstanding = _format_currency(
        outstanding
    )

    # =========================================================
    # 6. Final response
    # =========================================================

    return {
        "success": True,
        "message": (
            f"The outstanding amount for "
            f"{employee_display_name} is "
            f"{formatted_outstanding}."
        ),
        "data": {
            "employee_name": employee_display_name,
            "employee_id": actual_employee_id,
            "outstanding": outstanding,
            "formatted_outstanding": formatted_outstanding,
        },
    }