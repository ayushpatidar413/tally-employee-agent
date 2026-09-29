from database.database import get_connection


# ============================================================
# GET EMPLOYEE BY ID
# ============================================================

def get_employee_by_id(employee_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            employee_id,
            employee_name,
            department,
            designation,
            employment_type,
            joining_date,
            monthly_salary,
            previous_experience_years,
            current_company_experience,
            total_experience,
            pf_applicable,
            pf_rate,
            employee_pf,
            employer_pf,
            employment_status
        FROM employees
        WHERE employee_id = ?
        """,
        (employee_id,)
    )

    row = cursor.fetchone()
    connection.close()

    if row is None:
        return {
            "success": False,
            "message": f"Employee {employee_id} not found."
        }

    return {
        "success": True,
        "employee_id": row["employee_id"],
        "employee_name": row["employee_name"],
        "department": row["department"],
        "designation": row["designation"],
        "employment_type": row["employment_type"],
        "joining_date": row["joining_date"],
        "monthly_salary": row["monthly_salary"],
        "previous_experience_years": row["previous_experience_years"],
        "current_company_experience": row["current_company_experience"],
        "total_experience": row["total_experience"],
        "pf_applicable": row["pf_applicable"],
        "pf_rate": row["pf_rate"],
        "employee_pf": row["employee_pf"],
        "employer_pf": row["employer_pf"],
        "employment_status": row["employment_status"]
    }


# ============================================================
# GET EMPLOYEE
# ============================================================

def get_employee(employee_id: str):
    return get_employee_by_id(employee_id)


# ============================================================
# GET EMPLOYEE BY NAME
# ============================================================

def get_employee_by_name(employee_name: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            employee_id,
            employee_name,
            department,
            designation,
            employment_type,
            joining_date,
            monthly_salary,
            previous_experience_years,
            current_company_experience,
            total_experience,
            pf_applicable,
            pf_rate,
            employee_pf,
            employer_pf,
            employment_status
        FROM employees
        WHERE LOWER(employee_name) = LOWER(?)
        """,
        (employee_name.strip(),)
    )

    rows = cursor.fetchall()
    connection.close()

    if not rows:
        return {
            "success": False,
            "message": f"Employee {employee_name} not found.",
            "employees": []
        }

    employees = []

    for row in rows:
        employees.append({
            "employee_id": row["employee_id"],
            "employee_name": row["employee_name"],
            "department": row["department"],
            "designation": row["designation"],
            "employment_type": row["employment_type"],
            "joining_date": row["joining_date"],
            "monthly_salary": row["monthly_salary"],
            "previous_experience_years": row["previous_experience_years"],
            "current_company_experience": row["current_company_experience"],
            "total_experience": row["total_experience"],
            "pf_applicable": row["pf_applicable"],
            "pf_rate": row["pf_rate"],
            "employee_pf": row["employee_pf"],
            "employer_pf": row["employer_pf"],
            "employment_status": row["employment_status"]
        })

    return {
        "success": True,
        "employees": employees,
        "count": len(employees)
    }


# ============================================================
# FIND EMPLOYEE BY NAME
# ============================================================

def find_employee_by_name(employee_name: str):
    return get_employee_by_name(employee_name)


# ============================================================
# GET EMPLOYEE SALARY
# ============================================================

