
import os
import re

from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from tools.employee_db_tools import get_all_employees
from database.upload_db import get_uploaded_employees

from agents.hr_tools import (
    employee_by_id,
    employee_by_name,
    uploaded_employee_by_id,
    uploaded_employee_by_name,
    all_uploaded_employees,

    employee_salary,
    employee_experience,

    attendance_summary,
    employee_attendance,
    attendance_by_date,

    employee_leaves,
    employee_leave_summary,
    unpaid_leave_records,

    employee_salary_summary,
    salary_deduction_reason,

    highest_salary_employee,
    salary_ranking,

    leave_ranking,
    employees_by_leave_days,

    employee_pf_summary,
    total_pf,

    employee_monthly_summary,

    low_attendance_employees,
    most_experienced_employees,
)


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()

if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError(
        "GOOGLE_API_KEY is not set in .env file"
    )


# ============================================================
# LLM
# ============================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    temperature=0
)

# ============================================================
# MONTH / YEAR EXTRACTION
# ============================================================

def extract_month_year(user_query):

    query = user_query.lower()

    month_map = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }

    month = None
    year = None

    for month_name, month_number in month_map.items():

        if month_name in query:
            month = month_number
            break

    year_match = re.search(
        r"\b(20\d{2})\b",
        query
    )

    if year_match:
        year = int(
            year_match.group(1)
        )

    return month, year


# ============================================================
# MONTH NUMBER TO MONTH NAME
# ============================================================

def month_number_to_name(month):

    month_map = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    }

    return month_map.get(month)


# ============================================================
# EMPLOYEE DETECTION NODE
# ============================================================

def employee_detection_node(state):

    query = state.get(
        "user_query",
        ""
    ).strip()

    if not query:

        state["error"] = (
            "User query is empty."
        )

        return state

    query_lower = query.lower()

    # ========================================================
    # PREVIOUS EMPLOYEE MEMORY
    # ========================================================

    previous_employee_name = state.get(
        "previous_employee_name"
    )

    previous_employee_id = state.get(
        "previous_employee_id"
    )

    # Restore previous employee into current state
    if previous_employee_name:

        state["employee_name"] = (
            previous_employee_name
        )

    if previous_employee_id:

        state["employee_id"] = (
            previous_employee_id
        )

    # ========================================================
    # DEFAULT
    # ========================================================

    state["uploaded_employee"] = False

    # ========================================================
    # MONTH / YEAR
    # ========================================================

    month, year = extract_month_year(
        query
    )

    if month is not None:

        state["month"] = month

    if year is not None:

        state["year"] = year

    # ========================================================
    # 1. EMPLOYEE ID DETECTION
    # ========================================================

    employee_id_match = re.search(
        r"\b[A-Z]{2,}\d+\b",
        query,
        re.IGNORECASE
    )

    if employee_id_match:

        employee_id = (
            employee_id_match
            .group(0)
            .upper()
        )

        # ----------------------------------------------------
        # UPLOADED EMPLOYEE
        # ----------------------------------------------------

        try:

            uploaded_result = (
                uploaded_employee_by_id.invoke(
                    {
                        "employee_id":
                            employee_id
                    }
                )
            )

            if (
                isinstance(
                    uploaded_result,
                    dict
                )
                and uploaded_result.get(
                    "success"
                )
            ):

                employees = (
                    uploaded_result.get(
                        "employees",
                        []
                    )
                )

                if employees:

                    employee = employees[0]

                    state["employee_id"] = (
                        employee.get(
                            "employee_id"
                        )
                    )

                    state["employee_name"] = (
                        employee.get(
                            "employee_name"
                        )
                    )

                    state["employee_data"] = (
                        employee
                    )

                    state["uploaded_employee"] = True

                    # Save memory
                    state[
                        "previous_employee_id"
                    ] = employee.get(
                        "employee_id"
                    )

                    state[
                        "previous_employee_name"
                    ] = employee.get(
                        "employee_name"
                    )

                    return state

        except Exception as error:

            print(
                f"Uploaded ID search error: {error}"
            )

        # ----------------------------------------------------
        # ORIGINAL DATABASE
        # ----------------------------------------------------

        result = employee_by_id.invoke(
            {
                "employee_id":
                    employee_id
            }
        )

        if (
            isinstance(result, dict)
            and result.get("success")
        ):

            state["employee_id"] = (
                result.get(
                    "employee_id"
                )
            )

            state["employee_name"] = (
                result.get(
                    "employee_name"
                )
            )

            state["employee_data"] = result

            state["uploaded_employee"] = False

            # Save memory
            state[
                "previous_employee_id"
            ] = result.get(
                "employee_id"
            )

            state[
                "previous_employee_name"
            ] = result.get(
                "employee_name"
            )

            return state

        # Remember ID even if not found
        state["employee_id"] = (
            employee_id
        )

        state["employee_data"] = result

        state[
            "previous_employee_id"
        ] = employee_id

        return state

    # ========================================================
    # 2. EMPLOYEE NAME DETECTION
    # ========================================================

    # --------------------------------------------------------
    # UPLOADED EMPLOYEE DATABASE
    # --------------------------------------------------------

    try:

        uploaded_employees = (
            get_uploaded_employees(
                limit=10000
            )
        )

        for employee in uploaded_employees:

            employee_name = str(
                employee.get(
                    "employee_name",
                    ""
                )
            ).strip()

            if not employee_name:

                continue

            employee_name_lower = (
                employee_name.lower()
            )

            if employee_name_lower in query_lower:

                state["employee_id"] = (
                    employee.get(
                        "employee_id"
                    )
                )

                state["employee_name"] = (
                    employee.get(
                        "employee_name"
                    )
                )

                state["employee_data"] = (
                    employee
                )

                state["uploaded_employee"] = True

                # Save memory
                state[
                    "previous_employee_id"
                ] = employee.get(
                    "employee_id"
                )

                state[
                    "previous_employee_name"
                ] = employee.get(
                    "employee_name"
                )

                return state

        # ----------------------------------------------------
        # PARTIAL NAME SEARCH
        # ----------------------------------------------------

        uploaded_result = (
            uploaded_employee_by_name.invoke(
                {
                    "employee_name":
                        query
                }
            )
        )

        if (
            isinstance(
                uploaded_result,
                dict
            )
            and uploaded_result.get(
                "success"
            )
        ):

            employees = (
                uploaded_result.get(
                    "employees",
                    []
                )
            )

            if employees:

                employee = employees[0]

                state["employee_id"] = (
                    employee.get(
                        "employee_id"
                    )
                )

                state["employee_name"] = (
                    employee.get(
                        "employee_name"
                    )
                )

                state["employee_data"] = (
                    employee
                )

                state["uploaded_employee"] = True

                # Save memory
                state[
                    "previous_employee_id"
                ] = employee.get(
                    "employee_id"
                )

                state[
                    "previous_employee_name"
                ] = employee.get(
                    "employee_name"
                )

                return state

    except Exception as error:

        print(
            "Uploaded employee name "
            f"search error: {error}"
        )

    # ========================================================
    # 3. ORIGINAL DATABASE NAME SEARCH
    # ========================================================

    try:

        all_employees = (
            get_all_employees()
        )

        if isinstance(
            all_employees,
            dict
        ):

            employee_list = (
                all_employees.get(
                    "employees",
                    []
                )
            )

        elif isinstance(
            all_employees,
            list
        ):

            employee_list = (
                all_employees
            )

        else:

            employee_list = []

        for employee in employee_list:

            name = str(
                employee.get(
                    "employee_name",
                    ""
                )
            ).strip()

            if not name:

                continue

            if name.lower() in query_lower:

                state["employee_id"] = (
                    employee.get(
                        "employee_id"
                    )
                )

                state["employee_name"] = (
                    name
                )

                state["employee_data"] = (
                    employee
                )

                state["uploaded_employee"] = (
                    False
                )

                # Save memory
                state[
                    "previous_employee_id"
                ] = employee.get(
                    "employee_id"
                )

                state[
                    "previous_employee_name"
                ] = name

                return state

    except Exception as error:

        state["error"] = (
            "Employee detection error: "
            f"{error}"
        )

    # ========================================================
    # 4. FOLLOW-UP QUERY
    # ========================================================

    follow_up_patterns = [
        "yes",
        "his",
        "her",
        "their",
        "him",
        "them",
        "employee id",
        "emp id",
        "id",
        "experience",
        "salary",
        "pf",
        "provident fund",
        "attendance",
        "leave",
        "leaves",
    ]

    is_follow_up = any(
        pattern in query_lower
        for pattern in follow_up_patterns
    )

    if (
        is_follow_up
        and previous_employee_name
    ):

        state["employee_name"] = (
            previous_employee_name
        )

        state["employee_id"] = (
            previous_employee_id
        )

        # ----------------------------------------------------
        # Restore uploaded employee
        # ----------------------------------------------------

        if previous_employee_id:

            try:

                uploaded_result = (
                    uploaded_employee_by_id.invoke(
                        {
                            "employee_id":
                                previous_employee_id
                        }
                    )
                )

                if (
                    isinstance(
                        uploaded_result,
                        dict
                    )
                    and uploaded_result.get(
                        "success"
                    )
                ):

                    employees = (
                        uploaded_result.get(
                            "employees",
                            []
                        )
                    )

                    if employees:

                        employee = employees[0]

                        state[
                            "employee_id"
                        ] = employee.get(
                            "employee_id"
                        )

                        state[
                            "employee_name"
                        ] = employee.get(
                            "employee_name"
                        )

                        state[
                            "employee_data"
                        ] = employee

                        state[
                            "uploaded_employee"
                        ] = True

                        state[
                            "previous_employee_id"
                        ] = employee.get(
                            "employee_id"
                        )

                        state[
                            "previous_employee_name"
                        ] = employee.get(
                            "employee_name"
                        )

            except Exception as error:

                print(
                    "Follow-up employee "
                    f"restore error: {error}"
                )

        return state

    # ========================================================
    # 5. NOTHING FOUND
    # ========================================================

    return state


