from pathlib import Path
from typing import Any
import re
import pandas as pd
from pypdf import PdfReader

# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

SUPPORTED_STRUCTURED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
    ".json",
    ".pdf",
}

def read_pdf_file(
    file_path: str | Path,
) -> pd.DataFrame:
    """
    Extract a simple table from a text-based PDF.

    Expected PDF structure:

        Column 1    Column 2    Column 3
        value       value       value
        value       value       value

    This intentionally handles text-based PDFs first.
    Scanned/image-only PDFs require OCR and are not handled here.
    """

    reader = PdfReader(
        str(file_path)
    )

    lines = []

    for page in reader.pages:
        text = page.extract_text()

        if not text:
            continue

        for line in text.splitlines():
            line = line.strip()

            if line:
                lines.append(line)

    if not lines:
        raise ValueError(
            "PDF contains no extractable text. "
            "Scanned/image-only PDFs require OCR."
        )

    # --------------------------------------------------------
    # Try to detect a table using tabs or repeated spaces.
    # --------------------------------------------------------

    table_lines = []

    for line in lines:
        parts = [
            part.strip()
            for part in re.split(
                r"\t+|\s{2,}",
                line,
            )
            if part.strip()
        ]

        if len(parts) >= 2:
            table_lines.append(parts)

    if len(table_lines) < 2:
        raise ValueError(
            "Could not detect a tabular structure in the PDF."
        )

    header = table_lines[0]

    rows = []

    for parts in table_lines[1:]:
        if len(parts) < len(header):
            parts = parts + (
                [None]
                * (
                    len(header)
                    - len(parts)
                )
            )

        elif len(parts) > len(header):
            parts = parts[:len(header)]

        rows.append(parts)

    return pd.DataFrame(
        rows,
        columns=header,
    )
# ============================================================
# READ STRUCTURED FILE
# ============================================================

def read_structured_file(
    file_path: str | Path,
) -> pd.DataFrame:
    """
    Read CSV, Excel, or JSON file into a Pandas DataFrame.

    This function is completely generic.
    It does not expect employee-specific columns.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    extension = path.suffix.lower()

    if extension == ".csv":
        dataframe = pd.read_csv(path)

    elif extension in {".xlsx", ".xls"}:
        dataframe = pd.read_excel(path)

    elif extension == ".json":
        dataframe = pd.read_json(path)
    
    elif extension == ".pdf":
       dataframe = read_pdf_file(path)

    else:
        raise ValueError(
            "Unsupported structured file type. "
            "Supported formats: CSV, XLSX, XLS, JSON and PDF."
        )

    return dataframe


# ============================================================
# CLEAN DATAFRAME
# ============================================================

def clean_dataframe(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Clean column names and remove completely empty rows/columns.
    """

    dataframe = dataframe.copy()

    # Convert column names to clean strings.
    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    # Remove completely empty rows.
    dataframe = dataframe.dropna(
        how="all"
    )

    # Remove completely empty columns.
    dataframe = dataframe.dropna(
        axis=1,
        how="all",
    )

    return dataframe

# ============================================================
# LOAD EXCEL SHEETS
# ============================================================

