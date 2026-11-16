import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.table import Table as ExcelTable, TableStyleInfo
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# ============================================================
# PATHS
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BASE_DIR / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# THEME
# ============================================================
NAVY = "163A5F"
INK = "1F2937"
MUTED = "526477"
BAND = "EAF1F8"
INPUT_FILL = "FFF8DC"
PALETTE = ["2563EB", "10B981", "F59E0B", "8B5CF6", "EF4444", "0EA5E9"]
CARD_FILLS = ["E8F1FB", "E8F6EF", "FFF3DF", "F0EAFE"]
TOP_N = 15  # max categories drawn in dashboard charts for non-time data

_SALES = ("sales", "grossamount", "invoicevalue", "invoicetotal", "netamount", "revenue", "amount")
_PROFIT = ("profit", "netprofit", "grossprofit")
_QTY = ("quantity", "qty", "units")
_CURRENCY = ("sales", "amount", "invoicevalue", "invoicetotal", "grossamount", "netamount",
             "cost", "profit", "discount", "taxablevalue", "cgst", "sgst", "igst", "gst", "revenue")
_COUNT = ("qty", "quantity", "count", "units")
_PERCENT = ("percentage", "percent", "margin", "pct", "rate")
_TIME_NAMES = {"period", "month", "date", "year", "yearmonth", "quarter"}
_UPPER_WORDS = {"gst", "cgst", "sgst", "igst", "id"}


def _f(**kw) -> Font:
    return Font(name="Arial", **kw)


def _fill(hex_color: str) -> PatternFill:
    return PatternFill(fill_type="solid", fgColor=hex_color)


# ============================================================
# GENERIC HELPERS
# ============================================================
def _safe_filename(value: str) -> str:
    value = str(value).strip()
    if not value:
        value = "dataset_export"
    value = re.sub(r'[<>:"/\\|?*]', "_", value)
    value = re.sub(r"\s+", "_", value)
    return value[:100]


def _rows_to_dataframe(rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=columns) if columns else pd.DataFrame()
    dataframe = pd.DataFrame(rows)
    if columns:
        existing = [c for c in columns if c in dataframe.columns]
        if existing:
            dataframe = dataframe[existing]
    return dataframe


def _unique_file_path(filename: str) -> Path:
    path = GENERATED_DIR / filename
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = GENERATED_DIR / f"{path.stem}_{counter}{path.suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _norm(name: Any) -> str:
    return str(name).strip().lower().replace(" ", "").replace("_", "")


def _label(name: Any) -> str:
    """PartyName -> Party Name, gross_amount -> Gross Amount, gst -> GST."""
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(name))
    text = re.sub(r"[_\s]+", " ", text).strip()
    words = []
    for word in text.split(" "):
        if word.lower() in _UPPER_WORDS:
            words.append(word.upper())
        elif word.islower():
            words.append(word.capitalize())
        else:
            words.append(word)
    return " ".join(words)


def _pretty_title(title: str) -> str:
    text = re.sub(r"_+", " ", str(title)).strip()
    text = re.sub(r"(?i)\breport(\s+report)+$", "Report", text)
    return text or "Business Analysis Report"


def _is_time_like(name: Any, values: pd.Series) -> bool:
    if _norm(name) in _TIME_NAMES:
        return True
    vals = values.dropna().astype(str)
    return (not vals.empty) and bool(vals.str.match(r"^\d{4}[-/]\d{1,2}([-/]\d{1,2})?").all())


def _is_rate_metric(column: Any) -> bool:
    """Rates and percentages are not additive metrics."""
    name = _norm(column)
    return ("%" in str(column) or any(k in name for k in _PERCENT) or name.endswith("rate") or "taxrate" in name or "gstrate" in name)