# ============================================================
# LLM ROUTER NODE
# ============================================================

def llm_router_node(state):

    query = state.get(
        "user_query",
        ""
    )

    query_lower = (
        query.lower()
        .strip()
    )
        # ========================================================
    # DYNAMIC DATA / REPORT QUERIES
    # ========================================================

    dynamic_report_patterns = [
        "report",
        "reports",
        "dataset",
        "datasets",
        "data summary",
        "summary by",
        "breakdown",
        "distribution",
        "group by",
        "grouped by",
        "per customer",
        "per employee",
        "per department",
        "per product",
        "per category",
        "sales report",
        "sales summary",
        "sales by",
        "purchase report",
        "purchase summary",
        "purchase by",
        "expense report",
        "expense summary",
        "expense by",
        "stock report",
        "stock summary",
        "stock by",
        "attendance status summary",
        "attendance summary by",
        "attendance status count",
        "attendance breakdown",
        "attendance distribution",
        "total sales",
         # Ranking / top-value report queries
        "highest sales",
        "highest sale",
        "maximum sales",
        "maximum sale",
        "most sales",
        "top customer",
        "top customers",
        "best customer",
        "best customers",
        "customer with highest sales",
        "customer with maximum sales",
        "customer with most sales",
        "which customer has highest sales",
        "which customer has maximum sales",
        "which customer has most sales",

        "total purchase",
        "total expenses",
        "total expense",
        "total stock",
        "show sales",
        "show purchases",
        "show expenses",
        "show stock",
    ]

    employee_specific_query = bool(
        re.search(
            r"\b(?:emp\d+|employee\s+id|employee\s+name)\b",
            query_lower,
            re.IGNORECASE,
        )
    )

    # Generic dynamic sales queries.
    # Handles queries such as:
    #   Show Laptop sales for September 2026
    #   Show Monitor sales
    #   Show ABC Traders sales for September
    #   Show sales for Laptop
    
    dynamic_sales_query = bool(
        re.search(
            r"\b(?:show|give|display|get|find)\b",
            query_lower,
            re.IGNORECASE,
        )
    )
    # Generic invoice-detail queries.
    # Handles:
    #   Show details of invoice INV103
    #   Show invoice INV103
    #   Details for invoice INV101
    #   Find invoice INV104
    #   Show INV103 details
    dynamic_invoice_query = bool(
        re.search(
            r"\binvoice\b",
            query_lower,
            re.IGNORECASE,
        )
        and re.search(
            r"\b(?:inv[-\s]?\d+)\b",
            query_lower,
            re.IGNORECASE,
        )
    )
    
        # ========================================================
    # BUSINESS DATA COUNT QUERIES
    # ========================================================
    #
    # Handles:
    #   How many invoices?
    #   Count invoices
    #   Number of invoices
    #   Total invoices
    #   How many customers?
    #   Count customers
    #   Number of products
    #
    # Employee count is intentionally excluded because
    # employee-count queries are handled separately below.
    # ========================================================

    dynamic_count_query = bool(
        re.search(
            r"\b(?:how\s+many|count|number\s+of|total)\b",
            query_lower,
            re.IGNORECASE,
        )
        and re.search(
            r"\b(?:invoices?|customers?|products?|"
            r"transactions?|records?|entries?|"
            r"salespersons?|purchases?|expenses?|"
            r"payments?|suppliers?|stock|inventory)\b",
            query_lower,
            re.IGNORECASE,
        )
    )

    if (
        (
            any(
                pattern in query_lower
                for pattern in dynamic_report_patterns
            )
            or dynamic_sales_query
            or dynamic_invoice_query
            or dynamic_count_query
        )
        and not employee_specific_query
    ):
        state["intent"] = "dynamic_data"
        return state
    

    allowed_intents = {
    "salary",
    "pf",
    "attendance",
    "leave",
    "experience",
    "employee_id",
    "summary",
    "ranking",
    "all_employees",
    "general",
    "complete_details",
    "dynamic_data",
   }

    # ========================================================
    # ALL EMPLOYEES
    # ========================================================

    all_employee_patterns = [
        "all employees",
        "all employee",
        "employee names",
        "names of all employees",
        "name of all employees",
        "list all employees",
        "show all employees",
        "show all employee",
        "list employees",
        "show employee list",
        "employee list",
        "all uploaded employees",
        "uploaded employees",
        "list uploaded employees",
        "show uploaded employees",
        "how many employees",
        "how many employee",
        "number of employees",
        "number of employee",
        "total employees",
        "total employee",
        "employee count",
        "total number of employees",
        "total number of employee",
    ]

    if any(
        pattern in query_lower
        for pattern in all_employee_patterns
    ):

        state["intent"] = (
            "all_employees"
        )

        return state

    # ========================================================
    # EMPLOYEE ID
    # ========================================================

    employee_id_patterns = [
        "employee id",
        "employee-id",
        "emp id",
        "empid",
        "employee identification",
        "what is his id",
        "what is her id",
        "give me his id",
        "give me her id",
        "give his id",
        "give her id",
        "show his id",
        "show her id",
    ]

    if any(
        pattern in query_lower
        for pattern in employee_id_patterns
    ):

        state["intent"] = (
            "employee_id"
        )

        return state

    # ========================================================
    # EXPERIENCE
    # ========================================================

    if (
        state.get(
            "previous_employee_name"
        )
        and any(
            word in query_lower
            for word in [
                "experience",
                "work experience",
                "years of experience",
            ]
        )
    ):

        state["intent"] = (
            "experience"
        )

        return state

    # ========================================================
    # SALARY
    # ========================================================

    if (
        state.get(
            "previous_employee_name"
        )
        and any(
            word in query_lower
            for word in [
                "salary",
                "pay",
                "monthly salary",
            ]
        )
    ):

        state["intent"] = (
            "salary"
        )

        return state

    # ========================================================
    # PF
    # ========================================================

    if (
        state.get(
            "previous_employee_name"
        )
        and any(
            word in query_lower
            for word in [
                "pf",
                "provident fund",
            ]
        )
    ):

        state["intent"] = (
            "pf"
        )

        return state

    # ========================================================
    # ATTENDANCE
    # ========================================================

    if (
        state.get(
            "previous_employee_name"
        )
        and "attendance" in query_lower
    ):

        state["intent"] = (
            "attendance"
        )

        return state

    # ========================================================
    # LEAVE
    # ========================================================

    if (
        state.get(
            "previous_employee_name"
        )
        and any(
            word in query_lower
            for word in [
                "leave",
                "leaves",
            ]
        )
    ):

        state["intent"] = (
            "leave"
        )

        return state

    # ========================================================
    # EXACT LEAVE-DAYS QUERY
    # ========================================================

    exact_leave_query = (
        any(
            word in query_lower
            for word in [
                "leave",
                "leaves",
            ]
        )
        and any(
            word in query_lower
            for word in [
                "whose",
                "with",
                "is",
                "are",
                "equals",
                "equal",
            ]
        )
        and bool(
            re.search(
                r"\b\d+\b",
                query_lower
            )
        )
    )

    if exact_leave_query:

        state["intent"] = (
            "ranking"
        )

        return state

    # ========================================================
    # LLM ROUTER
    # ========================================================

    router_prompt = f"""
You are an HR query router.

Classify the user's query into exactly ONE intent.

Allowed intents:

salary
pf
attendance
leave
experience
employee_id
summary
ranking
all_employees
general

Rules:

salary:
The user asks about an employee's salary.

pf:
The user asks about PF or provident fund.

attendance:
The user asks about attendance.

leave:
The user asks about employee leave.

experience:
The user asks about work experience.

employee_id:
The user asks for an employee ID.

summary:
The user asks for complete or monthly employee information.

ranking:
The user asks to rank, compare, find highest/lowest,
top/bottom employees, or employees matching a number.

all_employees:
The user asks for all employee names, all employees,
uploaded employees, or employee count.

general:
Any other HR question.

User query:
{query}

Return ONLY one word.
"""

    response = llm.invoke(
        router_prompt
    )

    intent = (
        response.content
        .strip()
        .lower()
    )

    intent = (
        intent
        .replace("`", "")
        .strip()
    )

    if intent not in allowed_intents:

        intent = "general"

    state["intent"] = intent

    return state


