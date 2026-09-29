import re


def general_hr_agent(query):
    """
    General HR Agent.

    Handles general HR concepts only.
    It does not return employee-specific data.
    """

    query_lower = (query or "").strip().lower()

    # Remove punctuation such as ?, !, .
    query_lower = re.sub(r"[^a-z0-9\s-]", "", query_lower)

    # Normalize multiple spaces
    query_lower = " ".join(query_lower.split())

    # ============================================================
    # PF
    # ============================================================

    if (
        query_lower == "pf"
        or query_lower == "what is pf"
        or "what is provident fund" in query_lower
        or "what is epf" in query_lower
    ):
        return {
            "success": True,
            "message": (
                "PF (Provident Fund) is a retirement savings benefit "
                "where eligible employees and employers contribute "
                "a specified amount toward the employee's provident fund."
            ),
            "data": {
                "topic": "PF",
            },
        }

    # ============================================================
    # GROSS SALARY
    # ============================================================

    if (
        "gross salary" in query_lower
        or "what is gross salary" in query_lower
    ):
        return {
            "success": True,
            "message": (
                "Gross salary is the total salary amount before "
                "deductions such as employee PF, professional tax, "
                "income tax, or other applicable deductions."
            ),
            "data": {
                "topic": "Gross Salary",
            },
        }

    # ============================================================
    # NET SALARY
    # ============================================================

    if (
        "net salary" in query_lower
        or "what is net salary" in query_lower
        or "take home salary" in query_lower
    ):
        return {
            "success": True,
            "message": (
                "Net salary, also called take-home salary, is the "
                "amount an employee receives after applicable "
                "deductions are subtracted from gross salary."
            ),
            "data": {
                "topic": "Net Salary",
            },
        }

    # ============================================================
    # OUTSTANDING
    # ============================================================

    if (
        "outstanding" in query_lower
        or "what is outstanding" in query_lower
        or "outstanding amount" in query_lower
    ):
        return {
            "success": True,
            "message": (
                "Outstanding amount generally refers to money that "
                "is still pending or due. In an employee dataset, "
                "it should be treated as a separate uploaded field "
                "and should not be assumed to be the employee's salary."
            ),
            "data": {
                "topic": "Outstanding",
            },
        }

    # ============================================================
    # ATTENDANCE
    # ============================================================

    if (
        "what is attendance" in query_lower
        or query_lower == "attendance"
        or "employee attendance" in query_lower
    ):
        return {
            "success": True,
            "message": (
                "Employee attendance records the employee's presence "
                "and absence during the working period. It may include "
                "present days, absent days, working days, and attendance percentage."
            ),
            "data": {
                "topic": "Attendance",
            },
        }

    # ============================================================
    # LEAVE
    # ============================================================

    if (
        "what is leave" in query_lower
        or query_lower == "leave"
        or "employee leave" in query_lower
        or "leave balance" in query_lower
    ):
        return {
            "success": True,
            "message": (
                "Employee leave refers to approved or available time "
                "off from work. Organizations may maintain different "
                "leave types such as casual leave, sick leave, paid leave, "
                "and unpaid leave."
            ),
            "data": {
                "topic": "Leave",
            },
        }

    # ============================================================
    # EMPLOYEE ID
    # ============================================================

    if (
        "employee id" in query_lower
        or "what is employee id" in query_lower
        or "emp id" in query_lower
    ):
        return {
            "success": True,
            "message": (
                "An Employee ID is a unique identifier assigned to "
                "an employee by an organization. It is commonly used "
                "to identify employee records in HR systems."
            ),
            "data": {
                "topic": "Employee ID",
            },
        }

    # ============================================================
    # JOINING DATE
    # ============================================================

    if (
        "joining date" in query_lower
        or "what is joining date" in query_lower
    ):
        return {
            "success": True,
            "message": (
                "Joining date is the date on which an employee "
                "officially starts working for an organization."
            ),
            "data": {
                "topic": "Joining Date",
            },
        }

    # ============================================================
    # EXPERIENCE
    # ============================================================

    if (
        "what is experience" in query_lower
        or query_lower == "experience"
        or "employee experience" in query_lower
    ):
        return {
            "success": True,
            "message": (
                "Employee experience refers to the amount of work "
                "experience an employee has. It can include previous "
                "experience, experience in the current company, and total experience."
            ),
            "data": {
                "topic": "Experience",
            },
        }

    # ============================================================
    # DEPARTMENT
    # ============================================================

    if (
        "what is department" in query_lower
        or query_lower == "department"
    ):
        return {
            "success": True,
            "message": (
                "A department is an organizational unit responsible "
                "for a particular business function, such as HR, "
                "Finance, Sales, IT, or Support."
            ),
            "data": {
                "topic": "Department",
            },
        }

    # ============================================================
    # DESIGNATION
    # ============================================================

    if (
        "what is designation" in query_lower
        or query_lower == "designation"
        or "job designation" in query_lower
    ):
        return {
            "success": True,
            "message": (
                "Designation is the official job title or position "
                "assigned to an employee, such as Software Developer, "
                "Business Analyst, HR Manager, or Accountant."
            ),
            "data": {
                "topic": "Designation",
            },
        }

    # ============================================================
    # FULL-TIME / PART-TIME
    # ============================================================

    if (
        "full time" in query_lower
        or "full-time" in query_lower
        or "part time" in query_lower
        or "part-time" in query_lower
        or "employment type" in query_lower
    ):
        return {
            "success": True,
            "message": (
                "Employment type describes the nature of an employee's "
                "work arrangement, such as Full-Time, Part-Time, "
                "Contract, or Temporary employment."
            ),
            "data": {
                "topic": "Employment Type",
            },
        }

    # ============================================================
    # DEFAULT
    # ============================================================

    return {
        "success": False,
        "message": (
            "I can explain general HR concepts such as PF, salary, "
            "attendance, leave, experience, employee ID, joining date, "
            "department, and designation."
        ),
        "data": {},
    }