import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


# ============================================================
# DATABASE PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "conversations.db"


# ============================================================
# CONNECTION
# ============================================================

def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# ============================================================
# CREATE TABLES
# ============================================================

def create_conversation_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id)
                REFERENCES conversations(conversation_id)
                ON DELETE CASCADE
        )
        """
    )

    connection.commit()
    connection.close()


# ============================================================
# CREATE CONVERSATION
# ============================================================

def create_conversation(
    title="New Conversation",
    conversation_id=None,
):
    """
    Create a new conversation.

    Supports both:

        create_conversation("My Chat")

    and:

        create_conversation(
            conversation_id="abc",
            title="My Chat"
        )
    """

    if conversation_id is None:
        conversation_id = str(uuid.uuid4())

    conversation_id = str(conversation_id)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO conversations (
            conversation_id,
            title,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            conversation_id,
            title or "New Conversation",
            now,
            now,
        ),
    )

    connection.commit()
    connection.close()

    return conversation_id


# ============================================================
# GET ALL CONVERSATIONS
# ============================================================

def get_conversations():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            conversation_id,
            title,
            created_at,
            updated_at
        FROM conversations
        ORDER BY updated_at DESC
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ============================================================
# GET ONE CONVERSATION
# ============================================================

def get_conversation(conversation_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            conversation_id,
            title,
            created_at,
            updated_at
        FROM conversations
        WHERE conversation_id = ?
        """,
        (str(conversation_id),),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)


# ============================================================
# GET MESSAGES
# ============================================================

def get_messages(conversation_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            conversation_id,
            role,
            message,
            created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        """,
        (str(conversation_id),),
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ============================================================
# SAVE MESSAGE
# ============================================================

def save_message(
    conversation_id,
    role,
    message,
):
    conversation_id = str(conversation_id)

    connection = get_connection()
    cursor = connection.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        INSERT INTO messages (
            conversation_id,
            role,
            message,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            conversation_id,
            role,
            str(message),
            now,
        ),
    )

    cursor.execute(
        """
        UPDATE conversations
        SET updated_at = ?
        WHERE conversation_id = ?
        """,
        (
            now,
            conversation_id,
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# ADD MESSAGE
# Compatibility wrapper
# ============================================================

def add_message(
    conversation_id,
    role,
    message,
):
    save_message(
        conversation_id=conversation_id,
        role=role,
        message=message,
    )


# ============================================================
# UPDATE TITLE
# ============================================================

def update_conversation_title(
    conversation_id,
    title,
):
    connection = get_connection()
    cursor = connection.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        UPDATE conversations
        SET
            title = ?,
            updated_at = ?
        WHERE conversation_id = ?
        """,
        (
            title,
            now,
            str(conversation_id),
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# TOUCH CONVERSATION
# ============================================================

def touch_conversation(conversation_id):
    connection = get_connection()
    cursor = connection.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        UPDATE conversations
        SET updated_at = ?
        WHERE conversation_id = ?
        """,
        (
            now,
            str(conversation_id),
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# GET FULL CONVERSATION HISTORY
# ============================================================

def get_conversation_history(conversation_id):
    conversation = get_conversation(conversation_id)

    if conversation is None:
        return None

    messages = get_messages(conversation_id)

    conversation["messages"] = messages

    return conversation


# ============================================================
# DELETE CONVERSATION
# ============================================================

def delete_conversation(conversation_id):
    conversation_id = str(conversation_id)

    connection = get_connection()
    cursor = connection.cursor()

    # Delete messages first because existing databases
    # may not have foreign-key cascade enabled.
    cursor.execute(
        """
        DELETE FROM messages
        WHERE conversation_id = ?
        """,
        (conversation_id,),
    )

    cursor.execute(
        """
        DELETE FROM conversations
        WHERE conversation_id = ?
        """,
        (conversation_id,),
    )

    deleted = cursor.rowcount

    connection.commit()
    connection.close()

    return deleted > 0


# ============================================================
# INITIALIZE DATABASE
# ============================================================

create_conversation_tables()