def get_employee_salary(employee_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            employee_id,
            employee_name,
            month,
            year,
            monthly_salary,
            working_days,
            present_days,
            absent_days,
            leave_days,
            half_days,
            free_leave_days,
            unpaid_absence_days,
            per_day_salary,
            gross_salary,
            absence_deduction,
            leave_deduction,
            employee_pf,
            other_deduction,
            net_salary
        FROM salary
        WHERE employee_id = ?
        ORDER BY year DESC, month DESC
        LIMIT 1
        """,
        (employee_id,)
    )

    row = cursor.fetchone()
    connection.close()

    if row is None:
        return {
            "success": False,
            "message": f"Salary data for {employee_id} not found."
        }

    return {
        "success": True,
        "employee_id": row["employee_id"],
        "employee_name": row["employee_name"],
        "month": row["month"],
        "year": row["year"],
        "monthly_salary": row["monthly_salary"],
        "working_days": row["working_days"],
        "present_days": row["present_days"],
        "absent_days": row["absent_days"],
        "leave_days": row["leave_days"],
        "half_days": row["half_days"],
        "free_leave_days": row["free_leave_days"],
        "unpaid_absence_days": row["unpaid_absence_days"],
        "per_day_salary": row["per_day_salary"],
        "gross_salary": row["gross_salary"],
        "absence_deduction": row["absence_deduction"],
        "leave_deduction": row["leave_deduction"],
        "employee_pf": row["employee_pf"],
        "other_deduction": row["other_deduction"],
        "net_salary": row["net_salary"]
    }


# ============================================================
# GET EMPLOYEE PF
# ============================================================

def get_employee_pf(employee_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            employee_id,
            employee_name,
            month,
            year,
            pf_applicable,
            pf_rate,
            pf_wage,
            employee_pf,
            employer_pf,
            total_pf,
            pf_status
        FROM pf_records
        WHERE employee_id = ?
        ORDER BY year DESC, month DESC
        LIMIT 1
        """,
        (employee_id,)
    )

    row = cursor.fetchone()
    connection.close()

    if row is None:
        return {
            "success": False,
            "message": f"PF data for {employee_id} not found."
        }

    return {
        "success": True,
        "employee_id": row["employee_id"],
        "employee_name": row["employee_name"],
        "month": row["month"],
        "year": row["year"],
        "pf_applicable": row["pf_applicable"],
        "pf_rate": row["pf_rate"],
        "pf_wage": row["pf_wage"],
        "employee_pf": row["employee_pf"],
        "employer_pf": row["employer_pf"],
        "total_pf": row["total_pf"],
        "pf_status": row["pf_status"]
    }


# ============================================================
# GET EMPLOYEE EXPERIENCE
# ============================================================

def get_employee_experience(employee_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            employee_id,
            employee_name,
            previous_experience_years,
            current_company_experience,
            total_experience
        FROM employees
        WHERE employee_id = ?
        """,
        (employee_id,)
    )

    row = cursor.fetchone()
    connection.close()

    if row is None:
        return {
            "success": False,
            "message": f"Employee {employee_id} not found."
        }

    return {
        "success": True,
        "employee_id": row["employee_id"],
        "employee_name": row["employee_name"],
        "previous_experience_years": row["previous_experience_years"],
        "current_company_experience": row["current_company_experience"],
        "total_experience": row["total_experience"]
    }


# ============================================================
# GET ALL EMPLOYEES
# ============================================================

def get_all_employees():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            employee_id,
            employee_name,
            department,
            designation,
            employment_type,
            joining_date,
            monthly_salary,
            previous_experience_years,
            current_company_experience,
            total_experience,
            pf_applicable,
            pf_rate,
            employee_pf,
            employer_pf,
            employment_status
        FROM employees
        ORDER BY employee_id
        """
    )

    rows = cursor.fetchall()
    connection.close()

    employees = []

    for row in rows:
        employees.append({
            "employee_id": row["employee_id"],
            "employee_name": row["employee_name"],
            "department": row["department"],
            "designation": row["designation"],
            "employment_type": row["employment_type"],
            "joining_date": row["joining_date"],
            "monthly_salary": row["monthly_salary"],
            "previous_experience_years": row["previous_experience_years"],
            "current_company_experience": row["current_company_experience"],
            "total_experience": row["total_experience"],
            "pf_applicable": row["pf_applicable"],
            "pf_rate": row["pf_rate"],
            "employee_pf": row["employee_pf"],
            "employer_pf": row["employer_pf"],
            "employment_status": row["employment_status"]
        })

    return {
        "success": True,
        "count": len(employees),
        "employees": employees
    }
    