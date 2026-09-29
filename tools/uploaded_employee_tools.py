import json

from database.upload_db import (
    search_uploaded_employee,
    get_uploaded_employees,
)


# ============================================================
# FIND EMPLOYEE
# ============================================================

def find_uploaded_employee(search_text):

    search_text = str(
        search_text or ""
    ).strip()

    if not search_text:

        return {
            "success": False,
            "message": "Employee name or ID is required.",
            "employees": [],
            "count": 0,
        }

    employees = search_uploaded_employee(
        search_text
    )

    if not employees:

        return {
            "success": False,
            "message": (
                f"No uploaded employee found for "
                f"{search_text}"
            ),
            "employees": [],
            "count": 0,
        }

    return {
        "success": True,
        "employees": employees,
        "count": len(employees),
    }


# ============================================================
# FIND EMPLOYEE BY ID
# ============================================================

def find_uploaded_employee_by_id(employee_id):

    employee_id = str(
        employee_id or ""
    ).strip().upper()

    if not employee_id:

        return {
            "success": False,
            "message": "Employee ID is required.",
            "employees": [],
            "count": 0,
        }

    result = find_uploaded_employee(
        employee_id
    )

    if not result.get("success"):

        return result

    employees = [
        employee
        for employee in result["employees"]
        if str(
            employee.get("employee_id", "")
        ).upper() == employee_id
    ]

    if not employees:

        return {
            "success": False,
            "message": (
                f"No uploaded employee found "
                f"with ID {employee_id}"
            ),
            "employees": [],
            "count": 0,
        }

    return {
        "success": True,
        "employees": employees,
        "count": len(employees),
    }


# ============================================================
# FIND EMPLOYEE BY NAME
# ============================================================

def find_uploaded_employee_by_name(
    employee_name
):

    employee_name = str(
        employee_name or ""
    ).strip()

    if not employee_name:

        return {
            "success": False,
            "message": "Employee name is required.",
            "employees": [],
            "count": 0,
        }

    return find_uploaded_employee(
        employee_name
    )


# ============================================================
# GET ALL EMPLOYEES
# ============================================================

def get_all_uploaded_employees(
    limit=10000
):

    employees = get_uploaded_employees(
        limit
    )

    return {
        "success": True,
        "employees": employees,
        "count": len(employees),
    }


# ============================================================
# PARSE EXTRA DATA
# ============================================================

def _get_extra_data(employee):

    extra_data = employee.get(
        "extra_data",
        {}
    )

    if isinstance(extra_data, dict):
        return extra_data

    if isinstance(extra_data, str):

        try:

            parsed = json.loads(
                extra_data
            )

            if isinstance(parsed, dict):
                return parsed

        except (
            json.JSONDecodeError,
            TypeError
        ):
            pass

    return {}


# ============================================================
# NORMALIZE FIELD NAME
# ============================================================

def normalize_field_name(field_name):

    field_name = str(
        field_name or ""
    ).strip().lower()

    field_name = (
        field_name
        .replace("_", " ")
        .replace("-", " ")
    )

    return " ".join(
        field_name.split()
    )


# ============================================================
# FIELD ALIASES
# ============================================================

FIELD_ALIASES = {

    # Salary
    "salary": [
        "salary",
        "monthly salary",
        "monthly pay",
        "monthly income",
        "pay",
    ],

    # PF
    "pf": [
        "pf",
        "provident fund",
        "employee pf",
        "employer pf",
        "pf amount",
    ],

    # Outstanding
    "outstanding": [
        "outstanding",
        "outstanding amount",
        "pending amount",
        "pending payment",
        "amount due",
        "due amount",
        "balance due",
    ],

    # Experience
    "experience": [
        "experience",
        "total experience",
        "previous experience",
        "company experience",
    ],

    # Location
    "location": [
        "location",
        "city",
        "office location",
        "work location",
    ],

    # Manager
    "manager": [
        "manager",
        "reporting manager",
        "supervisor",
        "team manager",
    ],

    # Bonus
    "bonus": [
        "bonus",
        "annual bonus",
        "performance bonus",
    ],
}


# ============================================================
# FIND FIELD IN EMPLOYEE
# ============================================================

