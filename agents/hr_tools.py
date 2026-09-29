
from typing import Optional

from langchain_core.tools import tool
from tools.uploaded_employee_tools import (
    find_uploaded_employee,
    find_uploaded_employee_by_id,
    find_uploaded_employee_by_name,
    get_all_uploaded_employees,
)
from tools.employee_db_tools import (
    get_employee_by_id,
    get_employee_by_name,
    get_employee_salary,
    
)

from tools.attendance_db_tools import (
    get_employee_attendance,
    get_attendance_summary,
    get_attendance_by_date,
)

from tools.leave_db_tools import (
    get_employee_leaves,
    get_leave_summary,
    get_unpaid_leaves,
    get_leave_ranking,
    get_employees_by_leave_days,
)

from tools.salary_db_tools import (
    get_salary_summary,
    get_salary_deduction_reason,
    get_highest_salary_employee,
    get_salary_ranking,
)

from tools.pf_db_tools import (
    get_pf_summary,
    get_total_pf,
)

from tools.summary_db_tools import (
    get_employee_monthly_summary,
    get_low_attendance_employees,
    get_most_experienced_employees,
)



# ============================================================
# EMPLOYEE TOOLS
# ============================================================

@tool
def employee_by_id(employee_id: str):
    """
    Find an employee using Employee ID.

    Example:
        EMP001
    """

    result = get_employee_by_id(employee_id)

    if result is None:
        return f"No employee found with ID {employee_id}"

    return result


@tool
def employee_by_name(employee_name: str):
    """
    Find employee information using employee name.
    """

    result = get_employee_by_name(employee_name)

    if not result:
        return f"No employee found with name {employee_name}"

    return result


@tool
def employee_salary(employee_name: str):
    """
    Get monthly salary of an employee.
    """

    result = get_employee_salary(employee_name)

    if result is None:
        return f"No salary information found for {employee_name}"

    return result


@tool
def employee_experience(employee_name: str):
    """
    Get previous, current company, and total experience
    for an employee.
    """

    result = get_employee_by_name(employee_name)

    if not isinstance(result, dict):
        return {
            "success": False,
            "message": f"Employee {employee_name} not found."
        }

    if not result.get("success"):
        return result

    employees = result.get("employees", [])

    if not employees:
        return {
            "success": False,
            "message": f"Employee {employee_name} not found."
        }

    employee = employees[0]

    return {
        "success": True,
        "employee_id": employee.get("employee_id"),
        "employee_name": employee.get("employee_name"),
        "previous_experience_years": employee.get(
            "previous_experience_years"
        ),
        "current_company_experience": employee.get(
            "current_company_experience"
        ),
        "total_experience": employee.get(
            "total_experience"
        )
    }


# ============================================================
# UPLOADED EMPLOYEE SEARCH
# ============================================================

@tool
def uploaded_employee_by_id(employee_id: str):
    """
    Find an employee from dynamically uploaded CSV
    or Excel data using Employee ID.
    """

    result = find_uploaded_employee_by_id(employee_id)

    if not result.get("success"):
        return result.get(
            "message",
            f"No uploaded employee found with ID {employee_id}"
        )

    return result


@tool
def uploaded_employee_by_name(employee_name: str):
    """
    Find an employee from dynamically uploaded CSV
    or Excel data using employee name.
    """

    result = find_uploaded_employee_by_name(employee_name)

    if not result.get("success"):
        return result.get(
            "message",
            f"No uploaded employee found for {employee_name}"
        )

    return result


# ============================================================
# ALL UPLOADED EMPLOYEES
# ============================================================

@tool
def all_uploaded_employees(limit: int = 10000):
    """
    Get employees that were dynamically uploaded
    through CSV or Excel files.
    """

    return get_all_uploaded_employees(limit)



# ============================================================
# ATTENDANCE TOOLS
# ============================================================

@tool
def attendance_summary(
    employee_name: str,
    month: Optional[int] = None,
    year: Optional[int] = None
):
    """
    Get attendance summary of an employee.

    If month and year are provided,
    return attendance for that specific month.
    """

    result = get_attendance_summary(
        employee_name,
        month,
        year
    )

    if result is None:
        return f"No attendance information found for {employee_name}"

    return result


@tool
def employee_attendance(
    employee_name: str,
    month: Optional[int] = None,
    year: Optional[int] = None
):
    """
    Get attendance records of an employee.

    Optional month and year can be provided.
    """

    result = get_employee_attendance(
        employee_name,
        month,
        year
    )

    if not result:
        return f"No attendance records found for {employee_name}"

    return result


@tool
def attendance_by_date(
    employee_name: str,
    date: str
):
    """
    Get attendance of an employee on a specific date.

    Date format:
        YYYY-MM-DD
    """

    result = get_attendance_by_date(
        employee_name,
        date
    )

    if not result:
        return (
            f"No attendance found for "
            f"{employee_name} on {date}"
        )

    return result


