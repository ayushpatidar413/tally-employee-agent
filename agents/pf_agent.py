from tools.uploaded_employee_tools import (
    get_uploaded_employee_field_by_name,
    get_uploaded_employee_field_by_id,
)


def _format_currency(value):
    """Format a numeric value as Indian currency."""

    try:
        amount = float(value)
        return f"₹{amount:,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _format_percentage(value):
    """Format PF rate as percentage."""

    try:
        rate = float(value)

        # Database may store 0.12 or 12
        if rate <= 1:
            rate = rate * 100

        return f"{rate:g}%"

    except (TypeError, ValueError):
        return str(value)


def _get_field_by_name(employee_name, field):
    return get_uploaded_employee_field_by_name(
        employee_name,
        field,
    )


def _get_field_by_id(employee_id, field):
    return get_uploaded_employee_field_by_id(
        employee_id,
        field,
    )


def pf_agent(
    query,
    employee_name="",
    employee_id="",
):
    """
    PF Agent.

    Uses only uploaded employee data for employee-specific
    PF information.
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
    # 2. Detect requested PF information
    # =========================================================

    query_lower = (query or "").lower()

    if "rate" in query_lower or "percentage" in query_lower:

        requested_field = "pf_rate"

    elif (
        "employer pf" in query_lower
        or "employer contribution" in query_lower
        or "company pf" in query_lower
    ):

        requested_field = "employer_pf"

    elif (
        "employee pf" in query_lower
        or "employee contribution" in query_lower
        or "my pf" in query_lower
    ):

        requested_field = "employee_pf"

    elif "applicable" in query_lower:

        requested_field = "pf_applicable"

    else:

        # Generic PF question
        requested_field = "employee_pf"

    # =========================================================
    # 3. Get requested field
    # =========================================================

    if employee_id:

        result = _get_field_by_id(
            employee_id,
            requested_field,
        )

    else:

        result = _get_field_by_name(
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
    # 5. Requested PF field unavailable
    # =========================================================

    if not result.get("field_found"):

        field_display = {
            "employee_pf": "Employee PF",
            "employer_pf": "Employer PF",
            "pf_rate": "PF rate",
            "pf_applicable": "PF applicability",
        }.get(
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
    # 7. Format response based on field
    # =========================================================

    if requested_field == "employee_pf":

        formatted_value = _format_currency(value)

        message = (
            f"The employee PF contribution of "
            f"{employee_display_name} is {formatted_value}."
        )

    elif requested_field == "employer_pf":

        formatted_value = _format_currency(value)

        message = (
            f"The employer PF contribution for "
            f"{employee_display_name} is {formatted_value}."
        )

    elif requested_field == "pf_rate":

        formatted_value = _format_percentage(value)

        message = (
            f"The PF rate for "
            f"{employee_display_name} is {formatted_value}."
        )

    elif requested_field == "pf_applicable":

        formatted_value = str(value)

        message = (
            f"PF applicability for "
            f"{employee_display_name} is {formatted_value}."
        )

    else:

        formatted_value = str(value)

        message = (
            f"The PF information for "
            f"{employee_display_name} is {formatted_value}."
        )

    # =========================================================
    # 8. Final response
    # =========================================================

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