def get_employee_field(
    employee,
    requested_field
):
    """
    Search a requested field in an employee record.

    Searches:

    1. Standard database fields
    2. extra_data fields
    """

    if not employee:

        return {
            "found": False,
            "value": None,
            "field": requested_field,
        }

    requested = normalize_field_name(
        requested_field
    )

    # --------------------------------------------------------
    # STANDARD DATABASE FIELDS
    # --------------------------------------------------------

    standard_fields = {}

    for key, value in employee.items():

        if key in {
            "id",
            "extra_data",
            "uploaded_at",
        }:
            continue

        standard_fields[
            normalize_field_name(key)
        ] = value

    # --------------------------------------------------------
    # EXTRA FIELDS
    # --------------------------------------------------------

    extra_data = _get_extra_data(
        employee
    )

    for key, value in extra_data.items():

        standard_fields[
            normalize_field_name(key)
        ] = value

    # --------------------------------------------------------
    # DIRECT FIELD MATCH
    # --------------------------------------------------------

    if requested in standard_fields:

        value = standard_fields[
            requested
        ]

        if value is not None and str(
            value
        ).strip() != "":

            return {
                "found": True,
                "value": value,
                "field": requested_field,
            }

    # --------------------------------------------------------
    # ALIAS MATCH
    # --------------------------------------------------------

    for canonical_field, aliases in (
        FIELD_ALIASES.items()
    ):

        normalized_aliases = [
            normalize_field_name(alias)
            for alias in aliases
        ]

        if requested in normalized_aliases:

            # Search all actual fields
            for actual_field, value in (
                standard_fields.items()
            ):

                if actual_field in normalized_aliases:

                    if (
                        value is not None
                        and str(value).strip() != ""
                    ):

                        return {
                            "found": True,
                            "value": value,
                            "field": actual_field,
                        }

    # --------------------------------------------------------
    # PARTIAL FIELD MATCH
    # --------------------------------------------------------

    for actual_field, value in (
        standard_fields.items()
    ):

        if (
            requested in actual_field
            or actual_field in requested
        ):

            if (
                value is not None
                and str(value).strip() != ""
            ):

                return {
                    "found": True,
                    "value": value,
                    "field": actual_field,
                }

    # --------------------------------------------------------
    # FIELD NOT FOUND
    # --------------------------------------------------------

    return {
        "found": False,
        "value": None,
        "field": requested_field,
    }


# ============================================================
# GET EMPLOYEE FIELD BY NAME
# ============================================================

def get_uploaded_employee_field_by_name(
    employee_name,
    requested_field
):

    result = find_uploaded_employee_by_name(
        employee_name
    )

    if not result.get("success"):

        return {
            "success": False,
            "employee_found": False,
            "field_found": False,
            "message": (
                f"No uploaded employee named "
                f"{employee_name} was found."
            ),
            "value": None,
        }

    employees = result.get(
        "employees",
        []
    )

    if not employees:

        return {
            "success": False,
            "employee_found": False,
            "field_found": False,
            "message": (
                f"No uploaded employee named "
                f"{employee_name} was found."
            ),
            "value": None,
        }

    # --------------------------------------------------------
    # MULTIPLE MATCHES
    # --------------------------------------------------------

    if len(employees) > 1:

        return {
            "success": False,
            "employee_found": True,
            "field_found": False,
            "multiple_matches": True,
            "message": (
                f"Multiple employees matched "
                f"{employee_name}."
            ),
            "employees": employees,
            "value": None,
        }

    employee = employees[0]

    field_result = get_employee_field(
        employee,
        requested_field
    )

    if not field_result["found"]:

        return {
            "success": False,
            "employee_found": True,
            "field_found": False,
            "message": (
                f"{requested_field} information "
                f"is not available in the "
                f"uploaded employee data."
            ),
            "value": None,
            "employee": employee,
        }

    return {
        "success": True,
        "employee_found": True,
        "field_found": True,
        "message": "Employee field found.",
        "value": field_result["value"],
        "field": field_result["field"],
        "employee": employee,
    }


# ============================================================
# GET EMPLOYEE FIELD BY ID
# ============================================================

def get_uploaded_employee_field_by_id(
    employee_id,
    requested_field
):

    result = find_uploaded_employee_by_id(
        employee_id
    )

    if not result.get("success"):

        return {
            "success": False,
            "employee_found": False,
            "field_found": False,
            "message": (
                f"No uploaded employee found "
                f"with ID {employee_id}."
            ),
            "value": None,
        }

    employees = result.get(
        "employees",
        []
    )

    if not employees:

        return {
            "success": False,
            "employee_found": False,
            "field_found": False,
            "message": (
                f"No uploaded employee found "
                f"with ID {employee_id}."
            ),
            "value": None,
        }

    employee = employees[0]

    field_result = get_employee_field(
        employee,
        requested_field
    )

    if not field_result["found"]:

        return {
            "success": False,
            "employee_found": True,
            "field_found": False,
            "message": (
                f"{requested_field} information "
                f"is not available in the "
                f"uploaded employee data."
            ),
            "value": None,
            "employee": employee,
        }

    return {
        "success": True,
        "employee_found": True,
        "field_found": True,
        "message": "Employee field found.",
        "value": field_result["value"],
        "field": field_result["field"],
        "employee": employee,
    }


# ============================================================
# GET AVAILABLE EMPLOYEE FIELDS
# ============================================================

def get_employee_available_fields(
    employee
):

    fields = []

    # Standard database fields
    for key, value in employee.items():

        if key in {
            "id",
            "extra_data",
            "uploaded_at",
        }:
            continue

        if value is not None:

            fields.append(
                str(key)
            )

    # Extra fields
    extra_data = _get_extra_data(
        employee
    )

    for key, value in extra_data.items():

        if value is not None:

            fields.append(
                str(key)
            )

    return sorted(
        set(fields)
    )