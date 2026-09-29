import json
import sqlite3

from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_FOLDER = Path("database")

DATABASE_PATH = (
    DATABASE_FOLDER / "dynamic_data.db"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    DATABASE_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# ============================================================
# CREATE TABLES
# ============================================================

def create_dynamic_data_tables():

    connection = get_connection()

    cursor = connection.cursor()

    # --------------------------------------------------------
    # DATASETS TABLE
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS datasets (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            original_filename TEXT NOT NULL,

            stored_filename TEXT,

            file_path TEXT,

            file_type TEXT,

            file_size INTEGER DEFAULT 0,

            row_count INTEGER DEFAULT 0,

            column_count INTEGER DEFAULT 0,

            columns_json TEXT,

            data_type TEXT,

            status TEXT DEFAULT 'SUCCESS',

            error_message TEXT,

            uploaded_at TEXT

        )
        """
    )

    # --------------------------------------------------------
    # DATASET SCHEMA TABLE
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_schema (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            dataset_id INTEGER NOT NULL,

            source_column TEXT NOT NULL,

            canonical_column TEXT,

            data_type TEXT,

            confidence REAL DEFAULT 0,

            created_at TEXT,

            FOREIGN KEY (
                dataset_id
            )
            REFERENCES datasets(id)
            ON DELETE CASCADE

        )
        """
    )

    # --------------------------------------------------------
    # DATASET ROWS TABLE
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_rows (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            dataset_id INTEGER NOT NULL,

            row_number INTEGER NOT NULL,

            row_data_json TEXT NOT NULL,

            created_at TEXT,

            FOREIGN KEY (
                dataset_id
            )
            REFERENCES datasets(id)
            ON DELETE CASCADE

        )
        """
    )

    # --------------------------------------------------------
    # DATASET INDEXES
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_datasets_original_filename
        ON datasets(original_filename)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_datasets_uploaded_at
        ON datasets(uploaded_at)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_dataset_schema_dataset_id
        ON dataset_schema(dataset_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_dataset_schema_canonical_column
        ON dataset_schema(canonical_column)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_dataset_rows_dataset_id
        ON dataset_rows(dataset_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_dataset_rows_row_number
        ON dataset_rows(
            dataset_id,
            row_number
        )
        """
    )

    connection.commit()

    connection.close()


# ============================================================
# CREATE DATASET
# ============================================================

