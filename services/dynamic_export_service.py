import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from openpyxl import load_workbook
from openpyxl.chart import (
    BarChart,
    LineChart,
    PieChart,
    Reference,
)
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

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
    title: str = "Business Analysis Report",
    chart: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Export query results as a professional Excel report.

    Workbook structure:
        1. Business Summary
        2. Analysis Report
        3. Chart Data

    The complete supplied result rows are exported.
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

    # --------------------------------------------------------
    # Create workbook
    # --------------------------------------------------------

    with pd.ExcelWriter(
        output_path,
        engine="openpyxl",
    ) as writer:

        # ----------------------------------------------------
        # Sheet 1: Business Summary
        # ----------------------------------------------------

        summary_data = [
            ["REPORT", title],
            ["TOTAL RECORDS", len(dataframe)],
            ["TOTAL COLUMNS", len(dataframe.columns)],
        ]

        summary_dataframe = pd.DataFrame(
            summary_data,
            columns=["Metric", "Value"],
        )

        summary_dataframe.to_excel(
            writer,
            sheet_name="Business Summary",
            index=False,
        )

        # ----------------------------------------------------
        # Sheet 2: Complete Analysis Report
        # ----------------------------------------------------

        dataframe.to_excel(
            writer,
            sheet_name="Analysis Report",
            index=False,
        )

        # ----------------------------------------------------
        # Sheet 3: Chart Data
        #
        # Initially contains the same complete result data.
        # The chart-specific data will be connected later.
        # ----------------------------------------------------

        dataframe.to_excel(
            writer,
            sheet_name="Chart Data",
            index=False,
        )

    # --------------------------------------------------------
    # Open workbook for professional formatting
    # --------------------------------------------------------

    workbook = load_workbook(
        output_path
    )

    # --------------------------------------------------------
    # Common styles
    # --------------------------------------------------------

    header_fill = PatternFill(
        fill_type="solid",
        fgColor="1F2937",
    )

    header_font = Font(
        bold=True,
        color="FFFFFF",
    )

    title_font = Font(
        bold=True,
        size=16,
    )

    label_font = Font(
        bold=True,
    )

    # --------------------------------------------------------
    # Format Summary sheet
    # --------------------------------------------------------

    summary_sheet = workbook[
        "Business Summary"
    ]

    summary_sheet["A1"].font = header_font
    summary_sheet["A1"].fill = header_fill
    summary_sheet["B1"].font = header_font
    summary_sheet["B1"].fill = header_fill

    summary_sheet["A1"] = "REPORT"
    summary_sheet["B1"] = title

    for row in summary_sheet.iter_rows(
        min_row=2,
        max_row=summary_sheet.max_row,
    ):
        if row[0].value:
            row[0].font = label_font

    summary_sheet.column_dimensions[
        "A"
    ].width = 22

    summary_sheet.column_dimensions[
        "B"
    ].width = 55

    # --------------------------------------------------------
    # Format data sheets
    # --------------------------------------------------------

    for sheet_name in [
        "Analysis Report",
        "Chart Data",
    ]:

        sheet = workbook[
            sheet_name
        ]

        # Freeze header
        sheet.freeze_panes = "A2"

        # Enable autofilter
        if sheet.max_row >= 1:
            sheet.auto_filter.ref = (
                sheet.dimensions
            )

        # Header formatting
        for cell in sheet[1]:

            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

        # Header height
        sheet.row_dimensions[
            1
        ].height = 24

        # ----------------------------------------------------
        # Column width
        # ----------------------------------------------------

        for column_cells in sheet.columns:

            column_letter = (
                get_column_letter(
                    column_cells[0].column
                )
            )

            max_length = 0

            for cell in column_cells:

                if cell.value is None:
                    continue

                value_length = len(
                    str(cell.value)
                )

                max_length = max(
                    max_length,
                    value_length,
                )

            sheet.column_dimensions[
                column_letter
            ].width = min(
                max(max_length + 2, 12),
                32,
            )

        # ----------------------------------------------------
        # Number formatting
        # ----------------------------------------------------

        for column_index, column_name in enumerate(
            dataframe.columns,
            start=1,
        ):

            normalized_name = (
                str(column_name)
                .strip()
                .lower()
                .replace(" ", "")
                .replace("_", "")
            )

            for row_index in range(
                2,
                sheet.max_row + 1,
            ):

                cell = sheet.cell(
                    row=row_index,
                    column=column_index,
                )

                # Currency-like columns
                if any(
                    keyword in normalized_name
                    for keyword in [
                        "sales",
                        "amount",
                        "invoicevalue",
                        "invoicetotal",
                        "grossamount",
                        "netamount",
                        "cost",
                        "profit",
                        "discount",
                        "taxablevalue",
                        "cgst",
                        "sgst",
                        "igst",
                        "gst",
                    ]
                ):

                    if isinstance(
                        cell.value,
                        (int, float),
                    ):

                        cell.number_format = (
                            '₹#,##0.00'
                        )

                # Quantity-like columns
                elif any(
                    keyword in normalized_name
                    for keyword in [
                        "qty",
                        "quantity",
                        "count",
                    ]
                ):

                    if isinstance(
                        cell.value,
                        (int, float),
                    ):

                        cell.number_format = (
                            '#,##0.00'
                        )

                # Percentage-like columns
                elif any(
                    keyword in normalized_name
                    for keyword in [
                        "percentage",
                        "percent",
                        "margin",
                    ]
                ):

                    if isinstance(
                        cell.value,
                        (int, float),
                    ):

                        cell.number_format = (
                            '0.00%'
                        )

    # --------------------------------------------------------
    # Add Excel table to Analysis Report
    # --------------------------------------------------------

    analysis_sheet = workbook[
        "Analysis Report"
    ]

    if (
        analysis_sheet.max_row >= 2
        and analysis_sheet.max_column >= 1
    ):

        table_ref = (
            f"A1:{get_column_letter(analysis_sheet.max_column)}"
            f"{analysis_sheet.max_row}"
        )

    # --------------------------------------------------------
    # Add actual Excel chart
    # --------------------------------------------------------

    if (
        chart
        and isinstance(chart, dict)
        and chart.get("enabled")
        and dataframe.shape[0] > 0
    ):

        chart_sheet = workbook[
            "Chart Data"
        ]

        chart_data = chart.get(
            "data",
            [],
        )

        if isinstance(
            chart_data,
            list,
        ) and chart_data:

            chart_dataframe = pd.DataFrame(
                chart_data
            )

            # Clear the existing Chart Data sheet
            # and write the actual chart dataset.
            workbook.remove(
                chart_sheet
            )

            chart_sheet = workbook.create_sheet(
                "Chart Data"
            )

            # Write chart data
            for column_index, column_name in enumerate(
                chart_dataframe.columns,
                start=1,
            ):

                cell = chart_sheet.cell(
                    row=1,
                    column=column_index,
                    value=str(column_name),
                )

                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(
                    horizontal="center"
                )

            for row_index, row in enumerate(
                chart_dataframe.itertuples(
                    index=False,
                    name=None,
                ),
                start=2,
            ):

                for column_index, value in enumerate(
                    row,
                    start=1,
                ):

                    chart_sheet.cell(
                        row=row_index,
                        column=column_index,
                        value=value,
                    )

            chart_sheet.freeze_panes = "A2"

            # ------------------------------------------------
            # Identify category column
            # ------------------------------------------------

            group_by = str(
                chart.get(
                    "group_by",
                    ""
                )
                or chart.get(
                    "group_key",
                    ""
                )
                or ""
            )

            category_column = None

            for column_name in chart_dataframe.columns:

                normalized_column = (
                    str(column_name)
                    .strip()
                    .lower()
                )

                if (
                    normalized_column == group_by.lower()
                    or normalized_column in {
                        "label",
                        "month",
                        "year",
                        "quarter",
                        "date",
                        "product",
                        "partyname",
                        "party name",
                        "customer",
                    }
                ):

                    category_column = column_name
                    break

            if category_column is None:

                category_column = (
                    chart_dataframe.columns[0]
                )

            # ------------------------------------------------
            # Identify numeric series
            # ------------------------------------------------

            numeric_columns = []

            for column_name in chart_dataframe.columns:

                if column_name == category_column:
                    continue

                numeric_series = pd.to_numeric(
                    chart_dataframe[column_name],
                    errors="coerce",
                )

                if numeric_series.notna().any():
                    numeric_columns.append(
                        column_name
                    )

            # ------------------------------------------------
            # Create Chart sheet
            # ------------------------------------------------

            if numeric_columns:

                if "Chart" in workbook.sheetnames:
                    del workbook["Chart"]

                chart_display_sheet = (
                    workbook.create_sheet(
                        "Chart"
                    )
                )

                chart_type = str(
                    chart.get(
                        "type",
                        "bar",
                    )
                    or "bar"
                ).lower()

                # --------------------------------------------
                # Select native Excel chart
                # --------------------------------------------

                if chart_type == "line":
                    excel_chart = LineChart()

                elif chart_type == "pie":
                    excel_chart = PieChart()

                else:
                    excel_chart = BarChart()

                # --------------------------------------------
                # Chart title
                # --------------------------------------------

                excel_chart.title = (
                    chart.get(
                        "title"
                    )
                    or title
                )

                excel_chart.style = 10

                excel_chart.height = 10
                excel_chart.width = 20

                # --------------------------------------------
                # Category references
                # --------------------------------------------

                category_index = (
                    list(
                        chart_dataframe.columns
                    ).index(
                        category_column
                    )
                    + 1
                )

                categories = Reference(
                    chart_sheet,
                    min_col=category_index,
                    min_row=2,
                    max_row=(
                        len(chart_dataframe)
                        + 1
                    ),
                )

                # --------------------------------------------
                # Add numeric series
                # --------------------------------------------

                for numeric_column in numeric_columns:

                    numeric_index = (
                        list(
                            chart_dataframe.columns
                        ).index(
                            numeric_column
                        )
                        + 1
                    )

                    values = Reference(
                        chart_sheet,
                        min_col=numeric_index,
                        min_row=1,
                        max_row=(
                            len(chart_dataframe)
                            + 1
                        ),
                    )

                    excel_chart.add_data(
                        values,
                        titles_from_data=True,
                    )

                excel_chart.set_categories(
                    categories
                )

                # --------------------------------------------
                # Pie chart labels
                # --------------------------------------------

                if chart_type == "pie":

                    excel_chart.dataLabels = (
                        DataLabelList()
                    )

                    excel_chart.dataLabels.showPercent = True
                    excel_chart.dataLabels.showLeaderLines = True

                # --------------------------------------------
                # Axis titles for non-pie charts
                # --------------------------------------------

                if chart_type != "pie":

                    excel_chart.x_axis.title = str(
                        category_column
                    )

                    if len(numeric_columns) == 1:
                        excel_chart.y_axis.title = str(
                            numeric_columns[0]
                        )
                    else:
                        excel_chart.y_axis.title = (
                            "Value"
                        )

                # --------------------------------------------
                # Add chart to Chart sheet
                # --------------------------------------------

                chart_display_sheet["A1"] = (
                    title
                )

                chart_display_sheet["A1"].font = (
                    title_font
                )

                chart_display_sheet.add_chart(
                    excel_chart,
                    "A3",
                )

                chart_display_sheet.column_dimensions[
                    "A"
                ].width = 24
    # --------------------------------------------------------
    # Save final workbook
    # --------------------------------------------------------

    workbook.save(
        output_path
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
    chart: Optional[Dict[str, Any]] = None,
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
            title=title,
            chart=chart,
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