# ============================================================
# EMPLOYEE NODE
# ============================================================

def employee_node(state):

    employee_id = state.get(
        "employee_id"
    )

    employee_name = state.get(
        "employee_name"
    )

    intent = state.get(
        "intent",
        "general"
    )

    # ========================================================
    # 1. EMPLOYEE ID QUERY
    # ========================================================

    if intent == "employee_id":

        if employee_id:

            state["employee_data"] = {
                "employee_id":
                    employee_id,

                "employee_name":
                    employee_name,
            }

        else:

            state["employee_data"] = (
                "Employee information "
                "not found."
            )

        return state

    # ========================================================
    # 2. NAME MISSING BUT ID EXISTS
    # ========================================================

    if (
        employee_id
        and not employee_name
    ):

        try:

            uploaded_result = (
                uploaded_employee_by_id.invoke(
                    {
                        "employee_id":
                            employee_id
                    }
                )
            )

            if (
                isinstance(
                    uploaded_result,
                    dict
                )
                and uploaded_result.get(
                    "success"
                )
            ):

                employees = (
                    uploaded_result.get(
                        "employees",
                        []
                    )
                )

                if employees:

                    employee = employees[0]

                    employee_id = (
                        employee.get(
                            "employee_id"
                        )
                    )

                    employee_name = (
                        employee.get(
                            "employee_name"
                        )
                    )

                    state["employee_id"] = (
                        employee_id
                    )

                    state["employee_name"] = (
                        employee_name
                    )

                    state["employee_data"] = (
                        employee
                    )

                    state[
                        "uploaded_employee"
                    ] = True

                    # Save memory
                    state[
                        "previous_employee_id"
                    ] = employee_id

                    state[
                        "previous_employee_name"
                    ] = employee_name

        except Exception as error:

            print(
                "Uploaded employee ID "
                f"lookup error: {error}"
            )

    # ========================================================
    # 3. UPLOADED EMPLOYEE
    # ========================================================

    if state.get(
        "uploaded_employee"
    ):

        uploaded_data = state.get(
            "employee_data"
        )

        if not isinstance(
            uploaded_data,
            dict
        ):

            uploaded_data = {}

        # ----------------------------------------------------
        # EXPERIENCE
        # ----------------------------------------------------

        if intent == "experience":

            state["experience_data"] = {

                "employee_name":
                    uploaded_data.get(
                        "employee_name"
                    ),

                "employee_id":
                    uploaded_data.get(
                        "employee_id"
                    ),

                "previous_experience_years":
                    uploaded_data.get(
                        "previous_experience_years"
                    ),

                "current_company_experience":
                    uploaded_data.get(
                        "current_company_experience"
                    ),

                "total_experience":
                    uploaded_data.get(
                        "total_experience"
                    ),
            }

        state["employee_data"] = (
            uploaded_data
        )

        return state

    # ========================================================
    # 4. ORIGINAL DATABASE BY ID
    # ========================================================

    if employee_id:

        result = employee_by_id.invoke(
            {
                "employee_id":
                    employee_id
            }
        )

        state["employee_data"] = (
            result
        )

        if isinstance(
            result,
            dict
        ):

            employee_name = (
                result.get(
                    "employee_name"
                )
            )

            state["employee_name"] = (
                employee_name
            )

            # Save memory
            state[
                "previous_employee_id"
            ] = result.get(
                "employee_id"
            )

            state[
                "previous_employee_name"
            ] = employee_name

        if intent == "experience":

            if employee_name:

                experience_result = (
                    employee_experience.invoke(
                        {
                            "employee_name":
                                employee_name
                        }
                    )
                )

                state[
                    "experience_data"
                ] = experience_result

            else:

                state[
                    "experience_data"
                ] = {
                    "success": False,
                    "message":
                        "Employee name not found.",
                }

        return state

    # ========================================================
    # 5. ORIGINAL DATABASE BY NAME
    # ========================================================

    if employee_name:

        result = employee_by_name.invoke(
            {
                "employee_name":
                    employee_name
            }
        )

        state["employee_data"] = (
            result
        )

        if isinstance(
            result,
            dict
        ):

            state["employee_id"] = (
                result.get(
                    "employee_id"
                )
            )

            state[
                "previous_employee_id"
            ] = result.get(
                "employee_id"
            )

            state[
                "previous_employee_name"
            ] = (
                result.get(
                    "employee_name"
                )
                or employee_name
            )

        if intent == "experience":

            experience_result = (
                employee_experience.invoke(
                    {
                        "employee_name":
                            employee_name
                    }
                )
            )

            state[
                "experience_data"
            ] = experience_result

        return state

    # ========================================================
    # 6. NOT FOUND
    # ========================================================

    state["employee_data"] = (
        "Employee information "
        "not found."
    )

    return state