def load_excel_sheets(
    file_path: str | Path,
) -> dict[str, pd.DataFrame]:
    """
    Read all useful sheets from an Excel workbook.

    Each sheet is returned as a separate cleaned DataFrame.

    Empty sheets are ignored.
    Completely empty rows/columns are removed by the
    existing clean_dataframe() function.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    extension = path.suffix.lower()

    if extension not in {".xlsx", ".xls"}:
        raise ValueError(
            "load_excel_sheets() supports only XLSX and XLS files."
        )

    workbook = pd.read_excel(
        path,
        sheet_name=None,
    )

    useful_sheets = {}

    for sheet_name, dataframe in workbook.items():

        dataframe = clean_dataframe(
            dataframe
        )

        if dataframe.empty:
            continue

        useful_sheets[str(sheet_name)] = dataframe

    if not useful_sheets:
        raise ValueError(
            "Excel workbook contains no usable sheets."
        )

    return useful_sheets

# ============================================================
# LOAD DATA
# ============================================================

def load_structured_data(
    file_path: str | Path,
) -> pd.DataFrame:
    """
    Read and clean a structured file.
    """

    dataframe = read_structured_file(
        file_path
    )

    dataframe = clean_dataframe(
        dataframe
    )

    return dataframe


# ============================================================
# DATASET INFORMATION
# ============================================================

def get_dataset_info(
    dataframe: pd.DataFrame,
) -> dict[str, Any]:
    """
    Return generic information about the uploaded dataset.
    """

    dataframe = clean_dataframe(
        dataframe
    )

    columns = []

    for column in dataframe.columns:

        series = dataframe[column]

        columns.append(
            {
                "name": str(column),
                "dtype": str(series.dtype),
                "non_null_count": int(
                    series.notna().sum()
                ),
                "unique_count": int(
                    series.nunique(
                        dropna=True
                    )
                ),
            }
        )

    return {
        "row_count": int(
            len(dataframe)
        ),
        "column_count": int(
            len(dataframe.columns)
        ),
        "columns": columns,
    }


# ============================================================
# COLUMN SEARCH
# ============================================================

def find_column(
    dataframe: pd.DataFrame,
    requested_column: str,
) -> str | None:
    """
    Find a column using a flexible case-insensitive match.
    """

    requested = (
        str(requested_column)
        .strip()
        .lower()
    )

    for column in dataframe.columns:

        if (
            str(column)
            .strip()
            .lower()
            == requested
        ):
            return str(column)

    # Try normalized comparison.
    requested_normalized = (
        requested
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )

    for column in dataframe.columns:

        column_normalized = (
            str(column)
            .strip()
            .lower()
            .replace("_", "")
            .replace("-", "")
            .replace(" ", "")
        )

        if (
            column_normalized
            == requested_normalized
        ):
            return str(column)

    return None


# ============================================================
# NUMERIC COLUMNS
# ============================================================

def get_numeric_columns(
    dataframe: pd.DataFrame,
) -> list[str]:
    """
    Return columns that contain numeric data.
    """

    numeric_columns = dataframe.select_dtypes(
        include="number"
    ).columns.tolist()

    return [
        str(column)
        for column in numeric_columns
    ]


# ============================================================
# TEXT COLUMNS
# ============================================================

def get_text_columns(
    dataframe: pd.DataFrame,
) -> list[str]:
    """
    Return columns that contain object/string data.
    """

    text_columns = dataframe.select_dtypes(
        include=["object", "string"]
    ).columns.tolist()

    return [
        str(column)
        for column in text_columns
    ]


# ============================================================
# DATASET PREVIEW
# ============================================================

def get_dataset_preview(
    dataframe: pd.DataFrame,
    rows: int = 5,
) -> list[dict[str, Any]]:
    """
    Return a small preview of the dataset.
    """

    preview = dataframe.head(
        rows
    ).copy()

    return dataframe_to_records(
        preview
    )


# ============================================================
# DATAFRAME -> SAFE RECORDS
# ============================================================

def dataframe_to_records(
    dataframe: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Convert DataFrame rows into JSON-safe dictionaries.
    """

    records = []

    for record in dataframe.to_dict(
        orient="records"
    ):

        cleaned_record = {}

        for key, value in record.items():

            cleaned_record[
                str(key)
            ] = clean_value(value)

        records.append(
            cleaned_record
        )

    return records


# ============================================================
# CLEAN INDIVIDUAL VALUE
# ============================================================

def clean_value(
    value: Any,
) -> Any:
    """
    Convert Pandas/Numpy values into JSON-safe values.
    """

    if pd.isna(value):
        return None

    if isinstance(
        value,
        (
            pd.Timestamp,
            pd.Timedelta,
        ),
    ):
        return str(value)

    if hasattr(
        value,
        "item",
    ):
        try:
            return value.item()
        except Exception:
            pass

    return value


# ============================================================
# COLUMN VALUES
# ============================================================

