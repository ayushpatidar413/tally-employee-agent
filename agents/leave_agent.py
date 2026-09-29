from tools.uploaded_employee_tools import (
    get_uploaded_employee_field_by_name,
    get_uploaded_employee_field_by_id,
)


def leave_agent(
    query,
    employee_name="",
    employee_id="",
):
    """
    Leave Agent.

    Uses ONLY uploaded employee data for employee-specific
    leave information.
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

    query_lower = (query or "").lower()

    # =========================================================
    # 2. Detect requested leave field
    # =========================================================

    if (
        "leave balance" in query_lower
        or "remaining leave" in query_lower
        or "leaves remaining" in query_lower
        or "available leave" in query_lower
    ):
        requested_field = "leave_balance"

    elif (
        "paid leave" in query_lower
        or "pl" in query_lower
    ):
        requested_field = "paid_leave"

    elif (
        "sick leave" in query_lower
        or "sick leaves" in query_lower
    ):
        requested_field = "sick_leave"

    elif (
        "casual leave" in query_lower
        or "casual leaves" in query_lower
    ):
        requested_field = "casual_leave"

    elif (
        "unpaid leave" in query_lower
        or "unpaid leaves" in query_lower
    ):
        requested_field = "unpaid_leave"

    elif (
        "leave taken" in query_lower
        or "leaves taken" in query_lower
        or "total leave" in query_lower
        or "total leaves" in query_lower
    ):
        requested_field = "leaves_taken"

    elif "leave" in query_lower:
        requested_field = "leave"

    else:
        requested_field = "leave"

    # =========================================================
    # 3. Get leave field from uploaded data
    # =========================================================

    if employee_id:
        result = get_uploaded_employee_field_by_id(
            employee_id,
            requested_field,
        )
    else:
        result = get_uploaded_employee_field_by_name(
            employee_name,
            requested_field,
        )

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
    # 5. Leave information unavailable
    # =========================================================

    if not result.get("field_found"):
        return {
            "success": False,
            "message": (
                "Leave information is not available "
                "in the uploaded employee data."
            ),
            "data": {
                "employee": result.get("employee"),
            },
        }

    # =========================================================
    # 6. Employee information
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

    value = result.get("value")

    # =========================================================
    # 7. Field labels
    # =========================================================

    field_labels = {
        "leave": "leave information",
        "leave_balance": "leave balance",
        "paid_leave": "paid leave",
        "sick_leave": "sick leave",
        "casual_leave": "casual leave",
        "unpaid_leave": "unpaid leave",
        "leaves_taken": "leaves taken",
    }

    label = field_labels.get(
        requested_field,
        requested_field,
    )

    # =========================================================
    # 8. Final response
    # =========================================================

    return {
        "success": True,
        "message": (
            f"{employee_display_name}'s "
            f"{label} is {value}."
        ),
        "data": {
            "employee_name": employee_display_name,
            "employee_id": actual_employee_id,
            "field": requested_field,
            "value": value,
        },
    }