# ============================================================
# ATTENDANCE NODE
# ============================================================

def attendance_node(state):

    employee_id = state.get("employee_id")

    if not employee_id:
        state["attendance_data"] = {
            "success": False,
            "message": "Employee ID not found.",
        }
        return state

    state["attendance_data"] = attendance_summary.invoke(
        {
            "employee_name": employee_id,
            "month": state.get("month"),
            "year": state.get("year"),
        }
    )

    return state


# ============================================================
# LEAVE NODE
# ============================================================

def leave_node(state):

    # Uploaded employee does not have
    # leave data
    if state.get(
        "uploaded_employee"
    ):

        state["leave_data"] = {
            "success": False,
            "message":
                "Leave information "
                "is not available.",
        }

        return state

    employee_name = state.get(
        "employee_name"
    )

    if not employee_name:

        state["leave_data"] = {
            "success": False,
            "message":
                "Employee name not found.",
        }

        return state

    state["leave_data"] = (
        employee_leave_summary.invoke(
            {
                "employee_name":
                    employee_name
            }
        )
    )

    return state


# ============================================================
# SALARY NODE
# ============================================================

# ============================================================
# SALARY NODE
# ============================================================

def salary_node(state):

    employee_name = state.get(
        "employee_name"
    )

    month = state.get(
        "month"
    )

    year = state.get(
        "year"
    )

    month_name = (
        month_number_to_name(
            month
        )
    )

    if not employee_name:

        state["salary_data"] = {
            "success": False,
            "message": "Employee name not found.",
        }

        return state

    # ========================================================
    # UPLOADED EMPLOYEE
    # ========================================================

    if state.get(
        "uploaded_employee"
    ):

        employee_data = state.get(
            "employee_data",
            {}
        )

        if isinstance(
            employee_data,
            dict
        ):

            state["salary_data"] = {

                "success": True,

                "employee_id":
                    employee_data.get(
                        "employee_id"
                    ),

                "employee_name":
                    employee_data.get(
                        "employee_name"
                    ),

                "monthly_salary":
                    employee_data.get(
                        "monthly_salary"
                    ),
            }

            return state

    # ========================================================
    # ORIGINAL EMPLOYEE DATABASE
    # ========================================================

    employee_data = state.get(
        "employee_data"
    )

    # --------------------------------------------------------
    # SIMPLE SALARY QUERY
    # --------------------------------------------------------

    if isinstance(
        employee_data,
        dict
    ):

        monthly_salary = (
            employee_data.get(
                "monthly_salary"
            )
        )

        if monthly_salary is not None:

            state["salary_data"] = {

                "success": True,

                "employee_id":
                    employee_data.get(
                        "employee_id"
                    ),

                "employee_name":
                    employee_data.get(
                        "employee_name"
                    ),

                "monthly_salary":
                    monthly_salary,
            }

            return state

    # ========================================================
    # MONTH-SPECIFIC SALARY
    # ========================================================
    #
    # If the user asks something like:
    #
    # "What is EMP001 salary for August 2026?"
    #
    # use the existing salary summary tool because
    # attendance/leave deductions may be required.
    # ========================================================

    result = (
        employee_salary_summary.invoke(
            {
                "employee_name":
                    employee_name,

                "month":
                    month_name,

                "year":
                    year,
            }
        )
    )

    state["salary_data"] = result

    return state