def create_dataset(
    original_filename: str,
    stored_filename: str | None = None,
    file_path: str | None = None,
    file_type: str | None = None,
    file_size: int = 0,
    row_count: int = 0,
    column_count: int = 0,
    columns: list[str] | None = None,
    data_type: str | None = None,
    status: str = "SUCCESS",
    error_message: str | None = None,
):

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    uploaded_at = datetime.now().isoformat(
        timespec="seconds"
    )

    columns_json = json.dumps(
        columns or [],
        ensure_ascii=False,
    )

    cursor.execute(
        """
        INSERT INTO datasets (

            original_filename,
            stored_filename,
            file_path,
            file_type,
            file_size,
            row_count,
            column_count,
            columns_json,
            data_type,
            status,
            error_message,
            uploaded_at

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            original_filename,
            stored_filename,
            file_path,
            file_type,
            file_size,
            row_count,
            column_count,
            columns_json,
            data_type,
            status,
            error_message,
            uploaded_at,
        ),
    )

    dataset_id = cursor.lastrowid

    connection.commit()

    connection.close()

    return get_dataset(dataset_id)


# ============================================================
# CREATE DATASET SCHEMA
# ============================================================

def create_dataset_schema(
    dataset_id: int,
    schema_columns: list[dict[str, Any]],
):

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM dataset_schema
        WHERE dataset_id = ?
        """,
        (
            dataset_id,
        ),
    )

    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

    for column in schema_columns:

        cursor.execute(
            """
            INSERT INTO dataset_schema (

                dataset_id,
                source_column,
                canonical_column,
                data_type,
                confidence,
                created_at

            )

            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                column.get("source_column"),
                column.get("canonical_column"),
                column.get("data_type"),
                column.get("confidence", 0),
                created_at,
            ),
        )

    connection.commit()

    connection.close()

    return get_dataset_schema(
        dataset_id
    )


# ============================================================
# GET DATASET SCHEMA
# ============================================================

def get_dataset_schema(
    dataset_id: int,
):

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT

            id,
            dataset_id,
            source_column,
            canonical_column,
            data_type,
            confidence,
            created_at

        FROM dataset_schema

        WHERE dataset_id = ?

        ORDER BY id ASC
        """,
        (
            dataset_id,
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# SAVE DATASET ROWS
# ============================================================

def create_dataset_rows(
    dataset_id: int,
    rows: list[dict[str, Any]],
):

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

    # --------------------------------------------------------
    # REMOVE EXISTING ROWS
    # --------------------------------------------------------

    cursor.execute(
        """
        DELETE FROM dataset_rows

        WHERE dataset_id = ?
        """,
        (
            dataset_id,
        ),
    )

    # --------------------------------------------------------
    # INSERT NEW ROWS
    # --------------------------------------------------------

    for index, row in enumerate(
        rows,
        start=1,
    ):

        row_data_json = json.dumps(
            row,
            ensure_ascii=False,
            default=str,
        )

        cursor.execute(
            """
            INSERT INTO dataset_rows (

                dataset_id,
                row_number,
                row_data_json,
                created_at

            )

            VALUES (?, ?, ?, ?)
            """,
            (
                dataset_id,
                index,
                row_data_json,
                created_at,
            ),
        )

    connection.commit()

    connection.close()

    return get_dataset_rows(
        dataset_id
    )


# ============================================================
# GET DATASET ROWS
# ============================================================

def get_dataset_rows(
    dataset_id: int,
) -> list[dict[str, Any]]:

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT

            id,
            dataset_id,
            row_number,
            row_data_json,
            created_at

        FROM dataset_rows

        WHERE dataset_id = ?

        ORDER BY row_number ASC
        """,
        (
            dataset_id,
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    results = []

    for row in rows:

        item = dict(row)

        try:

            item["data"] = json.loads(
                item["row_data_json"]
            )

        except Exception:

            item["data"] = {}

        item.pop(
            "row_data_json",
            None,
        )

        results.append(
            item
        )

    return results


# ============================================================
# GET DATASET
# ============================================================

def get_dataset(
    dataset_id: int,
):

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *

        FROM datasets

        WHERE id = ?
        """,
        (
            dataset_id,
        ),
    )

    row = cursor.fetchone()

    connection.close()

    if not row:
        return None

    return row_to_dataset(
        row
    )


# ============================================================
# GET LATEST DATASET
# ============================================================

def get_latest_dataset():

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *

        FROM datasets

        ORDER BY id DESC

        LIMIT 1
        """
    )

    row = cursor.fetchone()

    connection.close()

    if not row:
        return None

    return row_to_dataset(
        row
    )


# ============================================================
# GET ALL DATASETS
# ============================================================

def get_datasets():

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *

        FROM datasets

        ORDER BY id DESC
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        row_to_dataset(row)
        for row in rows
    ]


# ============================================================
# FIND DATASET BY FILENAME
# ============================================================

def find_dataset_by_filename(
    original_filename: str,
):

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *

        FROM datasets

        WHERE original_filename = ?

        ORDER BY id DESC

        LIMIT 1
        """,
        (
            original_filename,
        ),
    )

    row = cursor.fetchone()

    connection.close()

    if not row:
        return None

    return row_to_dataset(
        row
    )


# ============================================================
# FIND DATASETS BY CANONICAL COLUMN
# ============================================================

def find_datasets_by_canonical_column(
    canonical_column: str,
):

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT DISTINCT

            d.*

        FROM datasets d

        INNER JOIN dataset_schema s

            ON d.id = s.dataset_id

        WHERE s.canonical_column = ?

        ORDER BY d.id DESC
        """,
        (
            canonical_column,
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        row_to_dataset(row)
        for row in rows
    ]


# ============================================================
# UPDATE DATASET STATUS
# ============================================================

def update_dataset_status(
    dataset_id: int,
    status: str,
    error_message: str | None = None,
):

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE datasets

        SET

            status = ?,

            error_message = ?

        WHERE id = ?
        """,
        (
            status,
            error_message,
            dataset_id,
        ),
    )

    connection.commit()

    connection.close()

    return get_dataset(
        dataset_id
    )


# ============================================================
# DELETE DATASET
# ============================================================

def delete_dataset(
    dataset_id: int,
):

    create_dynamic_data_tables()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM datasets

        WHERE id = ?
        """,
        (
            dataset_id,
        ),
    )

    deleted = cursor.rowcount > 0

    connection.commit()

    connection.close()

    return deleted


# ============================================================
# CONVERT DATABASE ROW
# ============================================================

def row_to_dataset(
    row,
):

    item = dict(row)

    try:

        item["columns"] = json.loads(
            item.get(
                "columns_json"
            )
            or "[]"
        )

    except Exception:

        item["columns"] = []

    item.pop(
        "columns_json",
        None,
    )

    return item


# ============================================================
# INITIALIZE DATABASE
# ============================================================

create_dynamic_data_tables()