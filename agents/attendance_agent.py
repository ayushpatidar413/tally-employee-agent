from tools.uploaded_employee_tools import (
    get_uploaded_employee_field_by_name,
    get_uploaded_employee_field_by_id,
)


def attendance_agent(
    query,
    employee_name="",
    employee_id="",
):
    """
    Attendance Agent.

    Attendance information is taken ONLY from uploaded
    employee data.

    The agent never invents attendance information.
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
    # 2. Detect requested attendance field
    # =========================================================

    if (
        "absent" in query_lower
        or "absence" in query_lower
        or "absent days" in query_lower
    ):
        requested_field = "absent_days"

    elif (
        "present" in query_lower
        or "present days" in query_lower
        or "days present" in query_lower
    ):
        requested_field = "present_days"

    elif (
        "attendance percentage" in query_lower
        or "attendance %" in query_lower
        or "attendance rate" in query_lower
        or "attendance percent" in query_lower
    ):
        requested_field = "attendance_percentage"

    elif (
        "working days" in query_lower
        or "total working days" in query_lower
    ):
        requested_field = "working_days"

    elif (
        "attendance" in query_lower
    ):
        requested_field = "attendance"

    else:
        requested_field = "attendance"

    # =========================================================
    # 3. Get field from uploaded employee data
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
    # 5. Attendance field not available
    # =========================================================

    if not result.get("field_found"):

        return {
            "success": False,
            "message": (
                "Attendance information is not available "
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
    # 7. Format response
    # =========================================================

    field_labels = {
        "attendance": "attendance",
        "attendance_percentage": "attendance percentage",
        "present_days": "present days",
        "absent_days": "absent days",
        "working_days": "working days",
    }

    label = field_labels.get(
        requested_field,
        requested_field,
    )

    # Percentage formatting
    if requested_field == "attendance_percentage":

        try:
            percentage = float(value)

            # Support both 0.95 and 95 formats
            if percentage <= 1:
                percentage = percentage * 100

            formatted_value = f"{percentage:g}%"

        except (TypeError, ValueError):

            formatted_value = str(value)

    else:

        formatted_value = str(value)

    # =========================================================
    # 8. Final response
    # =========================================================

    return {
        "success": True,
        "message": (
            f"{employee_display_name}'s "
            f"{label} is {formatted_value}."
        ),
        "data": {
            "employee_name": employee_display_name,
            "employee_id": actual_employee_id,
            "field": requested_field,
            "value": value,
            "formatted_value": formatted_value,
        },
    }