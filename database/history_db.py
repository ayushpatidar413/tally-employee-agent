import sqlite3
from datetime import datetime
from pathlib import Path


# ============================================================
# DATABASE PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

HISTORY_DB = BASE_DIR / "hr_history.db"


# ============================================================
# CONNECTION
# ============================================================

def get_history_connection():
    connection = sqlite3.connect(HISTORY_DB)
    connection.row_factory = sqlite3.Row
    return connection


# ============================================================
# CREATE TABLE
# ============================================================

def create_history_table():

    connection = get_history_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_query TEXT NOT NULL,

            intent TEXT,

            employee_name TEXT,

            employee_id TEXT,

            answer TEXT NOT NULL,

            created_at TEXT NOT NULL

        )
        """
    )

    connection.commit()
    connection.close()


# ============================================================
# SAVE CHAT HISTORY
# ============================================================

def save_chat_history(
    user_query,
    answer,
    intent=None,
    employee_name=None,
    employee_id=None
):

    connection = get_history_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO chat_history
        (
            user_query,
            intent,
            employee_name,
            employee_id,
            answer,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_query,
            intent,
            employee_name,
            employee_id,
            answer,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        )
    )

    connection.commit()
    connection.close()


# ============================================================
# GET ALL HISTORY
# ============================================================

def get_chat_history(limit=50):

    connection = get_history_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            user_query,
            intent,
            employee_name,
            employee_id,
            answer,
            created_at
        FROM chat_history
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ============================================================
# GET EMPLOYEE HISTORY
# ============================================================

def get_employee_history(employee_name):

    connection = get_history_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            user_query,
            intent,
            employee_name,
            employee_id,
            answer,
            created_at
        FROM chat_history
        WHERE LOWER(employee_name) = LOWER(?)
        ORDER BY id DESC
        """,
        (employee_name,)
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ============================================================
# SEARCH PREVIOUS QUESTIONS
# ============================================================

def search_chat_history(search_text):

    connection = get_history_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            user_query,
            intent,
            employee_name,
            employee_id,
            answer,
            created_at
        FROM chat_history
        WHERE
            LOWER(user_query) LIKE LOWER(?)
            OR LOWER(answer) LIKE LOWER(?)
        ORDER BY id DESC
        """,
        (
            f"%{search_text}%",
            f"%{search_text}%"
        )
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ============================================================
# DELETE HISTORY
# ============================================================

def clear_chat_history():

    connection = get_history_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM chat_history"
    )

    connection.commit()
    connection.close()