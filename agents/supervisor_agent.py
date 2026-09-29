from typing import Dict


# ============================================================
# SUPERVISOR / ROUTER AGENT
# ============================================================

def route_hr_query(
    query: str,
    previous_employee_name: str = "",
    previous_employee_id: str = "",
    previous_intent: str = "",
) -> Dict:
    """
    Decide which HR agent should handle the user's question.

    This is the first routing layer of the multi-agent system.
    """

    text = str(query or "").strip().lower()

    if not text:
        return {
            "intent": "out_of_scope",
            "agent": "general_hr_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    # ========================================================
    # EMPLOYEE-SPECIFIC TOPICS
    # ========================================================

    # Salary
    salary_words = [
        "salary",
        "pay",
        "monthly salary",
        "income",
        "wage",
    ]

    if any(word in text for word in salary_words):
        return {
            "intent": "salary",
            "agent": "salary_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    # PF
    pf_words = [
        "pf",
        "provident fund",
        "epf",
        "employee pf",
        "employer pf",
    ]

    if any(word in text for word in pf_words):
        return {
            "intent": "pf",
            "agent": "pf_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    # Experience
    experience_words = [
        "experience",
        "years of experience",
        "previous experience",
        "company experience",
        "total experience",
    ]

    if any(word in text for word in experience_words):
        return {
            "intent": "experience",
            "agent": "experience_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    # Attendance
    attendance_words = [
        "attendance",
        "present",
        "absent",
        "working days",
        "attendance summary",
    ]

    if any(word in text for word in attendance_words):
        return {
            "intent": "attendance",
            "agent": "attendance_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    # Leave
    leave_words = [
        "leave",
        "leaves",
        "leave balance",
        "leave history",
        "paid leave",
        "unpaid leave",
    ]

    if any(word in text for word in leave_words):
        return {
            "intent": "leave",
            "agent": "leave_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    # Outstanding
    outstanding_words = [
        "outstanding",
        "outstanding amount",
        "pending amount",
        "pending payment",
        "due amount",
        "amount due",
    ]

    if any(word in text for word in outstanding_words):
        return {
            "intent": "outstanding",
            "agent": "outstanding_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    # ========================================================
    # EMPLOYEE INFORMATION
    # ========================================================

    employee_words = [
        "employee details",
        "employee detail",
        "employee information",
        "employee info",
        "employee id",
        "employee name",
        "department",
        "designation",
        "joining date",
        "employment status",
        "complete details",
        "complete information",
        "show details",
        "show complete details",
    ]

    if any(word in text for word in employee_words):
        return {
            "intent": "employee_details",
            "agent": "employee_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    # ========================================================
    # EMPLOYEE COUNT / LIST
    # ========================================================

    count_words = [
        "employee count",
        "number of employees",
        "how many employees",
        "total employees",
        "employee total",
    ]

    if any(word in text for word in count_words):
        return {
            "intent": "employee_count",
            "agent": "employee_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    list_words = [
        "all employees",
        "list employees",
        "employee list",
        "show employees",
        "names of employees",
    ]

    if any(word in text for word in list_words):
        return {
            "intent": "employee_list",
            "agent": "employee_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    # ========================================================
    # GENERAL HR
    # ========================================================

    general_hr_words = [
        "what is pf",
        "what is provident fund",
        "what is salary",
        "what is gross salary",
        "what is net salary",
        "what is outstanding",
        "what is employee experience",
        "what is joining date",
        "what is attendance",
        "what is leave",
        "what is gratuity",
        "what is payroll",
        "what is hr",
        "what is employee",
    ]

    if any(word in text for word in general_hr_words):
        return {
            "intent": "general_hr",
            "agent": "general_hr_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    # ========================================================
    # RESEARCH
    # ========================================================

    research_words = [
        "latest hr",
        "current hr",
        "latest rule",
        "current rule",
        "latest labour law",
        "current labour law",
        "latest labor law",
        "current labor law",
        "research",
        "according to current law",
        "india hr rules",
        "government rule",
    ]

    if any(word in text for word in research_words):
        return {
            "intent": "research",
            "agent": "research_agent",
            "employee_name": previous_employee_name,
            "employee_id": previous_employee_id,
        }

    # ========================================================
    # FOLLOW-UP QUESTIONS
    # ========================================================

    follow_up_words = [
        "what about",
        "how about",
        "and pf",
        "and salary",
        "and experience",
        "and attendance",
        "and leave",
        "and outstanding",
        "tell me more",
        "more details",
    ]

    if any(word in text for word in follow_up_words):

        # If previous topic exists, keep employee context
        if previous_intent:
            return {
                "intent": previous_intent,
                "agent": f"{previous_intent}_agent",
                "employee_name": previous_employee_name,
                "employee_id": previous_employee_id,
            }

    # ========================================================
    # OUT OF SCOPE
    # ========================================================

    return {
        "intent": "out_of_scope",
        "agent": "out_of_scope",
        "employee_name": previous_employee_name,
        "employee_id": previous_employee_id,
    }