# ============================================================
# RANKING NODE
# ============================================================

def ranking_node(state):

    query = state.get(
        "user_query",
        ""
    ).lower()

    # ========================================================
    # RANKING TYPE
    # ========================================================

    if any(
        word in query
        for word in [
            "leave",
            "leaves",
            "leave days",
        ]
    ):

        ranking_type = "leave"

    else:

        ranking_type = "salary"

    # ========================================================
    # EXACT LEAVE DAYS
    # ========================================================

    if ranking_type == "leave":

        exact_match = re.search(
            r"(?:leave|leaves|leave days|total leave)"
            r"\D+(\d+)",
            query
        )

        if exact_match:

            exact_leave_days = int(
                exact_match.group(1)
            )

            try:

                result = (
                    employees_by_leave_days.invoke(
                        {
                            "leave_days":
                                exact_leave_days
                        }
                    )
                )

                state["ranking_data"] = (
                    result
                )

                state[
                    "ranking_type"
                ] = "exact_leave"

                state[
                    "ranking_limit"
                ] = 0

                state[
                    "ranking_order"
                ] = "EXACT"

            except Exception as error:

                state["ranking_data"] = (
                    "Error while finding "
                    f"employees with "
                    f"{exact_leave_days} "
                    f"leave days: {error}"
                )

            return state

    # ========================================================
    # HIGHEST / LOWEST
    # ========================================================

    if any(
        word in query
        for word in [
            "lowest",
            "low",
            "bottom",
            "least",
            "minimum",
        ]
    ):

        ranking_order = "ASC"

    else:

        ranking_order = "DESC"

    # ========================================================
    # REQUESTED NUMBER
    # ========================================================

    match = re.search(
        r"\b(?:top|bottom|first|last)\s+(\d+)\b",
        query,
        re.IGNORECASE
    )

    if match:

        ranking_limit = int(
            match.group(1)
        )

    else:

        match = re.search(
            r"\b(\d+)\s+"
            r"(?:highest|lowest|high|low|top|bottom)\b",
            query,
            re.IGNORECASE
        )

        if match:

            ranking_limit = int(
                match.group(1)
            )

        else:

            match = re.search(
                r"\b(\d+)\s+"
                r"(?:employees?|employee names?)\b",
                query,
                re.IGNORECASE
            )

            if match:

                ranking_limit = int(
                    match.group(1)
                )

            else:

                ranking_limit = 1

    # ========================================================
    # SAVE RANKING INFORMATION
    # ========================================================

    state[
        "ranking_type"
    ] = ranking_type

    state[
        "ranking_order"
    ] = ranking_order

    state[
        "ranking_limit"
    ] = ranking_limit

    # ========================================================
    # GET RANKING DATA
    # ========================================================

    try:

        if ranking_type == "leave":

            result = (
                leave_ranking.invoke(
                    {
                        "limit":
                            ranking_limit,

                        "order":
                            ranking_order,
                    }
                )
            )

        else:

            result = (
                salary_ranking.invoke(
                    {
                        "limit":
                            ranking_limit,

                        "order":
                            ranking_order,
                    }
                )
            )

        state["ranking_data"] = (
            result
        )

    except Exception as error:

        state["ranking_data"] = (
            "Error while getting "
            f"{ranking_type} ranking: "
            f"{error}"
        )

    return state


# ============================================================
# PF NODE
# ============================================================

def pf_node(state):

    employee_name = state.get(
        "employee_name"
    )

    employee_id = state.get(
        "employee_id"
    )

    employee = state.get(
        "employee_data"
    )

    # ========================================================
    # UPLOADED EMPLOYEE PF
    # ========================================================

    if employee_name:

        if isinstance(
            employee,
            dict
        ):

            pf_applicable = (
                employee.get(
                    "pf_applicable"
                )
            )

            pf_rate = (
                employee.get(
                    "pf_rate"
                )
            )

            employee_pf = (
                employee.get(
                    "employee_pf"
                )
            )

            employer_pf = (
                employee.get(
                    "employer_pf"
                )
            )

            if (
                pf_applicable is not None
                or pf_rate is not None
                or employee_pf is not None
                or employer_pf is not None
            ):

                state["pf_data"] = {

                    "success": True,

                    "employee_id":
                        employee_id
                        or employee.get(
                            "employee_id"
                        ),

                    "employee_name":
                        employee_name
                        or employee.get(
                            "employee_name"
                        ),

                    "pf_applicable":
                        pf_applicable,

                    "pf_rate":
                        pf_rate,

                    "employee_pf":
                        employee_pf,

                    "employer_pf":
                        employer_pf,
                }

                return state

    # ========================================================
    # NAME NOT FOUND
    # ========================================================

    if not employee_name:

        state["pf_data"] = {
            "success": False,
            "message":
                "Employee name not found.",
        }

        return state

    # ========================================================
    # ORIGINAL DATABASE PF
    # ========================================================

    state["pf_data"] = (
        employee_pf_summary.invoke(
            {
                "employee_name":
                    employee_name,

                "month":
                    state.get("month"),

                "year":
                    state.get("year"),
            }
        )
    )

    return state


# ============================================================
# SUMMARY NODE
# ============================================================

def summary_node(state):

    employee_name = state.get(
        "employee_name"
    )

    if not employee_name:

        state["summary_data"] = (
            "Employee name not found."
        )

        return state

    result = (
        employee_monthly_summary.invoke(
            {
                "employee_name":
                    employee_name
            }
        )
    )

    state["summary_data"] = result

    return state


# ============================================================
# COMPLETE EMPLOYEE DATA NODE
# ============================================================