# ============================================================
# LEAVE TOOLS
# ============================================================

@tool
def employee_leaves(employee_name: str):
    """
    Get leave records of an employee.
    """

    result = get_employee_leaves(employee_name)

    if not result:
        return f"No leave records found for {employee_name}"

    return result


@tool
def employee_leave_summary(employee_name: str):
    """
    Get paid and unpaid leave summary.
    """

    result = get_leave_summary(employee_name)

    if result is None:
        return f"No leave information found for {employee_name}"

    return result


@tool
def unpaid_leave_records():
    """
    Get all unpaid leave records.
    """

    return get_unpaid_leaves()


# ============================================================
# SALARY TOOLS
# ============================================================

@tool
def employee_salary_summary(
    employee_name: str,
    month: Optional[str] = None,
    year: Optional[int] = None
):
    """
    Get complete salary information.

    Example:
        employee_salary_summary(
            "Rajesh Sharma",
            "August",
            2026
        )
    """

    result = get_salary_summary(
        employee_name,
        month,
        year
    )

    if result is None:
        return (
            f"No salary record found for "
            f"{employee_name}"
        )

    return result


@tool
def salary_deduction_reason(
    employee_name: str,
    month: Optional[str] = None,
    year: Optional[int] = None
):
    """
    Explain salary deductions for an employee.

    Optional month and year can be provided.
    """

    result = get_salary_deduction_reason(
        employee_name,
        month,
        year
    )

    if result is None:
        return (
            f"No salary information found "
            f"for {employee_name}"
        )

    return result


@tool
def highest_salary_employee():
    """
    Find the employee with the highest monthly salary.
    """

    return get_highest_salary_employee()


@tool
def salary_ranking(
    limit: int = 5,
    order: str = "DESC"
):
    """
    Get employees ranked by salary.

    limit = number of employees
    order = DESC for highest first,
            ASC for lowest first
    """

    return get_salary_ranking(
        limit,
        order
    )


@tool
def leave_ranking(
    limit: int = 5,
    order: str = "DESC"
):
    """
    Get employees ranked by total leave days.

    limit = number of employees
    order = DESC for highest leave first,
            ASC for lowest leave first
    """

    return get_leave_ranking(
        limit,
        order
    )


@tool
def employees_by_leave_days(
    leave_days: int
):
    """
    Find employees whose total leave days
    exactly match the requested number.
    """

    return get_employees_by_leave_days(
        leave_days
    )


# ============================================================
# PF TOOLS
# ============================================================

@tool
def employee_pf_summary(
    employee_name: str,
    month: Optional[str] = None,
    year: Optional[int] = None
):
    """
    Get PF information of an employee.

    Month and year are optional.

    Example:
        employee_pf_summary(
            "Rajesh Sharma",
            "August",
            2026
        )
    """

    result = get_pf_summary(
        employee_name,
        month,
        year
    )

    if result is None:
        return (
            f"No PF information found "
            f"for {employee_name}"
        )

    return result


@tool
def total_pf():
    """
    Get total employee PF,
    employer PF and total PF.
    """

    return get_total_pf()


# ============================================================
# MONTHLY SUMMARY TOOLS
# ============================================================

@tool
def employee_monthly_summary(
    employee_name: str
):
    """
    Get complete monthly HR and payroll summary.
    """

    result = get_employee_monthly_summary(
        employee_name
    )

    if result is None:
        return (
            f"No monthly summary found "
            f"for {employee_name}"
        )

    return result


@tool
def low_attendance_employees(
    limit: int = 20
):
    """
    Find employees whose attendance is below 80%.
    """

    return get_low_attendance_employees(
        limit
    )


@tool
def most_experienced_employees(
    limit: int = 10
):
    """
    Find employees with the highest total experience.
    """

    return get_most_experienced_employees(
        limit
    )


# ============================================================
# TOOL LIST
# ============================================================

HR_TOOLS = [

    # Employee
    employee_by_id,
    employee_by_name,
    employee_salary,
    employee_experience,

    # Dynamic uploaded employees
    uploaded_employee_by_id,
    uploaded_employee_by_name,
    
    all_uploaded_employees,

    # Attendance
    attendance_summary,
    employee_attendance,
    attendance_by_date,

    # Leave
    employee_leaves,
    employee_leave_summary,
    unpaid_leave_records,

    # Salary
    employee_salary_summary,
    salary_deduction_reason,
    highest_salary_employee,
    salary_ranking,

    # Leave ranking
    leave_ranking,
    employees_by_leave_days,

    # PF
    employee_pf_summary,
    total_pf,

    # Monthly summary
    employee_monthly_summary,
    low_attendance_employees,
    most_experienced_employees,
]