def _metric_unit(column: Any) -> str:
    """Coarse unit group used to avoid misleading mixed-scale charts."""
    name = _norm(column)
    if _is_rate_metric(column):
        return "rate"
    if any(k in name for k in _COUNT):
        return "count"
    if any(k in name for k in _CURRENCY):
        return "currency"
    return "numeric"


def _num_format(column: Any, series: pd.Series) -> str:
    name = _norm(column)
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if _is_rate_metric(column):
        return "0.00%" if clean.empty or clean.abs().max() <= 1 else '0.00"%"'
    if any(k in name for k in _CURRENCY):
        return "₹#,##0.00"
    if any(k in name for k in _COUNT):
        return "#,##0" if (clean % 1 == 0).all() else "#,##0.00"
    return "#,##0.00"


def _money(fmt: str, value: float) -> str:
    return f"₹{value:,.2f}" if fmt.startswith("₹") else f"{value:,.2f}"


def _prepare(dataframe: pd.DataFrame):
    """Return (clean dataframe, numeric columns, category column)."""
    data = dataframe.copy()
    numeric: List[Any] = []
    for col in data.columns:
        converted = pd.to_numeric(data[col], errors="coerce")
        non_null = int(data[col].notna().sum())
        if non_null and int(converted.notna().sum()) >= 0.9 * non_null \
                and not _is_time_like(col, data[col].dropna().astype(str)):
            data[col] = converted
            numeric.append(col)
    category = next((c for c in data.columns if c not in numeric), None)
    for col in data.columns:
        if col not in numeric:
            data[col] = data[col].fillna("").astype(str)
    return data, numeric, category


def _metric_order(cols: List[Any]) -> List[Any]:
    def rank(col):
        n = _norm(col)
        groups = (
            _SALES,
            _PROFIT,
            ("discount", "discountamt", "discountamount"),
            ("totalgst", "gst", "cgst", "sgst", "igst"),
            _QTY,
        )
        for i, keys in enumerate(groups):
            if any(k in n for k in keys):
                return i
        return len(groups)
    return sorted(cols, key=rank)


def _merge(ws, r1, c1, r2, c2, value=None, font=None, fill=None, align=None, fmt=None):
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            cell = ws.cell(r, c)
            if fill is not None:
                cell.fill = fill
    anchor = ws.cell(r1, c1)
    if value is not None:
        anchor.value = value
    if font is not None:
        anchor.font = font
    if align is not None:
        anchor.alignment = align
    if fmt:
        anchor.number_format = fmt
    if (r1, c1) != (r2, c2):
        ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)


def _write_table(ws, df: pd.DataFrame, table_name: str, bars: bool = False) -> None:
    """Header + rows + formats + native Excel table (the table provides the filter buttons)."""
    cols = list(df.columns)
    for j, col in enumerate(cols, 1):
        cell = ws.cell(1, j, str(col))
        cell.font = _f(bold=True, color="FFFFFF")
        cell.fill = _fill(INK)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 24
    formats = {}
    for j, col in enumerate(cols, 1):
        if pd.api.types.is_numeric_dtype(df[col]):
            formats[j] = _num_format(col, df[col])
    for i, rec in enumerate(df.itertuples(index=False, name=None), 2):
        for j, value in enumerate(rec, 1):
            if hasattr(value, "item"):
                value = value.item()
            if value is not None and not isinstance(value, str) and pd.isna(value):
                value = None
            cell = ws.cell(i, j, value)
            cell.font = _f()
            if j in formats and value is not None:
                cell.number_format = formats[j]
    for j, col in enumerate(cols, 1):
        longest = max([len(str(col))] + [len(str(v)) for v in df[col].head(500)])
        ws.column_dimensions[get_column_letter(j)].width = min(max(longest + 4, 16), 40)
    ws.freeze_panes = "A2"
    n = len(df)
    if n >= 1 and cols:
        ref = f"A1:{get_column_letter(len(cols))}{n + 1}"
        table = ExcelTable(displayName=table_name, ref=ref)
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleLight9", showFirstColumn=False, showLastColumn=False,
            showRowStripes=True, showColumnStripes=False)
        ws.add_table(table)
        if bars:
            for k, j in enumerate(sorted(formats)):
                letter = get_column_letter(j)
                ws.conditional_formatting.add(
                    f"{letter}2:{letter}{n + 1}",
                    DataBarRule(start_type="num", start_value=0, end_type="max",
                                color=PALETTE[k % len(PALETTE)], showValue=True))


