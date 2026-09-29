from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

GENERATED_DIR = BASE_DIR / "generated"

GENERATED_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# HELPERS
# ============================================================

def _safe_filename(value: str) -> str:
    """
    Convert arbitrary text into a safe filename.
    """

    value = str(value).strip()

    if not value:
        value = "dataset_export"

    value = re.sub(
        r"[<>:\"/\\|?*]",
        "_",
        value,
    )

    value = re.sub(
        r"\s+",
        "_",
        value,
    )

    value = value[:100]

    return value


def _rows_to_dataframe(
    rows: List[Dict[str, Any]],
    columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Convert query result rows into a DataFrame.

    The rows can contain arbitrary columns.
    """

    if not rows:
        if columns:
            return pd.DataFrame(
                columns=columns
            )

        return pd.DataFrame()

    dataframe = pd.DataFrame(rows)

    if columns:
        existing_columns = [
            column
            for column in columns
            if column in dataframe.columns
        ]

        if existing_columns:
            dataframe = dataframe[
                existing_columns
            ]

    return dataframe


def _unique_file_path(
    filename: str,
) -> Path:
    """
    Prevent overwriting an existing generated file.
    """

    path = GENERATED_DIR / filename

    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix

    counter = 2

    while True:
        candidate = (
            GENERATED_DIR
            / f"{stem}_{counter}{suffix}"
        )

        if not candidate.exists():
            return candidate

        counter += 1


# ============================================================
# CSV EXPORT
# ============================================================

def export_csv(
    rows: List[Dict[str, Any]],
    filename: str = "dataset_export.csv",
    columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Export rows to CSV.
    """

    dataframe = _rows_to_dataframe(
        rows,
        columns,
    )

    filename = _safe_filename(filename)

    if not filename.lower().endswith(".csv"):
        filename += ".csv"

    output_path = _unique_file_path(
        filename
    )

    dataframe.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    return {
        "success": True,
        "format": "csv",
        "filename": output_path.name,
        "path": str(output_path),
        "rows": len(dataframe),
        "columns": list(dataframe.columns),
    }


# ============================================================
# XLSX EXPORT
# ============================================================

def export_xlsx(
    rows: List[Dict[str, Any]],
    filename: str = "dataset_export.xlsx",
    columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Export rows to Excel XLSX.
    """

    dataframe = _rows_to_dataframe(
        rows,
        columns,
    )

    filename = _safe_filename(filename)

    if not filename.lower().endswith(".xlsx"):
        filename += ".xlsx"

    output_path = _unique_file_path(
        filename
    )

    dataframe.to_excel(
        output_path,
        index=False,
        engine="openpyxl",
    )

    return {
        "success": True,
        "format": "xlsx",
        "filename": output_path.name,
        "path": str(output_path),
        "rows": len(dataframe),
        "columns": list(dataframe.columns),
    }


# ============================================================
# PDF EXPORT
# ============================================================

def export_pdf(
    rows: List[Dict[str, Any]],
    filename: str = "dataset_report.pdf",
    columns: Optional[List[str]] = None,
    title: str = "Dataset Report",
) -> Dict[str, Any]:
    """
    Export rows as a readable PDF table.

    Wide datasets are handled using landscape A4.
    """

    dataframe = _rows_to_dataframe(
        rows,
        columns,
    )

    filename = _safe_filename(filename)

    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    output_path = _unique_file_path(
        filename
    )

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        rightMargin=24,
        leftMargin=24,
        topMargin=24,
        bottomMargin=24,
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    normal_style = styles["Normal"]

    elements = []

    elements.append(
        Paragraph(
            title,
            title_style,
        )
    )

    elements.append(
        Spacer(
            1,
            12,
        )
    )

    elements.append(
        Paragraph(
            f"Total Records: {len(dataframe)}",
            normal_style,
        )
    )

    elements.append(
        Spacer(
            1,
            12,
        )
    )

    if dataframe.empty:
        elements.append(
            Paragraph(
                "No records found.",
                normal_style,
            )
        )

        document.build(elements)

        return {
            "success": True,
            "format": "pdf",
            "filename": output_path.name,
            "path": str(output_path),
            "rows": 0,
            "columns": [],
        }

    # --------------------------------------------------------
    # Convert data to display strings.
    # --------------------------------------------------------

    display_dataframe = dataframe.copy()

    display_dataframe = display_dataframe.fillna("")

    headers = [
        str(column)
        for column in display_dataframe.columns
    ]

    table_data = [headers]

    for _, row in display_dataframe.iterrows():
        table_data.append(
            [
                str(value)
                for value in row.tolist()
            ]
        )

    # --------------------------------------------------------
    # Limit extremely wide tables.
    #
    # We don't remove columns from CSV/XLSX.
    # This only prevents unreadable PDFs.
    # --------------------------------------------------------

    max_pdf_columns = 12

    if len(headers) > max_pdf_columns:
        limited_columns = headers[
            :max_pdf_columns
        ]

        display_dataframe = display_dataframe[
            limited_columns
        ]

        headers = limited_columns

        table_data = [headers]

        for _, row in display_dataframe.iterrows():
            table_data.append(
                [
                    str(value)
                    for value in row.tolist()
                ]
            )

    # --------------------------------------------------------
    # Limit very large PDF row count.
    #
    # CSV/XLSX remain complete.
    # --------------------------------------------------------

    max_pdf_rows = 5000

    if len(table_data) > max_pdf_rows + 1:
        table_data = (
            table_data[: max_pdf_rows + 1]
        )

        elements.append(
            Paragraph(
                f"PDF contains the first "
                f"{max_pdf_rows} records. "
                f"CSV/XLSX exports contain all records.",
                normal_style,
            )
        )

        elements.append(
            Spacer(
                1,
                8,
            )
        )

    table = Table(
        table_data,
        repeatRows=1,
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.lightgrey,
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.black,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    elements.append(table)

    document.build(elements)

    return {
        "success": True,
        "format": "pdf",
        "filename": output_path.name,
        "path": str(output_path),
        "rows": len(dataframe),
        "columns": list(dataframe.columns),
    }


# ============================================================
# GENERIC EXPORT
# ============================================================

def export_rows(
    rows: List[Dict[str, Any]],
    file_format: str,
    filename: str,
    columns: Optional[List[str]] = None,
    title: str = "Dataset Report",
) -> Dict[str, Any]:
    """
    Generic export entry point.
    """

    file_format = (
        str(file_format)
        .strip()
        .lower()
        .replace(".", "")
    )

    if file_format == "csv":
        return export_csv(
            rows=rows,
            filename=filename,
            columns=columns,
        )

    if file_format in {
        "xlsx",
        "excel",
    }:
        return export_xlsx(
            rows=rows,
            filename=filename,
            columns=columns,
        )

    if file_format == "pdf":
        return export_pdf(
            rows=rows,
            filename=filename,
            columns=columns,
            title=title,
        )

    return {
        "success": False,
        "error": (
            f"Unsupported export format: "
            f"{file_format}"
        ),
    }