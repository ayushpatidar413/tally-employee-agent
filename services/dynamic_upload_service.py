from pathlib import Path

from services.dynamic_data_service import (
    load_structured_data,
    load_excel_sheets,
    get_dataset_info,
    dataframe_to_records,
)

from services.schema_detection_service import (
    detect_schema,
)

from database.dynamic_data_db import (
    create_dataset,
    create_dataset_schema,
    create_dataset_rows,
)


# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
    ".json",
    ".pdf",
}


# ============================================================
# PROCESS UPLOADED FILE
# ============================================================

def process_uploaded_file(
    file_path,
    original_filename=None,
    stored_filename=None,
):
    """
    Process an uploaded structured file.

    CSV / JSON / PDF:
        One file -> one dataset

    XLSX / XLS:
        One workbook -> one dataset per useful sheet
    """

    file_path = Path(file_path)

    # ========================================================
    # VALIDATE FILE
    # ========================================================

    if not file_path.exists():

        return {
            "success": False,
            "message": "File does not exist.",
            "file_path": str(file_path),
        }

    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:

        return {
            "success": False,
            "message": (
                f"Unsupported file type: {extension}. "
                "Supported types are CSV, XLSX, XLS, JSON and PDF."
            ),
            "file_path": str(file_path),
        }

    # ========================================================
    # FILE METADATA
    # ========================================================

    if original_filename is None:
        original_filename = file_path.name

    if stored_filename is None:
        stored_filename = file_path.name

    file_size = file_path.stat().st_size

    file_type = extension.replace(".", "")

    # ========================================================
    # EXCEL MULTI-SHEET FLOW
    # ========================================================

    if extension in {".xlsx", ".xls"}:

        try:

            sheets = load_excel_sheets(
                file_path
            )

        except Exception as error:

            return {
                "success": False,
                "message": "Failed to read Excel workbook.",
                "error": str(error),
                "file_path": str(file_path),
            }

        created_datasets = []

        for sheet_name, dataframe in sheets.items():

            # =================================================
            # DATASET INFORMATION
            # =================================================

            try:

                dataset_info = get_dataset_info(
                    dataframe
                )

            except Exception as error:

                return {
                    "success": False,
                    "message": (
                        f"Failed to analyze Excel sheet "
                        f"'{sheet_name}'."
                    ),
                    "error": str(error),
                    "file_path": str(file_path),
                    "sheet": sheet_name,
                }

            # =================================================
            # CONVERT DATAFRAME TO RECORDS
            # =================================================

            try:

                rows = dataframe_to_records(
                    dataframe
                )

            except Exception as error:

                return {
                    "success": False,
                    "message": (
                        f"Failed to convert Excel sheet "
                        f"'{sheet_name}' into records."
                    ),
                    "error": str(error),
                    "file_path": str(file_path),
                    "sheet": sheet_name,
                }

            if not rows:
                continue

            # =================================================
            # SCHEMA DETECTION
            # =================================================

            try:

                columns = [
                    column["name"]
                    for column in dataset_info["columns"]
                ]

                sheet_filename = (
                    f"{original_filename} — {sheet_name}"
                )

                schema = detect_schema(
                    filename=sheet_filename,
                    columns=columns,
                    rows=rows,
                )

            except Exception as error:

                return {
                    "success": False,
                    "message": (
                        f"Failed to detect schema for "
                        f"Excel sheet '{sheet_name}'."
                    ),
                    "error": str(error),
                    "file_path": str(file_path),
                    "sheet": sheet_name,
                }

            # =================================================
            # CREATE DATASET
            # =================================================

            try:

                dataset = create_dataset(

                    original_filename=sheet_filename,

                    stored_filename=stored_filename,

                    file_path=str(file_path),

                    file_type=file_type,

                    file_size=file_size,

                    row_count=dataset_info[
                        "row_count"
                    ],

                    column_count=dataset_info[
                        "column_count"
                    ],

                    columns=columns,

                    data_type=schema.get(
                        "dataset_type"
                    ),

                    status="SUCCESS",

                )

            except Exception as error:

                return {
                    "success": False,
                    "message": (
                        f"Failed to save dataset metadata "
                        f"for sheet '{sheet_name}'."
                    ),
                    "error": str(error),
                    "file_path": str(file_path),
                    "sheet": sheet_name,
                }

            # =================================================
            # SAVE SCHEMA
            # =================================================

            try:

                saved_schema = create_dataset_schema(

                    dataset_id=dataset["id"],

                    schema_columns=schema.get(
                        "columns",
                        []
                    ),

                )

            except Exception as error:

                return {
                    "success": False,
                    "message": (
                        f"Dataset was created for sheet "
                        f"'{sheet_name}', but schema could "
                        "not be saved."
                    ),
                    "error": str(error),
                    "dataset": dataset,
                }

            # =================================================
            # SAVE ROWS
            # =================================================

            try:

                saved_rows = create_dataset_rows(

                    dataset_id=dataset["id"],

                    rows=rows,

                )

            except Exception as error:

                return {
                    "success": False,
                    "message": (
                        f"Dataset and schema were saved "
                        f"for sheet '{sheet_name}', but "
                        "dataset rows could not be saved."
                    ),
                    "error": str(error),
                    "dataset": dataset,
                    "saved_schema": saved_schema,
                }

            created_datasets.append(
                {
                    "sheet_name": sheet_name,
                    "dataset": dataset,
                    "schema": schema,
                    "saved_schema": saved_schema,
                    "rows_saved": len(saved_rows),
                }
            )

        # =====================================================
        # FINAL EXCEL RESPONSE
        # =====================================================

        return {

            "success": True,

            "message": (
                "Excel workbook uploaded and all useful "
                "sheets were processed successfully."
            ),

            "file": original_filename,

            "sheet_count": len(
                created_datasets
            ),

            "datasets": created_datasets,

        }

    # ========================================================
    # EXISTING SINGLE-DATASET FLOW
    # ========================================================

    try:

        dataframe = load_structured_data(
            file_path
        )

    except Exception as error:

        return {
            "success": False,
            "message": "Failed to read structured file.",
            "error": str(error),
            "file_path": str(file_path),
        }

    # ========================================================
    # VALIDATE DATAFRAME
    # ========================================================

    if dataframe is None:

        return {
            "success": False,
            "message": "No dataframe was returned.",
            "file_path": str(file_path),
        }

    if dataframe.empty:

        return {
            "success": False,
            "message": "Uploaded file contains no data.",
            "file_path": str(file_path),
        }

    # ========================================================
    # DATASET INFORMATION
    # ========================================================

    try:

        dataset_info = get_dataset_info(
            dataframe
        )

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to analyze uploaded dataset."
            ),
            "error": str(error),
            "file_path": str(file_path),
        }

    # ========================================================
    # CONVERT DATAFRAME TO RECORDS
    # ========================================================

    try:

        rows = dataframe_to_records(
            dataframe
        )

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to convert uploaded data "
                "into records."
            ),
            "error": str(error),
            "file_path": str(file_path),
        }

    # ========================================================
    # SCHEMA DETECTION
    # ========================================================

    try:

        columns = [
            column["name"]
            for column in dataset_info["columns"]
        ]

        schema = detect_schema(
            filename=original_filename,
            columns=columns,
            rows=rows,
        )

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to detect dataset schema."
            ),
            "error": str(error),
            "file_path": str(file_path),
        }

    # ========================================================
    # CREATE DATASET
    # ========================================================

    try:

        dataset = create_dataset(

            original_filename=original_filename,

            stored_filename=stored_filename,

            file_path=str(file_path),

            file_type=file_type,

            file_size=file_size,

            row_count=dataset_info[
                "row_count"
            ],

            column_count=dataset_info[
                "column_count"
            ],

            columns=columns,

            data_type=schema.get(
                "dataset_type"
            ),

            status="SUCCESS",

        )

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Failed to save dataset metadata."
            ),
            "error": str(error),
            "file_path": str(file_path),
        }

    # ========================================================
    # SAVE SCHEMA
    # ========================================================

    try:

        saved_schema = create_dataset_schema(

            dataset_id=dataset["id"],

            schema_columns=schema.get(
                "columns",
                []
            ),

        )

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Dataset was created, but "
                "schema could not be saved."
            ),
            "error": str(error),
            "dataset": dataset,
        }

    # ========================================================
    # SAVE ACTUAL DATASET ROWS
    # ========================================================

    try:

        saved_rows = create_dataset_rows(

            dataset_id=dataset["id"],

            rows=rows,

        )

    except Exception as error:

        return {
            "success": False,
            "message": (
                "Dataset and schema were saved, "
                "but dataset rows could not be saved."
            ),
            "error": str(error),
            "dataset": dataset,
            "saved_schema": saved_schema,
        }

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return {

        "success": True,

        "message": (
            "File uploaded and processed successfully."
        ),

        "dataset": dataset,

        "schema": schema,

        "saved_schema": saved_schema,

        "rows_saved": len(saved_rows),

    }