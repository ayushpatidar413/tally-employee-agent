
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from services.gst_excel_report_service import generate_gst_sales_report
from services.dynamic_upload_service import process_uploaded_file
from database.dynamic_data_db import (
    create_dataset,
    create_dataset_schema,
    create_dataset_rows,
)
# ============================================================
# HR / LEGACY DATABASE
# ============================================================

from database.upload_db import (
    create_upload_table,
    get_uploaded_employees,
    count_uploaded_employees,
    record_upload,
    delete_upload,
    upload_employee_file,
)

# ============================================================
# CONVERSATION DATABASE
# ============================================================

from database.conversation_db import (
    create_conversation_tables,
    create_conversation,
    get_conversations,
    get_conversation,
    save_message,
    get_messages,
    update_conversation_title,
    delete_conversation,
)

# ============================================================
# AGENTS
# ============================================================

from graph.supervisor_workflow import supervisor_graph
from graph.dynamic_workflow import dynamic_agent

# ============================================================
# DYNAMIC UPLOAD SERVICES
# ============================================================

from services.dynamic_upload_service import process_uploaded_file

from services.dynamic_dataset_service import (
    get_all_uploaded_datasets,
    get_uploaded_dataset,
    delete_uploaded_dataset,
)

# ============================================================
# DYNAMIC EXPORT SERVICE
# ============================================================

from services.dynamic_export_service import export_rows


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

UPLOADS_DIR = BASE_DIR / "uploads"
GENERATED_DIR = BASE_DIR / "generated"

UPLOADS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

GENERATED_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# FASTAPI APP
# ============================================================
app = FastAPI(
    title="Tally Employee & Dynamic Business Agent",
    description=(
        "HR Agent + Dynamic Business Data Agent "
        "with upload, query and export support."
    ),
    version="1.0.0",
)

# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# INITIALIZE DATABASE TABLES
# ============================================================


# ============================================================
# INITIALIZE DATABASE TABLES
# ============================================================

try:
    create_upload_table()
except Exception as exc:
    print(
        f"[WARNING] Could not initialize upload table: {exc}"
    )

try:
    create_conversation_tables()
except Exception as exc:
    print(
        f"[WARNING] Could not initialize conversation tables: {exc}"
    )


# ============================================================
# REQUEST MODELS
# ============================================================


class AskRequest(BaseModel):
    query: str
    conversation_id: str | None = None
    dataset_id: int | None = None


class CreateConversationRequest(BaseModel):
    title: str | None = None


class SaveMessageRequest(BaseModel):
    role: str
    content: str

class ManualDataRequest(BaseModel):
    dataset_type: str
    rows: list[dict[str, Any]]


# ============================================================
# ROOT
# ============================================================


@app.get("/")
def root():
    return {
        "success": True,
        "message": "Tally Employee & Dynamic Business Agent API",
        "status": "running",
    }


# ============================================================
# HEALTH
# ============================================================


@app.get("/health")
def health():
    return {
        "success": True,
        "status": "healthy",
    }


# ============================================================
# API STATUS
# ============================================================


@app.get("/api-status")
def api_status():
    return {
        "success": True,
        "api": "running",
        "hr_agent": "available",
        "dynamic_agent": "available",
        "upload": "available",
        "export": "available",
    }


# ============================================================
# CONVERSATIONS
# ============================================================


@app.post("/conversations")
def create_new_conversation(
    request: CreateConversationRequest,
):
    try:
        conversation_id = create_conversation(
            title=request.title
        )

        return {
            "success": True,
            "conversation_id": conversation_id,
            "title": request.title,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )




@app.get("/conversations")
def list_conversations():
    try:
        conversations = get_conversations()

        return {
            "success": True,
            "conversations": conversations,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/conversations/{conversation_id}")
def get_conversation_details(
    conversation_id: str,
):
    try:
        conversation = get_conversation(
            conversation_id
        )

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        messages = get_messages(
            conversation_id
        )

        return {
            "success": True,
            "conversation": conversation,
            "messages": messages,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.delete("/conversations/{conversation_id}")
def remove_conversation(
    conversation_id: str,
):
    try:
        deleted = delete_conversation(
            conversation_id
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        return {
            "success": True,
            "message": "Conversation deleted successfully.",
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# LEGACY HR AGENT
# ============================================================


@app.post("/ask")
def ask_hr_agent(request: AskRequest):
    try:
        query = request.query.strip()

        if not query:
            raise HTTPException(
                status_code=400,
                detail="Query cannot be empty.",
            )

        result = supervisor_graph.invoke(
            {
                "question": query,
            }
        )

        answer = result.get(
            "answer",
            result.get(
                "final_answer",
                "No answer generated.",
            ),
        )

        # ----------------------------------------------------
        # Save chat message if conversation is supplied
        # ----------------------------------------------------

        if request.conversation_id:
            try:
                save_message(
                    conversation_id=request.conversation_id,
                    role="user",
                    content=query,
                )

                save_message(
                    conversation_id=request.conversation_id,
                    role="assistant",
                    content=str(answer),
                )

            except Exception as conversation_error:
                print(
                    "[WARNING] Could not save conversation:",
                    conversation_error,
                )

        return {
            "success": True,
            "answer": answer,
            "result": result,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

def is_gst_sales_report_request(query: str) -> bool:
    """
    Detect explicit requests for the specialized
    8-sheet GST Sales Excel report.
    """

    text = query.lower().strip()

    gst_terms = [
        "gst sales report",
        "gst report",
        "gst sales excel",
        "gst report excel",
        "gst sales workbook",
        "gst workbook",
    ]

    report_terms = [
        "generate",
        "create",
        "download",
        "export",
        "make",
        "prepare",
        "excel",
        "xlsx",
        "workbook",
    ]

    has_gst = any(
        term in text
        for term in gst_terms
    )

    has_report_action = any(
        term in text
        for term in report_terms
    )

    return has_gst and has_report_action
# ============================================================
# DYNAMIC BUSINESS AGENT
# ============================================================


@app.post("/ask-business")
def ask_business(request: AskRequest):
    """
    Main endpoint for the Dynamic Business Agent.

    Supports natural-language questions such as:

    - Show ABC Traders data
    - ABC Traders ka data dikhao
    - Show Indore customers
    - Show amount greater than 50000
    - Download ABC Traders data
    - Download ABC Traders data as Excel
    - Export this data as CSV
    - Create PDF report
    """

    try:
        query = request.query.strip()

        if not query:
            raise HTTPException(
                status_code=400,
                detail="Query cannot be empty.",
            )

        # ----------------------------------------------------
        # Invoke Dynamic LangGraph Agent
        # ----------------------------------------------------

        import time

        agent_start_time = time.perf_counter()

        result = dynamic_agent.invoke(
            {
                "question": query,
                "dataset_id": request.dataset_id,
            }
        )

        agent_end_time = time.perf_counter()

        print(
            f"[TIMING] Dynamic Agent: "
            f"{agent_end_time - agent_start_time:.2f} seconds"
        )
        print(
         "[DEBUG API DYNAMIC AGENT]",
          dynamic_agent,
        )

        import graph.dynamic_nodes as dn

        print( 
            "[DEBUG API detect_dynamic_intent FILE]",
            dn.__file__,
        )

        print(
           "[DEBUG API detect_dynamic_intent LINE]",
           dn.detect_dynamic_intent.__code__.co_firstlineno,
        )
        print("[DEBUG API ANSWER] =", repr(result.get("answer")))

        # ----------------------------------------------------
        # Base response
        # ----------------------------------------------------

        response = {
            "success": True,
            "dataset_id": result.get(
                "dataset_id"
            ),
            "intent": result.get(
                "intent"
            ),
            "dataset_type": result.get(
                "dataset_type"
            ),
            "dataset": result.get(
                "dataset"
            ),
            "answer": result.get(
                "answer"
            ),
            "result": result.get(
                "result"
            ),
            "chart": result.get("chart"),
            
            "export_requested": result.get(
                "export_requested",
                False,
            ),
            "export_format": result.get(
                "export_format"
            ),
            "download_url": None,
            "download_filename": None,
        }

        # ----------------------------------------------------
        # Save conversation
        # ----------------------------------------------------

        if request.conversation_id:
            try:
                save_message(
                    conversation_id=request.conversation_id,
                    role="user",
                    content=query,
                )

                save_message(
                    conversation_id=request.conversation_id,
                    role="assistant",
                    content=str(
                        result.get(
                            "answer",
                            "",
                        )
                    ),
                )

            except Exception as conversation_error:
                print(
                    "[WARNING] Could not save business conversation:",
                    conversation_error,
                )

        # ----------------------------------------------------
        # SPECIALIZED GST SALES REPORT
        # ----------------------------------------------------

        if is_gst_sales_report_request(query):

            query_result = result.get(
                "result",
                {},
            )

            if not isinstance(
                query_result,
                dict,
            ):
                query_result = {}

            gst_rows = query_result.get(
                "rows",
                [],
            )
            print(
               "[GST DEBUG] gst_rows =",
               gst_rows,
            )

            if not isinstance(
                gst_rows,
                list,
            ):
                gst_rows = []

            if gst_rows:

                # ---------------------------------------------
                # Generate specialized 8-sheet GST workbook
                # ---------------------------------------------

                gst_filename = (
                    "GST_Sales_Report.xlsx"
                )

                gst_result = generate_gst_sales_report(
                    rows=gst_rows,
                    filename=gst_filename,
                )

                if gst_result.get(
                    "success"
                ):

                    filename = gst_result.get(
                        "filename"
                    )

                    if filename:

                        response[
                            "download_url"
                        ] = (
                            f"/download/{filename}"
                        )

                        response[
                            "download_filename"
                        ] = filename

                        response[
                            "export"
                        ] = gst_result

                        response[
                            "export_requested"
                        ] = True

                        response[
                            "export_format"
                        ] = "xlsx"

                        response[
                            "answer"
                        ] = (
                            "GST Sales Report generated "
                            "successfully with 8 sheets."
                            "\n\n"
                            "Download ready: "
                            + filename
                        )

                else:

                    response[
                        "export_error"
                    ] = gst_result.get(
                        "message",
                        "GST Sales Report generation failed.",
                    )

            else:

                response[
                    "export_error"
                ] = (
                    "There are no matching sales rows "
                    "to generate the GST Sales Report."
                )

        # ----------------------------------------------------
        # EXISTING GENERIC EXPORT
        # ----------------------------------------------------

        # ----------------------------------------------------
        # GENERIC REPORT EXPORT
        # ----------------------------------------------------

        else:

            query_result = result.get(
                "result",
                {},
            )

            if not isinstance(
                query_result,
                dict,
            ):
                query_result = {}

            export_rows_data = query_result.get(
                "rows",
                [],
            )

            if not isinstance(
                export_rows_data,
                list,
            ):
                export_rows_data = []

            # -----------------------------------------------
            # Generate downloadable report when rows exist
            # -----------------------------------------------

            if export_rows_data:

                dataset = result.get(
                    "dataset",
                    {},
                )

                if not isinstance(
                    dataset,
                    dict,
                ):
                    dataset = {}

                original_filename = (
                    dataset.get(
                        "original_filename"
                    )
                    or "dataset"
                )

                dataset_stem = Path(
                    original_filename
                ).stem

                # -------------------------------------------
                # Keep requested export format when supplied
                # Otherwise default to XLSX
                # -------------------------------------------

                export_requested = bool(
                    result.get(
                        "export_requested",
                        False,
                    )
                )

                export_format = (
                    result.get(
                        "export_format"
                    )
                    or "xlsx"
                )

                export_format = str(
                    export_format
                ).lower().replace(
                    ".",
                    "",
                )

                if export_format not in {
                    "xlsx",
                    "csv",
                    "pdf",
                }:
                    export_format = "xlsx"

                # -------------------------------------------
                # Filename
                # -------------------------------------------

                generated_filename = (
                    f"{dataset_stem}_report"
                )

                if export_format == "csv":
                    generated_filename += ".csv"

                elif export_format == "pdf":
                    generated_filename += ".pdf"

                else:
                    generated_filename += ".xlsx"

                # -------------------------------------------
                # Generate file
                # -------------------------------------------

                export_result = export_rows(
                    rows=export_rows_data,
                    file_format=export_format,
                    filename=generated_filename,
                    columns=(
                        result.get(
                            "requested_columns"
                        )
                        or None
                    ),
                    title=(
                        f"{dataset_stem} Report"
                    ),
                    chart=result.get(
                        "chart"
                    ),
                )

                # -------------------------------------------
                # Attach download information
                # -------------------------------------------

                if export_result.get(
                    "success"
                ):

                    filename = (
                        export_result.get(
                            "filename"
                        )
                    )

                    if filename:

                        response[
                            "download_url"
                        ] = (
                            f"/download/{filename}"
                        )

                        response[
                            "download_filename"
                        ] = filename

                        response[
                            "export"
                        ] = export_result

                        response[
                            "export_requested"
                        ] = export_requested

                        response[
                            "export_format"
                        ] = export_format

                else:

                    response[
                        "export_error"
                    ] = export_result.get(
                        "error",
                        export_result.get(
                            "message",
                            "Report generation failed.",
                        ),
                    )

            else:

                # No rows means there is nothing
                # useful to download.
                response[
                    "download_url"
                ] = None

                response[
                    "download_filename"
                ] = None
        return response

    except HTTPException:
        raise

    except Exception as exc:
        print(
            "[ERROR] /ask-business:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# GENERATED FILE DOWNLOAD
# ============================================================


@app.get("/download/{filename}")
def download_generated_file(
    filename: str,
):
    """
    Download a generated CSV/XLSX/PDF file.

    Only files inside the generated directory
    are allowed.
    """

    # --------------------------------------------------------
    # Prevent path traversal
    # --------------------------------------------------------

    safe_name = Path(
        filename
    ).name

    if safe_name != filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename.",
        )

    file_path = (
        GENERATED_DIR / safe_name
    )

    # --------------------------------------------------------
    # File existence
    # --------------------------------------------------------

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Generated file not found.",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Generated file not found.",
        )

    # --------------------------------------------------------
    # Allowed extensions
    # --------------------------------------------------------

    allowed_extensions = {
        ".csv": "text/csv",
        ".xlsx": (
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        ".pdf": "application/pdf",
    }

    media_type = allowed_extensions.get(
        file_path.suffix.lower()
    )

    if not media_type:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type.",
        )

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=media_type,
    )


# ============================================================
# LEGACY HR FILE UPLOAD
# ============================================================


@app.post("/upload-employees")
async def upload_employees(
    file: UploadFile = File(...),
):
    """
    Legacy HR employee upload endpoint.

    Keeps the existing HR upload system working.
    """

    try:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No file selected.",
            )

        extension = Path(
            file.filename
        ).suffix.lower()

        allowed_extensions = {
            ".csv",
            ".xlsx",
            ".xls",
            ".json",
        }

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only CSV, XLSX, XLS and JSON "
                    "files are supported."
                ),
            )

        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        result = upload_employee_file(
            filename=file.filename,
            file_bytes=contents,
        )

        return {
            "success": True,
            **(
                result
                if isinstance(
                    result,
                    dict,
                )
                else {
                    "result": result,
                }
            ),
        }

    except HTTPException:
        raise

    except Exception as exc:
        print(
            "[ERROR] /upload-employees:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# LEGACY HR UPLOAD HISTORY
# ============================================================


@app.get("/upload-history")
def upload_history():
    try:
        uploads = get_uploaded_employees()

        return {
            "success": True,
            "uploads": uploads,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.delete("/upload-history/{upload_id}")
def remove_upload_history(
    upload_id: int,
):
    try:
        result = delete_upload(
            upload_id
        )

        return {
            "success": True,
            "result": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# LEGACY HR EMPLOYEE DATA
# ============================================================


@app.get("/uploaded-employees")
def uploaded_employees():
    try:
        employees = get_uploaded_employees()

        return {
            "success": True,
            "employees": employees,
            "count": len(employees),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/uploaded-employees/count")
def uploaded_employee_count():
    try:
        count = count_uploaded_employees()

        return {
            "success": True,
            "count": count,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# MANUAL DYNAMIC DATA ENTRY
# ============================================================


@app.post("/manual-data")
def create_manual_data(
    request: ManualDataRequest,
):
    try:
        # ----------------------------------------------------
        # Validate dataset type
        # ----------------------------------------------------

        dataset_type = (
            request.dataset_type
            .strip()
            .lower()
        )

        if dataset_type not in {
            "sales",
            "purchase",
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    "dataset_type must be "
                    "'sales' or 'purchase'."
                ),
            )

        # ----------------------------------------------------
        # Validate rows
        # ----------------------------------------------------

        if not request.rows:
            raise HTTPException(
                status_code=400,
                detail="At least one row is required.",
            )

        # ----------------------------------------------------
        # Extract columns
        # ----------------------------------------------------

        columns = []

        for row in request.rows:
            for column in row.keys():
                if column not in columns:
                    columns.append(column)

        if not columns:
            raise HTTPException(
                status_code=400,
                detail="No columns found in manual data.",
            )

        # ----------------------------------------------------
        # Detect schema using existing system
        # ----------------------------------------------------

        from services.schema_detection_service import (
            detect_schema,
        )

        schema = detect_schema(
            filename=f"manual_{dataset_type}",
            columns=columns,
            rows=request.rows,
        )

        # ----------------------------------------------------
        # Create dataset
        # ----------------------------------------------------

        dataset = create_dataset(
            original_filename=(
                f"Manual {dataset_type.title()}"
            ),
            stored_filename=None,
            file_path=None,
            file_type="manual",
            file_size=0,
            row_count=len(request.rows),
            column_count=len(columns),
            columns=columns,
            data_type=dataset_type,
            status="SUCCESS",
        )

        dataset_id = dataset["id"]

        # ----------------------------------------------------
        # Save detected schema
        # ----------------------------------------------------

        saved_schema = create_dataset_schema(
            dataset_id=dataset_id,
            schema_columns=schema.get(
                "columns",
                [],
            ),
        )

        # ----------------------------------------------------
        # Save actual rows
        # ----------------------------------------------------

        saved_rows = create_dataset_rows(
            dataset_id=dataset_id,
            rows=request.rows,
        )

        return {
            "success": True,
            "message": (
                f"Manual {dataset_type} data "
                "saved successfully."
            ),
            "dataset_id": dataset_id,
            "dataset_type": dataset_type,
            "row_count": len(saved_rows),
            "column_count": len(columns),
            "columns": columns,
            "schema": saved_schema,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

# ============================================================
# DYNAMIC DATA UPLOAD
# ============================================================


@app.post("/upload-data")
async def upload_dynamic_data(
    file: UploadFile = File(...),
):
    """
    Generic Dynamic Data upload.

    Supported:
    - CSV
    - XLSX
    - XLS

    The original file is stored in uploads/.
    Dataset metadata, schema and actual rows
    are stored in the dynamic database.
    """

    try:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No file selected.",
            )

        extension = Path(
            file.filename
        ).suffix.lower()

        allowed_extensions = {
            ".csv",
            ".xlsx",
            ".xls",
            ".json",
            ".pdf",
        }

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only CSV, XLSX, XLS, JSON and PDF "
                    "files are supported."
                ),
            )

        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        # ----------------------------------------------------
        # Generate safe stored filename
        # ----------------------------------------------------

        import time

        timestamp = int(
            time.time() * 1000
        )

        original_filename = (
            Path(
                file.filename
            ).name
        )

        stored_filename = (
            f"{timestamp}_"
            f"{original_filename}"
        )

        stored_path = (
            UPLOADS_DIR
            / stored_filename
        )

        # ----------------------------------------------------
        # Save original file
        # ----------------------------------------------------

        with open(
            stored_path,
            "wb",
        ) as output_file:
            output_file.write(
                contents
            )

        # ----------------------------------------------------
        # Process dataset
        # ----------------------------------------------------

        result = process_uploaded_file(
            file_path=str(
                stored_path
            ),
            original_filename=original_filename,
            stored_filename=stored_filename,
        )

        return {
            "success": True,
            "message": (
                "Dataset uploaded and "
                "processed successfully."
            ),
            "original_filename": (
                original_filename
            ),
            "stored_filename": (
                stored_filename
            ),
            "file_path": str(
                stored_path
            ),
            "result": result,
        }

    except HTTPException:
        raise

    except Exception as exc:
        print(
            "[ERROR] /upload-data:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# DYNAMIC DATASET HISTORY
# ============================================================


@app.get("/datasets")
def list_datasets():
    try:
        datasets = (
            get_all_uploaded_datasets()
        )

        return {
            "success": True,
            "datasets": datasets,
            "count": len(datasets),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# SINGLE DATASET
# ============================================================


@app.get("/datasets/{dataset_id}")
def dataset_details(
    dataset_id: int,
):
    try:
        dataset = get_uploaded_dataset(
            dataset_id
        )

        if not dataset:
            raise HTTPException(
                status_code=404,
                detail="Dataset not found.",
            )

        return {
            "success": True,
            "dataset": dataset,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# DELETE DYNAMIC DATASET
# ============================================================


@app.delete("/datasets/{dataset_id}")
def remove_dataset(
    dataset_id: int,
):
    try:
        result = delete_uploaded_dataset(
            dataset_id
        )

        return {
            "success": True,
            "message": (
                "Dataset deleted successfully."
            ),
            "result": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# STARTUP MESSAGE
# ============================================================


@app.on_event("startup")
def startup_event():
    print("=" * 60)
    print(
        "Tally Employee & Dynamic Business Agent API"
    )
    print("=" * 60)
    print("API: http://127.0.0.1:8000")
    print("Docs: http://127.0.0.1:8000/docs")
    print("HR Agent: /ask")
    print("Business Agent: /ask-business")
    print("Upload Data: /upload-data")
    print("Datasets: /datasets")
    print("Download: /download/{filename}")