def complete_employee_data_node(state):

    employee_name = state.get(
        "employee_name"
    )

    month = state.get(
        "month"
    )

    year = state.get(
        "year"
    )

    month_name = (
        month_number_to_name(
            month
        )
    )

    if not employee_name:

        state["error"] = (
            "Employee name not found."
        )

        return state

    # ========================================================
    # UPLOADED EMPLOYEE
    # ========================================================

    if state.get(
        "uploaded_employee"
    ):

        employee_data = state.get(
            "employee_data"
        )

        if employee_data:

            state["employee_data"] = (
                employee_data
            )

            # ------------------------------------------------
            # SALARY
            # ------------------------------------------------

            state["salary_data"] = {

                "employee_id":
                    employee_data.get(
                        "employee_id"
                    ),

                "employee_name":
                    employee_data.get(
                        "employee_name"
                    ),

                "monthly_salary":
                    employee_data.get(
                        "monthly_salary"
                    ),
            }

            # ------------------------------------------------
            # PF
            # ------------------------------------------------

            state["pf_data"] = {

                "employee_id":
                    employee_data.get(
                        "employee_id"
                    ),

                "employee_name":
                    employee_data.get(
                        "employee_name"
                    ),

                "pf_applicable":
                    employee_data.get(
                        "pf_applicable"
                    ),

                "pf_rate":
                    employee_data.get(
                        "pf_rate"
                    ),

                "employee_pf":
                    employee_data.get(
                        "employee_pf"
                    ),

                "employer_pf":
                    employee_data.get(
                        "employer_pf"
                    ),
            }

            # ------------------------------------------------
            # EXPERIENCE
            # ------------------------------------------------

            state["experience_data"] = {

                "employee_name":
                    employee_data.get(
                        "employee_name"
                    ),

                "employee_id":
                    employee_data.get(
                        "employee_id"
                    ),

                "previous_experience_years":
                    employee_data.get(
                        "previous_experience_years"
                    ),

                "current_company_experience":
                    employee_data.get(
                        "current_company_experience"
                    ),

                "total_experience":
                    employee_data.get(
                        "total_experience"
                    ),
            }

            # ------------------------------------------------
            # ATTENDANCE
            # ------------------------------------------------

            state["attendance_data"] = (
                attendance_summary.invoke(
                    {
                        "employee_name":
                            employee_name,

                        "month":
                            month,

                        "year":
                            year,
                    }
                )
            )

            # ------------------------------------------------
            # LEAVE
            # ------------------------------------------------

            state["leave_data"] = (
                employee_leave_summary.invoke(
                    {
                        "employee_name":
                            employee_name
                    }
                )
            )

            # ------------------------------------------------
            # SUMMARY
            # ------------------------------------------------

            state["summary_data"] = (
                "No monthly summary found "
                f"for {employee_name}"
            )

            return state

    # ========================================================
    # ORIGINAL DATABASE EMPLOYEE
    # ========================================================

    state["employee_data"] = (
        employee_by_name.invoke(
            {
                "employee_name":
                    employee_name
            }
        )
    )

    # --------------------------------------------------------
    # Salary
    # --------------------------------------------------------

    state["salary_data"] = (
        employee_salary_summary.invoke(
            {
                "employee_name":
                    employee_name,

                "month":
                    month_name,

                "year":
                    year,
            }
        )
    )

    # --------------------------------------------------------
    # Attendance
    # --------------------------------------------------------

    state["attendance_data"] = (
        attendance_summary.invoke(
            {
                "employee_name":
                    employee_name,

                "month":
                    month,

                "year":
                    year,
            }
        )
    )

    # --------------------------------------------------------
    # Leave
    # --------------------------------------------------------

    state["leave_data"] = (
        employee_leave_summary.invoke(
            {
                "employee_name":
                    employee_name
            }
        )
    )

    # --------------------------------------------------------
    # PF
    # --------------------------------------------------------

    state["pf_data"] = (
        employee_pf_summary.invoke(
            {
                "employee_name":
                    employee_name,

                "month":
                    month_name,

                "year":
                    year,
            }
        )
    )

    # --------------------------------------------------------
    # Experience
    # --------------------------------------------------------

    state["experience_data"] = (
        employee_experience.invoke(
            {
                "employee_name":
                    employee_name
            }
        )
    )

    # --------------------------------------------------------
    # Monthly Summary
    # --------------------------------------------------------

    state["summary_data"] = (
        employee_monthly_summary.invoke(
            {
                "employee_name":
                    employee_name
            }
        )
    )

    return state


# ============================================================
# PARALLEL START NODE
# ============================================================

def parallel_start_node(state):

    return state


# ============================================================
# PARALLEL SALARY NODE
# ============================================================

def parallel_salary_node(state):

    employee_name = state.get(
        "employee_name"
    )

    month = state.get(
        "month"
    )

    year = state.get(
        "year"
    )

    month_name = (
        month_number_to_name(
            month
        )
    )

    if not employee_name:

        return {
            "salary_data":
                "Employee name not found."
        }

    # ========================================================
    # UPLOADED EMPLOYEE
    # ========================================================

    if state.get(
        "uploaded_employee"
    ):

        employee = state.get(
            "employee_data"
        )

        if employee:

            return {
                "salary_data": {

                    "employee_id":
                        employee.get(
                            "employee_id"
                        ),

                    "employee_name":
                        employee.get(
                            "employee_name"
                        ),

                    "monthly_salary":
                        employee.get(
                            "monthly_salary"
                        ),
                }
            }

    # ========================================================
    # ORIGINAL DATABASE
    # ========================================================

    result = (
        employee_salary_summary.invoke(
            {
                "employee_name":
                    employee_name,

                "month":
                    month_name,

                "year":
                    year,
            }
        )
    )

    return {
        "salary_data":
            result
    }


# ============================================================
# PARALLEL ATTENDANCE NODE
# ============================================================

def parallel_attendance_node(state):

    employee_name = state.get(
        "employee_name"
    )

    month = state.get(
        "month"
    )

    year = state.get(
        "year"
    )

    if not employee_name:

        return {
            "attendance_data":
                "Employee name not found."
        }

    # Uploaded employees do not have
    # attendance information.
    if state.get(
        "uploaded_employee"
    ):

        return {
            "attendance_data": {
                "success": False,
                "message":
                    "Attendance information "
                    "is not available.",
            }
        }

    result = (
        attendance_summary.invoke(
            {
                "employee_name":
                    employee_name,

                "month":
                    month,

                "year":
                    year,
            }
        )
    )

    return {
        "attendance_data":
            result
    }


# ============================================================
# PARALLEL LEAVE NODE
# ============================================================

