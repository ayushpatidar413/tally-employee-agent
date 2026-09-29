from database import get_connection


def create_tables():

    connection = get_connection()
    cursor = connection.cursor()

    # --------------------------------------------------
    # EMPLOYEES
    # --------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            employee_name TEXT NOT NULL,
            department TEXT,
            designation TEXT,
            employment_type TEXT,
            joining_date TEXT,
            monthly_salary REAL,
            previous_experience_years REAL,
            current_company_experience REAL,
            total_experience REAL,
            pf_applicable TEXT,
            pf_rate REAL,
            employee_pf REAL,
            employer_pf REAL,
            employment_status TEXT
        )
    """)

    # --------------------------------------------------
    # ATTENDANCE
    # --------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            employee_name TEXT,
            department TEXT,
            date TEXT,
            day TEXT,
            attendance_status TEXT,
            check_in TEXT,
            check_out TEXT,
            working_hours REAL,
            leave_type TEXT,
            remarks TEXT
        )
    """)

    # --------------------------------------------------
    # LEAVE
    # --------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaves (
            leave_id TEXT PRIMARY KEY,
            employee_id TEXT,
            employee_name TEXT,
            leave_date TEXT,
            leave_type TEXT,
            paid_unpaid TEXT,
            leave_days REAL,
            approval_status TEXT,
            reason TEXT
        )
    """)

    # --------------------------------------------------
    # SALARY
    # --------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            employee_name TEXT,
            month TEXT,
            year INTEGER,
            monthly_salary REAL,
            working_days INTEGER,
            present_days INTEGER,
            absent_days INTEGER,
            leave_days INTEGER,
            half_days INTEGER,
            free_leave_days INTEGER,
            unpaid_absence_days INTEGER,
            per_day_salary REAL,
            gross_salary REAL,
            absence_deduction REAL,
            leave_deduction REAL,
            employee_pf REAL,
            other_deduction REAL,
            net_salary REAL
        )
    """)

    # --------------------------------------------------
    # PF
    # --------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pf_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            employee_name TEXT,
            month TEXT,
            year INTEGER,
            pf_applicable TEXT,
            pf_rate REAL,
            pf_wage REAL,
            employee_pf REAL,
            employer_pf REAL,
            total_pf REAL,
            pf_status TEXT
        )
    """)

    # --------------------------------------------------
    # MONTHLY SUMMARY
    # --------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            employee_name TEXT,
            department TEXT,
            month TEXT,
            working_days INTEGER,
            present_days INTEGER,
            absent_days INTEGER,
            leave_days INTEGER,
            half_days INTEGER,
            attendance_percentage REAL,
            free_leave_allowed INTEGER,
            free_leave_used INTEGER,
            unpaid_absence_days INTEGER,
            monthly_salary REAL,
            absence_deduction REAL,
            employee_pf REAL,
            employer_pf REAL,
            total_pf REAL,
            net_salary REAL,
            current_company_experience REAL,
            previous_experience REAL,
            total_experience REAL
        )
    """)

    connection.commit()
    connection.close()

    print("All tables created successfully.")


if __name__ == "__main__":
    create_tables()