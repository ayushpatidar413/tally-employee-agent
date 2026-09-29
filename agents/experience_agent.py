from tools.uploaded_employee_tools import (
    get_uploaded_employee_field_by_name,
    get_uploaded_employee_field_by_id,
)


def _format_years(value):
    """Format experience years."""

    try:
        years = float(value)
        return f"{years:g} years"
    except (TypeError, ValueError):
        return str(value)


def _get_field(employee_name="", employee_id="", field=""):
    """Get an employee field from uploaded data."""

    if employee_id:
        return get_uploaded_employee_field_by_id(
            employee_id,
            field,
        )

    return get_uploaded_employee_field_by_name(
        employee_name,
        field,
    )


def experience_agent(
    query,
    employee_name="",
    employee_id="",
):
    """
    Experience Agent.

    Uses only uploaded employee data for employee-specific
    experience information.
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
    # 2. Get employee first
    # =========================================================

    employee_result = _get_field(
        employee_name=employee_name,
        employee_id=employee_id,
        field="total_experience",
    )

    # =========================================================
    # 3. Employee not found
    # =========================================================

    if not employee_result.get("employee_found"):

        return {
            "success": False,
            "message": "Employee was not found in the uploaded employee data.",
            "data": {},
        }

    employee = employee_result.get("employee") or {}

    employee_display_name = employee.get(
        "employee_name",
        employee_name or employee_id,
    )

    actual_employee_id = employee.get(
        "employee_id",
        employee_id,
    )

    query_lower = (query or "").lower()

    # =========================================================
    # 4. Determine requested experience
    # =========================================================

    if (
        "previous experience" in query_lower
        or "previous work experience" in query_lower
        or "before joining" in query_lower
    ):

        requested_field = "previous_experience_years"

    elif (
        "current company experience" in query_lower
        or "company experience" in query_lower
        or "experience in current company" in query_lower
    ):

        requested_field = "current_company_experience"

    elif (
        "total experience" in query_lower
        or "overall experience" in query_lower
        or "overall work experience" in query_lower
    ):

        requested_field = "total_experience"

    else:

        # Generic experience question.
        # We will return the complete experience breakdown.
        requested_field = "all_experience"

    # =========================================================
    # 5. Single experience field
    # =========================================================

    if requested_field != "all_experience":

        result = _get_field(
            employee_name=employee_name,
            employee_id=employee_id,
            field=requested_field,
        )

        if not result.get("field_found"):

            field_names = {
                "previous_experience_years": "Previous experience",
                "current_company_experience": "Current company experience",
                "total_experience": "Total experience",
            }

            field_display = field_names.get(
                requested_field,
                requested_field,
            )

            return {
                "success": False,
                "message": (
                    f"{field_display} information is not available "
                    "in the uploaded employee data."
                ),
                "data": {
                    "employee": employee,
                },
            }

        value = result.get("value")
        formatted_value = _format_years(value)

        field_labels = {
            "previous_experience_years": "previous experience",
            "current_company_experience": "current company experience",
            "total_experience": "total experience",
        }

        label = field_labels[requested_field]

        message = (
            f"{employee_display_name} has "
            f"{formatted_value} of {label}."
        )

        return {
            "success": True,
            "message": message,
            "data": {
                "employee_name": employee_display_name,
                "employee_id": actual_employee_id,
                "field": requested_field,
                "value": value,
                "formatted_value": formatted_value,
            },
        }

    # =========================================================
    # 6. Complete experience breakdown
    # =========================================================

    previous_result = _get_field(
        employee_name=employee_name,
        employee_id=employee_id,
        field="previous_experience_years",
    )

    current_result = _get_field(
        employee_name=employee_name,
        employee_id=employee_id,
        field="current_company_experience",
    )

    total_result = _get_field(
        employee_name=employee_name,
        employee_id=employee_id,
        field="total_experience",
    )

    previous_available = previous_result.get("field_found")
    current_available = current_result.get("field_found")
    total_available = total_result.get("field_found")

    if not (
        previous_available
        or current_available
        or total_available
    ):

        return {
            "success": False,
            "message": (
                "Experience information is not available "
                "in the uploaded employee data."
            ),
            "data": {
                "employee": employee,
            },
        }

    # =========================================================
    # 7. Build experience response
    # =========================================================

    parts = []

    if previous_available:
        previous_value = previous_result.get("value")
        parts.append(
            f"Previous experience: {_format_years(previous_value)}"
        )

    if current_available:
        current_value = current_result.get("value")
        parts.append(
            f"Current company experience: {_format_years(current_value)}"
        )

    if total_available:
        total_value = total_result.get("value")
        parts.append(
            f"Total experience: {_format_years(total_value)}"
        )

    message = (
        f"Experience details for {employee_display_name}:\n"
        + "\n".join(parts)
    )

    return {
        "success": True,
        "message": message,
        "data": {
            "employee_name": employee_display_name,
            "employee_id": actual_employee_id,
            "previous_experience": (
                previous_result.get("value")
                if previous_available
                else None
            ),
            "current_company_experience": (
                current_result.get("value")
                if current_available
                else None
            ),
            "total_experience": (
                total_result.get("value")
                if total_available
                else None
            ),
        },
    }