def parallel_leave_node(state):

    employee_name = state.get(
        "employee_name"
    )

    if not employee_name:

        return {
            "leave_data":
                "Employee name not found."
        }

    # Uploaded employees do not have
    # leave information.
    if state.get(
        "uploaded_employee"
    ):

        return {
            "leave_data": {
                "success": False,
                "message":
                    "Leave information "
                    "is not available.",
            }
        }

    result = (
        employee_leave_summary.invoke(
            {
                "employee_name":
                    employee_name
            }
        )
    )

    return {
        "leave_data":
            result
    }


# ============================================================
# PARALLEL PF NODE
# ============================================================

def parallel_pf_node(state):

    employee_name = state.get(
        "employee_name"
    )

    month = state.get(
        "month"
    )

    year = state.get(
        "year"
    )

    month_name = (
        month_number_to_name(
            month
        )
    )

    if not employee_name:

        return {
            "pf_data":
                "Employee name not found."
        }

    # ========================================================
    # UPLOADED EMPLOYEE
    # ========================================================

    if state.get(
        "uploaded_employee"
    ):

        employee = state.get(
            "employee_data"
        )

        if employee:

            return {
                "pf_data": {

                    "employee_id":
                        employee.get(
                            "employee_id"
                        ),

                    "employee_name":
                        employee.get(
                            "employee_name"
                        ),

                    "pf_applicable":
                        employee.get(
                            "pf_applicable"
                        ),

                    "pf_rate":
                        employee.get(
                            "pf_rate"
                        ),

                    "employee_pf":
                        employee.get(
                            "employee_pf"
                        ),

                    "employer_pf":
                        employee.get(
                            "employer_pf"
                        ),
                }
            }

    # ========================================================
    # ORIGINAL DATABASE
    # ========================================================

    result = (
        employee_pf_summary.invoke(
            {
                "employee_name":
                    employee_name,

                "month":
                    month_name,

                "year":
                    year,
            }
        )
    )

    return {
        "pf_data":
            result
    }


# ============================================================
# PARALLEL EXPERIENCE NODE
# ============================================================

def parallel_experience_node(state):

    employee_name = state.get(
        "employee_name"
    )

    if not employee_name:

        return {
            "experience_data":
                "Employee name not found."
        }

    # ========================================================
    # UPLOADED EMPLOYEE
    # ========================================================

    if state.get(
        "uploaded_employee"
    ):

        employee = state.get(
            "employee_data"
        )

        if employee:

            return {
                "experience_data": {

                    "employee_name":
                        employee.get(
                            "employee_name"
                        ),

                    "employee_id":
                        employee.get(
                            "employee_id"
                        ),

                    "previous_experience_years":
                        employee.get(
                            "previous_experience_years"
                        ),

                    "current_company_experience":
                        employee.get(
                            "current_company_experience"
                        ),

                    "total_experience":
                        employee.get(
                            "total_experience"
                        ),
                }
            }

    # ========================================================
    # ORIGINAL DATABASE
    # ========================================================

    result = (
        employee_experience.invoke(
            {
                "employee_name":
                    employee_name
            }
        )
    )

    return {
        "experience_data":
            result
    }


# ============================================================
# PARALLEL JOIN NODE
# ============================================================

def parallel_join_node(state):

    employee_name = state.get(
        "employee_name"
    )

    employee_id = state.get(
        "employee_id"
    )

    # ========================================================
    # MONTHLY SUMMARY
    # ========================================================

    if employee_name:

        try:

            summary_result = (
                employee_monthly_summary.invoke(
                    {
                        "employee_id":
                            employee_id,

                        "employee_name":
                            employee_name,
                    }
                )
            )

            state[
                "summary_data"
            ] = summary_result

        except Exception as error:

            state[
                "summary_data"
            ] = {

                "success": False,

                "message":
                    "Monthly summary "
                    "could not be loaded: "
                    f"{error}",
            }

    else:

        state[
            "summary_data"
        ] = {

            "success": False,

            "message":
                "Employee name not found.",
        }

    # ========================================================
    # MARK COMPLETE
    # ========================================================

    state[
        "parallel_completed"
    ] = [

        "salary",
        "attendance",
        "leave",
        "pf",
        "experience",
        "monthly_summary",
    ]

    return state


# ============================================================
# ANSWER GENERATION NODE
# ============================================================

# ============================================================
# ANSWER GENERATION NODE
# ============================================================