def get_unique_values(
    dataframe: pd.DataFrame,
    column_name: str,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Return unique values from a column.
    """

    actual_column = find_column(
        dataframe,
        column_name,
    )

    if actual_column is None:
        return {
            "success": False,
            "message": (
                "The information is not available "
                "in the uploaded file."
            ),
        }

    values = (
        dataframe[actual_column]
        .dropna()
        .drop_duplicates()
        .head(limit)
        .tolist()
    )

    return {
        "success": True,
        "column": actual_column,
        "values": [
            clean_value(value)
            for value in values
        ],
        "count": int(
            dataframe[actual_column]
            .nunique(
                dropna=True
            )
        ),
    }


# ============================================================
# COLUMN SUMMARY
# ============================================================

def summarize_column(
    dataframe: pd.DataFrame,
    column_name: str,
) -> dict[str, Any]:
    """
    Calculate generic statistics for one column.
    """

    actual_column = find_column(
        dataframe,
        column_name,
    )

    if actual_column is None:
        return {
            "success": False,
            "message": (
                "The information is not available "
                "in the uploaded file."
            ),
        }

    series = dataframe[
        actual_column
    ]

    result = {
        "success": True,
        "column": actual_column,
        "dtype": str(
            series.dtype
        ),
        "count": int(
            series.notna().sum()
        ),
        "unique_count": int(
            series.nunique(
                dropna=True
            )
        ),
    }

    if pd.api.types.is_numeric_dtype(
        series
    ):

        result.update(
            {
                "sum": clean_value(
                    series.sum()
                ),
                "average": clean_value(
                    series.mean()
                ),
                "minimum": clean_value(
                    series.min()
                ),
                "maximum": clean_value(
                    series.max()
                ),
            }
        )

    return result


# ============================================================
# NUMERIC CALCULATIONS
# ============================================================

def calculate_numeric(
    dataframe: pd.DataFrame,
    column_name: str,
    operation: str,
) -> dict[str, Any]:
    """
    Perform exact numeric calculations.

    Supported operations:
    - sum
    - average
    - mean
    - min
    - max
    - count
    """

    actual_column = find_column(
        dataframe,
        column_name,
    )

    if actual_column is None:
        return {
            "success": False,
            "message": (
                "The information is not available "
                "in the uploaded file."
            ),
        }

    series = pd.to_numeric(
        dataframe[actual_column],
        errors="coerce",
    )

    valid_values = series.dropna()

    if len(valid_values) == 0:
        return {
            "success": False,
            "message": (
                f"Column '{actual_column}' "
                "does not contain numeric data."
            ),
        }

    operation = (
        str(operation)
        .strip()
        .lower()
    )

    if operation == "sum":

        value = valid_values.sum()

    elif operation in {
        "average",
        "avg",
        "mean",
    }:

        value = valid_values.mean()

    elif operation == "min":

        value = valid_values.min()

    elif operation == "max":

        value = valid_values.max()

    elif operation == "count":

        value = len(valid_values)

    else:

        return {
            "success": False,
            "message": (
                f"Unsupported calculation: "
                f"{operation}"
            ),
        }

    return {
        "success": True,
        "column": actual_column,
        "operation": operation,
        "value": clean_value(value),
        "count": int(
            len(valid_values)
        ),
    }


# ============================================================
# FILTER DATA
# ============================================================

def filter_data(
    dataframe: pd.DataFrame,
    column_name: str,
    value: Any,
) -> dict[str, Any]:
    """
    Filter rows where a column matches a value.

    Matching is case-insensitive for text values.
    """

    actual_column = find_column(
        dataframe,
        column_name,
    )

    if actual_column is None:
        return {
            "success": False,
            "message": (
                "The information is not available "
                "in the uploaded file."
            ),
        }

    series = dataframe[
        actual_column
    ]

    if pd.api.types.is_numeric_dtype(
        series
    ):

        numeric_value = pd.to_numeric(
            value,
            errors="coerce",
        )

        if pd.isna(
            numeric_value
        ):
            return {
                "success": False,
                "message": (
                    f"Invalid numeric value: "
                    f"{value}"
                ),
            }

        mask = (
            pd.to_numeric(
                series,
                errors="coerce",
            )
            == numeric_value
        )

    else:

        mask = (
            series.astype(str)
            .str.strip()
            .str.lower()
            ==
            str(value)
            .strip()
            .lower()
        )

    filtered = dataframe[
        mask
    ].copy()

    return {
        "success": True,
        "column": actual_column,
        "value": value,
        "row_count": int(
            len(filtered)
        ),
        "records": dataframe_to_records(
            filtered.head(100)
        ),
    }


# ============================================================
# GROUP BY
# ============================================================

def group_and_aggregate(
    dataframe: pd.DataFrame,
    group_column: str,
    value_column: str,
    operation: str = "sum",
) -> dict[str, Any]:
    """
    Group data by one column and calculate
    an aggregate on another column.
    """

    actual_group_column = find_column(
        dataframe,
        group_column,
    )

    actual_value_column = find_column(
        dataframe,
        value_column,
    )

    if (
        actual_group_column is None
        or actual_value_column is None
    ):
        return {
            "success": False,
            "message": (
                "The information is not available "
                "in the uploaded file."
            ),
        }

    numeric_values = pd.to_numeric(
        dataframe[actual_value_column],
        errors="coerce",
    )

    working_dataframe = dataframe.copy()

    working_dataframe[
        actual_value_column
    ] = numeric_values

    operation = (
        str(operation)
        .strip()
        .lower()
    )

    grouped = working_dataframe.groupby(
        actual_group_column,
        dropna=False,
    )[actual_value_column]

    if operation == "sum":

        result = grouped.sum()

    elif operation in {
        "average",
        "avg",
        "mean",
    }:

        result = grouped.mean()

    elif operation == "min":

        result = grouped.min()

    elif operation == "max":

        result = grouped.max()

    elif operation == "count":

        result = grouped.count()

    else:

        return {
            "success": False,
            "message": (
                f"Unsupported aggregation: "
                f"{operation}"
            ),
        }

    records = []

    for group_value, aggregate_value in (
        result.items()
    ):

        records.append(
            {
                actual_group_column:
                    clean_value(
                        group_value
                    ),
                actual_value_column:
                    clean_value(
                        aggregate_value
                    ),
            }
        )

    return {
        "success": True,
        "group_column":
            actual_group_column,
        "value_column":
            actual_value_column,
        "operation":
            operation,
        "groups":
            records,
    }


# ============================================================
# ROW COUNT
# ============================================================

def count_rows(
    dataframe: pd.DataFrame,
) -> int:
    """
    Return exact number of rows.
    """

    return int(
        len(dataframe)
    )


# ============================================================
# CHECK WHETHER INFORMATION EXISTS
# ============================================================

def has_column(
    dataframe: pd.DataFrame,
    column_name: str,
) -> bool:
    """
    Check whether a requested column exists.
    """

    return (
        find_column(
            dataframe,
            column_name,
        )
        is not None
    )