# ============================================================
# CSV EXPORT
# ============================================================
def export_csv(rows: List[Dict[str, Any]], filename: str = "dataset_export.csv",
               columns: Optional[List[str]] = None) -> Dict[str, Any]:
    dataframe = _rows_to_dataframe(rows, columns)
    filename = _safe_filename(filename)
    if not filename.lower().endswith(".csv"):
        filename += ".csv"
    output_path = _unique_file_path(filename)
    dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")
    return {"success": True, "format": "csv", "filename": output_path.name,
            "path": str(output_path), "rows": len(dataframe), "columns": list(dataframe.columns)}


# ============================================================
# XLSX EXPORT
# ============================================================
def export_xlsx(rows: List[Dict[str, Any]], filename: str = "dataset_export.xlsx",
                columns: Optional[List[str]] = None, title: str = "Business Analysis Report",
                chart: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Professional, interactive Excel report.

    Sheets: Dashboard (KPI cards, dropdown lookup, insights, charts),
            Business Summary, Analysis Report (full data table), Chart Data.
    """
    dataframe = _rows_to_dataframe(rows, columns)
    filename = _safe_filename(filename)
    if not filename.lower().endswith(".xlsx"):
        filename += ".xlsx"
    output_path = _unique_file_path(filename)
    title = _pretty_title(title)

    data, numeric_cols, category = _prepare(dataframe)
    metrics = _metric_order(numeric_cols)
    n = len(data)
    time_like = category is not None and _is_time_like(category, data[category])
    cat_label = _label(category) if category is not None else "Record"

    wb = Workbook()
    dash = wb.active
    dash.title = "Dashboard"
    summ = wb.create_sheet("Business Summary")
    ana = wb.create_sheet("Analysis Report")
    cdata = wb.create_sheet("Chart Data")
    dash.sheet_properties.tabColor = NAVY

    # -------- Analysis Report (complete result rows) --------
    _write_table(ana, data, "AnalysisDataTable", bars=True)
    cat_idx = list(data.columns).index(category) + 1 if category is not None else None

    # -------- Business Summary --------
    for c, w in zip("ABCDE", (28, 22, 22, 22, 22)):
        summ.column_dimensions[c].width = w
    summ.sheet_view.showGridLines = False
    _merge(summ, 1, 1, 1, 1, "REPORT", _f(bold=True, color="FFFFFF"), _fill(NAVY))
    _merge(summ, 1, 2, 1, 5, title, _f(bold=True, size=14, color="FFFFFF"), _fill(NAVY),
           Alignment(vertical="center"))
    summ.row_dimensions[1].height = 28
    meta = [("GENERATED ON", datetime.now().strftime("%d %b %Y, %I:%M %p")),
            ("TOTAL RECORDS", n), ("TOTAL COLUMNS", len(data.columns))]
    if time_like and n:
        meta.append(("DATA COVERAGE", f"{data[category].min()}  to  {data[category].max()}"))
    for i, (k, v) in enumerate(meta, 2):
        summ.cell(i, 1, k).font = _f(bold=True, color=INK)
        c = summ.cell(i, 2, v)
        c.font = _f(color=NAVY, bold=True)
        c.alignment = Alignment(horizontal="left")
        if isinstance(v, int):
            c.number_format = "#,##0"
    row = len(meta) + 3
    if metrics:
        _merge(summ, row, 1, row, 5, "BUSINESS PERFORMANCE", _f(bold=True, size=12, color="FFFFFF"), _fill(NAVY))
        row += 1
        for j, h in enumerate(("Metric", "Total / Average", "Average", "Highest", "Lowest"), 1):
            c = summ.cell(row, j, h)
            c.font = _f(bold=True, color="FFFFFF")
            c.fill = _fill(INK)
            c.alignment = Alignment(horizontal="center")
        for m in metrics:
            row += 1
            s = data[m].dropna()
            fmt = _num_format(m, data[m])
            is_rate = _is_rate_metric(m)
            primary_stat = (float(s.mean()) if len(s) else 0) if is_rate else float(s.sum())
            vals = [_label(m), primary_stat, float(s.mean()) if len(s) else 0,
                    float(s.max()) if len(s) else 0, float(s.min()) if len(s) else 0]
            for j, v in enumerate(vals, 1):
                c = summ.cell(row, j, v)
                c.font = _f(bold=(j == 1))
                c.fill = _fill(BAND if row % 2 == 0 else "FFFFFF")
                if j > 1:
                    c.number_format = fmt
        row += 2
    main = metrics[0] if metrics else None
    if main is not None and category is not None and n >= 2 and not _is_rate_metric(main):
        total_main = float(data[main].sum()) or 1.0
        fmt_main = _num_format(main, data[main])
        blocks = [("TOP 5", data.nlargest(min(5, n), main))]
        if n >= 10:
            blocks.append(("BOTTOM 5", data.nsmallest(5, main)))
        for name, part in blocks:
            _merge(summ, row, 1, row, 5, f"{name} BY {_label(main).upper()}",
                   _f(bold=True, size=12, color="FFFFFF"), _fill(NAVY))
            row += 1
            for j, h in enumerate((cat_label, _label(main), "Share of Total"), 1):
                c = summ.cell(row, j, h)
                c.font = _f(bold=True, color="FFFFFF")
                c.fill = _fill(INK)
                c.alignment = Alignment(horizontal="center")
            for _, rec in part.iterrows():
                row += 1
                summ.cell(row, 1, rec[category]).font = _f(bold=True)
                v = summ.cell(row, 2, float(rec[main]))
                v.number_format = fmt_main
                v.font = _f()
                sh = summ.cell(row, 3, float(rec[main]) / total_main)
                sh.number_format = "0.0%"
                sh.font = _f()
                for j in (1, 2, 3):
                    summ.cell(row, j).fill = _fill(BAND if row % 2 == 0 else "FFFFFF")
            row += 2

    # -------- Dashboard --------
    dash.sheet_view.showGridLines = False
    for i in range(1, 17):
        dash.column_dimensions[get_column_letter(i)].width = 12
    _merge(dash, 1, 1, 1, 16, title, _f(bold=True, size=20, color="FFFFFF"), _fill(NAVY),
           Alignment(vertical="center", indent=1))
    dash.row_dimensions[1].height = 38
    sub = f"Business Analytics Dashboard  |  Records: {n:,}"
    if time_like and n:
        sub += f"  |  Period: {data[category].min()} to {data[category].max()}"
    _merge(dash, 2, 1, 2, 16, sub, _f(italic=True, size=10, color=MUTED), None, Alignment(indent=1))

    def _find_kpi_metric(keys):
        for key in keys:
            found = next((m for m in metrics if key in _norm(m)), None)
            if found is not None:
                return found
        return None

    kpi_metrics = []
    for keys in (
        _SALES,
        _PROFIT,
        ("totalgst", "gst", "cgst", "sgst", "igst"),
        _QTY,
    ):
        metric = _find_kpi_metric(keys)
        if metric is not None and metric not in kpi_metrics:
            kpi_metrics.append(metric)

    for metric in metrics:
        if metric not in kpi_metrics and len(kpi_metrics) < 3:
            kpi_metrics.append(metric)

    kpis = [("RECORDS", float(n), "#,##0")]
    for m in kpi_metrics[:3]:
        kpis.append((
            f"{'AVERAGE' if _is_rate_metric(m) else 'TOTAL'} {_label(m).upper()}",
            float(data[m].mean()) if _is_rate_metric(m) else float(data[m].sum()),
            _num_format(m, data[m])
        ))
    if len(kpi_metrics) == 1:
        metric = kpi_metrics[0]
        kpis.append((
            f"AVERAGE {_label(metric).upper()}",
            float(data[metric].mean()),
            _num_format(metric, data[metric])
        ))
        kpis.append((
            f"HIGHEST {_label(metric).upper()}",
            float(data[metric].max()),
            _num_format(metric, data[metric])
        ))
    for i, (lab, val, fmt) in enumerate(kpis[:4]):
        c0 = 1 + i * 4
        _merge(dash, 4, c0, 4, c0 + 2, lab, _f(bold=True, size=9, color=MUTED), _fill(CARD_FILLS[i]),
               Alignment(horizontal="center", vertical="center"))
        _merge(dash, 5, c0, 6, c0 + 2, val, _f(bold=True, size=17, color=NAVY), _fill(CARD_FILLS[i]),
               Alignment(horizontal="center", vertical="center"), fmt)
    dash.row_dimensions[4].height = 23
    dash.row_dimensions[5].height = 24
    dash.row_dimensions[6].height = 24

    # Interactive lookup (dropdown + live formulas)
    if category is not None and metrics and n:
        _merge(dash, 8, 1, 8, 8, "QUICK LOOKUP  (pick from the dropdown)", _f(bold=True, color="FFFFFF"), _fill(NAVY),
               Alignment(indent=1))
        cat_letter = get_column_letter(cat_idx)
        cat_rng = f"'Analysis Report'!${cat_letter}$2:${cat_letter}${n + 1}"
        _merge(dash, 9, 1, 9, 3, f"Select {cat_label}", _f(bold=True, color=INK), _fill(BAND),
               Alignment(indent=1, vertical="center"))
        _merge(dash, 9, 4, 9, 8, data[category].iloc[0], _f(bold=True, color="0000FF"), _fill(INPUT_FILL),
               Alignment(horizontal="left", indent=1, vertical="center"))
        dash.row_dimensions[9].height = 22
        dv = DataValidation(type="list", formula1=f"={cat_rng}", allow_blank=False, showDropDown=False)
        dv.promptTitle = cat_label
        dv.prompt = f"Choose a {cat_label.lower()} to see its numbers"
        dash.add_data_validation(dv)
        dv.add("D9")
        for j, h in enumerate(("Metric", "Value", "Share of total"), 0):
            span = [(1, 3), (4, 6), (7, 8)][j]
            _merge(dash, 10, span[0], 10, span[1], h, _f(bold=True, color="FFFFFF"), _fill(INK),
                   Alignment(horizontal="center"))
        for k, m in enumerate(metrics[:4]):
            r = 11 + k
            letter = get_column_letter(list(data.columns).index(m) + 1)
            met_rng = f"'Analysis Report'!${letter}$2:${letter}${n + 1}"
            band = _fill(BAND if k % 2 == 0 else "FFFFFF")
            _merge(dash, r, 1, r, 3, _label(m), _f(bold=True), band, Alignment(indent=1))
            lookup_formula = (f"=IFERROR(AVERAGEIF({cat_rng},$D$9,{met_rng}),0)" if _is_rate_metric(m)
                              else f"=IFERROR(SUMIF({cat_rng},$D$9,{met_rng}),0)")
            _merge(dash, r, 4, r, 6, lookup_formula, _f(bold=True, color=NAVY), band,
                   Alignment(horizontal="center"), _num_format(m, data[m]))
            share_formula = '=""' if _is_rate_metric(m) else f"=IFERROR(D{r}/SUM({met_rng}),0)"
            _merge(dash, r, 7, r, 8, share_formula, _f(), band,
                   Alignment(horizontal="center"), "0.0%")

    # Insights (static snapshot computed in Python)
    insights: List[tuple] = []
    if main is not None and category is not None and n >= 2:
        fmt = _num_format(main, data[main])
        hi = data.loc[data[main].idxmax()]
        lo = data.loc[data[main].idxmin()]
        insights.append((f"Highest {_label(main)}", f"{hi[category]}  ({_money(fmt, float(hi[main]))})"))
        insights.append((f"Lowest {_label(main)}", f"{lo[category]}  ({_money(fmt, float(lo[main]))})"))
        insights.append((f"Average {_label(main)}" if _is_rate_metric(main) else "Average per record",
                         _money(fmt, float(data[main].mean()))))
        total = float(data[main].sum())
        if time_like and not _is_rate_metric(main):
            ordered = data.sort_values(category)
            if len(ordered) >= 2 and float(ordered[main].iloc[-2]) != 0:
                prev, last = float(ordered[main].iloc[-2]), float(ordered[main].iloc[-1])
                insights.append((f"{ordered[category].iloc[-1]} vs {ordered[category].iloc[-2]}",
                                 f"{(last - prev) / prev * 100:+.1f}%"))
        elif n >= 4 and total and not _is_rate_metric(main):
            top3 = float(data[main].nlargest(3).sum())
            insights.append(("Top 3 contribute", f"{top3 / total * 100:.1f}% of total"))
    if insights:
        _merge(dash, 8, 10, 8, 16, "KEY INSIGHTS", _f(bold=True, color="FFFFFF"), _fill(NAVY), Alignment(indent=1))
        for k, (lab, val) in enumerate(insights[:5]):
            r = 9 + k
            band = _fill(BAND if k % 2 == 0 else "FFFFFF")
            _merge(dash, r, 10, r, 12, lab, _f(bold=True, color=INK), band, Alignment(indent=1))
            _merge(dash, r, 13, r, 16, val, _f(bold=True, color=NAVY), band, Alignment(horizontal="left"))

    # -------- Chart data + charts --------
    chart_df = None
    group_by = ""
    requested_type = "bar"
    supplied_title = ""
    if isinstance(chart, dict) and chart.get("enabled") and chart.get("data"):
        cd = pd.DataFrame(chart["data"])
        if len(cd.columns) >= 2:
            chart_df = cd
            group_by = str(chart.get("group_by") or chart.get("group_key") or "").strip().lower()
            requested_type = str(chart.get("type") or "bar").lower()
            supplied_title = str(chart.get("title") or "").strip()
    if chart_df is None and category is not None and metrics and n >= 2:
        # Include business metrics such as Discount and GST in chart data.
        chart_df = data[[category] + metrics[:6]].copy()
    if requested_type not in {"line", "bar", "pie"}:
        requested_type = "bar"

    chart_cat = None
    chart_metrics: List[Any] = []
    if chart_df is not None:
        names = {"label", "month", "year", "quarter", "date", "period", "product", "partyname",
                 "party name", "customer", "category", "paymentmode"}
        chart_cat = next((c for c in chart_df.columns
                          if str(c).strip().lower() == group_by or str(c).strip().lower() in names),
                         chart_df.columns[0])
        for c in chart_df.columns:
            if c == chart_cat:
                continue
            conv = pd.to_numeric(chart_df[c], errors="coerce")
            if conv.notna().any():
                chart_df[c] = conv
                chart_metrics.append(c)
        # Preserve the metric order returned by the query; do not silently reorder
        # columns in a query-specific chart.
        if not chart_metrics:
            chart_df = None

    if chart_df is None:
        _write_table(cdata, data, "ChartDataTable")
    else:
        chart_df = chart_df[[chart_cat] + chart_metrics].copy()
        chart_df[chart_cat] = chart_df[chart_cat].fillna("").astype(str)
        c_time = _is_time_like(chart_cat, chart_df[chart_cat])
        if c_time:
            chart_df = chart_df.sort_values(chart_cat)
        else:
            chart_df = chart_df.sort_values(chart_metrics[0], ascending=False)
        chart_df = chart_df.reset_index(drop=True)
        # pretty, unique headers (they become legend / axis titles)
        rename, seen = {}, set()
        for c in chart_df.columns:
            lab = _label(c)
            if c == chart_cat and _norm(c) == "label":
                lab = cat_label if category is not None else "Category"  # 'label' is an internal name
            while lab in seen:
                lab += " "
            seen.add(lab)
            rename[c] = lab
        chart_df = chart_df.rename(columns=rename)
        cat_h = rename[chart_cat]
        metric_h = [rename[m] for m in chart_metrics]
        _write_table(cdata, chart_df, "ChartDataTable")

        limit = len(chart_df) if c_time else min(len(chart_df), TOP_N)
        limit = min(limit, 36)
        suffix = f" (Top {limit})" if (not c_time and len(chart_df) > limit) else ""
        m0 = metric_h[0]
        generic = (not supplied_title or "by label" in supplied_title.lower()
                   or supplied_title.lower() == title.lower())
        primary = (f"{m0} Trend by {cat_h}" if requested_type == "line" else f"{m0} by {cat_h}") \
            if generic else supplied_title
        same_unit = len({_metric_unit(m) for m in chart_metrics}) <= 1
        primary_metrics = metric_h[:6] if requested_type == "line" and c_time and same_unit else [m0]
        plans = [(requested_type, primary_metrics, primary + suffix)]
        if c_time:
            other = "bar" if requested_type == "line" else "line"
            other_metrics = metric_h[:6] if other == "line" and same_unit else [m0]
            plans.append((
                other,
                other_metrics,
                f"{m0} Trend by {cat_h}" if other == "line" else f"{m0} by {cat_h}"
            ))
        if len(metric_h) >= 2 and same_unit:
            plans.append(("bar", metric_h[:6], "Metric Comparison" + suffix))
        elif len(metric_h) >= 2:
            # Mixed units (e.g. Sales + Quantity + GST rate) need separate axes/charts.
            for metric_name in metric_h[1:4]:
                plans.append((requested_type, [metric_name], f"{metric_name} by {cat_h}"))
        if requested_type != "pie" and not c_time and 2 <= len(chart_df) <= 8:
            plans.append(("pie", [m0], f"{m0} Share by {cat_h}"))
        uniq, seen_p = [], set()
        for kind, ms, ttl in plans:
            sig = (kind, tuple(ms))
            if sig not in seen_p:
                seen_p.add(sig)
                uniq.append((kind, ms, ttl))

        header = list(chart_df.columns)
        cats = Reference(cdata, min_col=1, min_row=2, max_row=limit + 1)
        for idx, (kind, ms, ttl) in enumerate(uniq[:4]):
            if kind == "line":
                ch = LineChart()
            elif kind == "pie":
                ch = PieChart()
            else:
                ch = BarChart()
                ch.type = "col"
                ch.grouping = "clustered"
                ch.gapWidth = 60
            ch.title = ttl
            ch.height = 7
            ch.width = 15
            ch.display_blanks = "gap"
            for k, m in enumerate(ms):
                col_i = header.index(m) + 1
                ch.add_data(Reference(cdata, min_col=col_i, min_row=1, max_row=limit + 1), titles_from_data=True)
            ch.set_categories(cats)
            if kind == "pie":
                ch.dataLabels = DataLabelList()
                ch.dataLabels.showPercent = True
                ch.dataLabels.showVal = False
                ch.dataLabels.showCatName = False
                ch.dataLabels.showSerName = False
                ch.dataLabels.showLeaderLines = True
                ch.legend.position = "r"
            else:
                for k, s in enumerate(ch.series):
                    color = PALETTE[k % len(PALETTE)]
                    if kind == "line":
                        s.graphicalProperties.line.solidFill = color
                        s.graphicalProperties.line.width = 28000
                        s.smooth = False
                    else:
                        s.graphicalProperties.solidFill = color
                ch.x_axis.title = cat_h
                ch.y_axis.title = ms[0] if len(ms) == 1 else "Value"
                ch.x_axis.delete = False
                ch.y_axis.delete = False
                ch.y_axis.numFmt = (_num_format(ms[0], chart_df[ms[0]]) if len(ms) == 1 and ms[0] in chart_df.columns else "#,##0.00")
                if len(ms) == 1:
                    ch.legend = None
                else:
                    ch.legend.position = "b"
            dash.add_chart(ch, f"{'A' if idx % 2 == 0 else 'I'}{16 + (idx // 2) * 17}")

    # -------- Final workbook settings --------
    dash.page_setup.orientation = "landscape"
    dash.page_setup.fitToWidth = 1
    dash.page_setup.fitToHeight = 0
    dash.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    wb.active = 0
    wb.calculation.fullCalcOnLoad = True
    wb.save(output_path)

    return {"success": True, "format": "xlsx", "filename": output_path.name, "path": str(output_path),
            "rows": len(dataframe), "columns": list(dataframe.columns)}


# ============================================================
# PDF EXPORT
# ============================================================
def export_pdf(rows: List[Dict[str, Any]], filename: str = "dataset_report.pdf",
               columns: Optional[List[str]] = None, title: str = "Dataset Report") -> Dict[str, Any]:
    dataframe = _rows_to_dataframe(rows, columns)
    filename = _safe_filename(filename)
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    output_path = _unique_file_path(filename)
    document = SimpleDocTemplate(str(output_path), pagesize=landscape(A4),
                                 rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    elements = [Paragraph(_pretty_title(title), styles["Title"]), Spacer(1, 12),
                Paragraph(f"Total Records: {len(dataframe)}", styles["Normal"]), Spacer(1, 12)]
    if dataframe.empty:
        elements.append(Paragraph("No records found.", styles["Normal"]))
        document.build(elements)
        return {"success": True, "format": "pdf", "filename": output_path.name,
                "path": str(output_path), "rows": 0, "columns": []}

    display = dataframe.fillna("")
    max_pdf_columns = 12
    if len(display.columns) > max_pdf_columns:
        display = display[list(display.columns)[:max_pdf_columns]]
    headers = [str(c) for c in display.columns]
    table_data = [headers] + [[str(v) for v in row.tolist()] for _, row in display.iterrows()]
    max_pdf_rows = 5000
    if len(table_data) > max_pdf_rows + 1:
        table_data = table_data[: max_pdf_rows + 1]
        elements += [Paragraph(f"PDF contains the first {max_pdf_rows} records. "
                               f"CSV/XLSX exports contain all records.", styles["Normal"]), Spacer(1, 8)]
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    document.build(elements)
    return {"success": True, "format": "pdf", "filename": output_path.name, "path": str(output_path),
            "rows": len(dataframe), "columns": list(dataframe.columns)}


# ============================================================
# GENERIC EXPORT
# ============================================================
def export_rows(rows: List[Dict[str, Any]], file_format: str, filename: str,
                columns: Optional[List[str]] = None, title: str = "Dataset Report",
                chart: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    file_format = str(file_format).strip().lower().replace(".", "")
    if file_format == "csv":
        return export_csv(rows=rows, filename=filename, columns=columns)
    if file_format in {"xlsx", "excel"}:
        return export_xlsx(rows=rows, filename=filename, columns=columns, title=title, chart=chart)
    if file_format == "pdf":
        return export_pdf(rows=rows, filename=filename, columns=columns, title=title)
    return {"success": False, "error": f"Unsupported export format: {file_format}"}