def answer_generation_node(state):

    query = state.get("user_query", "")
    employee_name = state.get("employee_name")
    employee_id = state.get("employee_id")

    salary_data = state.get("salary_data")
    pf_data = state.get("pf_data")
    experience_data = state.get("experience_data")
    attendance_data = state.get("attendance_data")
    leave_data = state.get("leave_data")

    intent = state.get("intent", "general")

    # ========================================================
    # SALARY
    # ========================================================

    if intent == "salary":

        salary = None

        if isinstance(salary_data, dict):
            salary = salary_data.get("monthly_salary")

            if salary is None:
                salary = salary_data.get("salary")

        if salary is not None:

            try:
                salary_value = float(salary)

                if salary_value.is_integer():
                    salary_text = f"{int(salary_value):,}"
                else:
                    salary_text = f"{salary_value:,.2f}"

                answer = f"His monthly salary is ₹{salary_text}."

            except (ValueError, TypeError):

                answer = f"His monthly salary is ₹{salary}."

        else:

            answer = "Salary information is not available."

        state["answer"] = answer
        state["final_answer"] = answer

        return state

    # ========================================================
    # PF
    # ========================================================

    if intent == "pf":

        employee_pf = None

        if isinstance(pf_data, dict):
            employee_pf = pf_data.get("employee_pf")

        if employee_pf is not None:

            try:
                pf_value = float(employee_pf)

                if pf_value.is_integer():
                    pf_text = f"{int(pf_value):,}"
                else:
                    pf_text = f"{pf_value:,.2f}"

                answer = (
                    f"His employee PF contribution is ₹{pf_text}."
                )

            except (ValueError, TypeError):

                answer = (
                    f"His employee PF contribution is ₹{employee_pf}."
                )

        else:

            answer = "PF information is not available."

        state["answer"] = answer
        state["final_answer"] = answer

        return state

    # ========================================================
    # EXPERIENCE
    # ========================================================

    if intent == "experience":

        total_experience = None
        previous_experience = None
        current_experience = None

        if isinstance(experience_data, dict):

            total_experience = experience_data.get(
                "total_experience"
            )

            previous_experience = experience_data.get(
                "previous_experience_years"
            )

            current_experience = experience_data.get(
                "current_company_experience"
            )

        if total_experience is not None:

            answer = (
                f"His total experience is "
                f"{total_experience} years."
            )

            if (
                previous_experience is not None
                and current_experience is not None
            ):

                answer = (
                    f"His total experience is "
                    f"{total_experience} years "
                    f"({previous_experience} years prior "
                    f"experience and "
                    f"{current_experience} years at the "
                    f"current company)."
                )

        else:

            answer = "Experience information is not available."

        state["answer"] = answer
        state["final_answer"] = answer

        return state

    # ========================================================
    # EMPLOYEE ID
    # ========================================================

    if intent == "employee_id":

        if employee_id:

            answer = str(employee_id)

        else:

            answer = "Employee ID information is not available."

        state["answer"] = answer
        state["final_answer"] = answer

        return state

       # ==========================================
    # ATTENDANCE
    # ==========================================

    if intent == "attendance":

        if isinstance(attendance_data, dict):

            if attendance_data.get("success") is False:

                answer = attendance_data.get(
                    "message",
                    "Attendance information is not available."
                )

            else:

                total_records = attendance_data.get(
                    "total_records", 0
                )

                present_days = attendance_data.get(
                    "present_days", 0
                )

                absent_days = attendance_data.get(
                    "absent_days", 0
                )

                leave_days = attendance_data.get(
                    "leave_days", 0
                )

                half_days = attendance_data.get(
                    "half_days", 0
                )

                weekly_offs = attendance_data.get(
                    "weekly_offs", 0
                )

                answer = (
                    f"Attendance summary for {employee_name}: "
                    f"{present_days} present days, "
                    f"{absent_days} absent days, "
                    f"{leave_days} leave days, "
                    f"{half_days} half days, "
                    f"{weekly_offs} weekly offs, "
                    f"out of {total_records} total records."
                )

        else:

            answer = (
                "Attendance information is not available."
            )

        state["answer"] = str(answer)
        state["final_answer"] = str(answer)

        return state

    # ========================================================
    # LEAVE
    # ========================================================

    if intent == "leave":

        if isinstance(leave_data, dict):

            if leave_data.get("success") is False:

                answer = leave_data.get(
                    "message",
                    "Leave information is not available."
                )

            else:

                answer = leave_data.get(
                    "answer",
                    "Leave information is not available."
                )

        else:

            answer = "Leave information is not available."

        state["answer"] = str(answer)
        state["final_answer"] = str(answer)

        return state

    # ========================================================
    # GENERAL QUESTIONS
    # ========================================================

    prompt = f"""
You are a professional HR assistant.

Answer ONLY what the user asked.

Rules:

1. Answer only the current question.
2. Do not provide unrelated employee information.
3. Do not mention databases.
4. Do not mention tools.
5. Do not mention uploaded files.
6. Do not mention internal system details.
7. Do not invent information.
8. Use only the provided data.
9. Keep the answer short and natural.
10. Use normal spaces only.

CURRENT QUESTION:
{query}

CURRENT EMPLOYEE:
{employee_name}

EMPLOYEE ID:
{employee_id}

CURRENT INTENT:
{intent}

SALARY DATA:
{salary_data}

PF DATA:
{pf_data}

EXPERIENCE DATA:
{experience_data}

ATTENDANCE DATA:
{attendance_data}

LEAVE DATA:
{leave_data}

Return only the final answer.
"""

    try:

        response = llm.invoke(prompt)

        answer = str(response.content).strip()

        # Remove Unicode special spaces
        answer = answer.replace("\u202f", " ")
        answer = answer.replace("\u00a0", " ")
        answer = answer.replace("\u2009", " ")
        answer = answer.replace("\u2007", " ")
        answer = answer.replace("\u200a", " ")

        # Fix common missing spaces
        answer = answer.replace(
            "contributionis",
            "contribution is"
        )

        answer = answer.replace(
            "salaryis",
            "salary is"
        )

        answer = answer.replace(
            "experienceis",
            "experience is"
        )

        answer = answer.replace(
            "yearsprior",
            "years prior"
        )

        answer = answer.replace(
            "yearsat",
            "years at"
        )

        answer = answer.replace(
            "permonth",
            "per month"
        )

        # Normalize spaces
        answer = " ".join(answer.split())

        state["answer"] = answer
        state["final_answer"] = answer

    except Exception as error:

        answer = f"Unable to generate answer: {error}"

        state["answer"] = answer
        state["final_answer"] = answer

    return state

# ============================================================
# ALL UPLOADED EMPLOYEES NODE
# ============================================================

def all_uploaded_employees_node(state):

    query = state.get(
        "user_query",
        ""
    ).lower().strip()

    result = all_uploaded_employees.invoke(
        {
            "limit": 10000
        }
    )

    if not isinstance(result, dict):

        message = "Unable to retrieve uploaded employees."

        state["answer"] = message
        state["final_answer"] = message

        return state

    if not result.get("success"):

        message = result.get(
            "message",
            "Unable to retrieve uploaded employees."
        )

        state["answer"] = message
        state["final_answer"] = message

        return state

    employees = result.get(
        "employees",
        []
    )

    total = len(employees)

    if total == 0:

        message = "No uploaded employees found."

        state["answer"] = message
        state["final_answer"] = message

        return state

    # ========================================================
    # COUNT QUERY
    # ========================================================

    count_patterns = [

        "how many employees",

        "how many employee",

        "number of employees",

        "number of employee",

        "total employees",

        "total employee",

        "employee count",

        "total number of employees",

        "total number of employee",

        "count of employees",

        "count of employee",
    ]

    is_count_query = any(
        pattern in query
        for pattern in count_patterns
    )

    if is_count_query:

        answer = (
            f"Total uploaded employees: {total}"
        )

        state["answer"] = answer
        state["final_answer"] = answer

        return state

    # ========================================================
    # FULL EMPLOYEE LIST
    # ========================================================

    lines = [

        f"Total Employees: {total}",

        "",

        "Employee List:",
    ]

    for index, employee in enumerate(
        employees,
        start=1
    ):

        employee_id = employee.get(
            "employee_id",
            "N/A"
        )

        employee_name = employee.get(
            "employee_name",
            "N/A"
        )

        lines.append(
            f"{index}. {employee_name} ({employee_id})"
        )

    answer = "\n".join(lines)

    state["answer"] = answer
    state["final_answer"] = answer

    return state