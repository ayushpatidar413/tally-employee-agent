"""
Dynamic Chart Service
---------------------
Converts dynamic query results into a frontend-friendly chart configuration.
This service does NOT execute database queries.
It only converts already calculated query results into chart data.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize(text: Any) -> str:
    """Normalize text for matching."""
    if text is None:
        return ""
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(text).strip().lower(),
    ).strip()
def _is_numeric(value: Any) -> bool:
    """Return True when a value can safely be treated as numeric."""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return False
        value = (
            value.replace("₹", "")
            .replace(",", "")
            .replace("%", "")
            .strip()
        )
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    return False
def _to_number(value: Any) -> Any:
    """Convert numeric-looking values to int/float."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = (
            value.replace("₹", "")
            .replace(",", "")
            .replace("%", "")
            .strip()
        )
        try:
            number = float(cleaned)
            if number.is_integer():
                return int(number)
            return number
        except (ValueError, TypeError):
            return value
    return value
def _humanize(value: Any) -> str:
    """Convert internal field names into readable labels."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("_", " ")
    text = re.sub(r"(?<!^)([A-Z])", r" 1", text)
    return text.strip().title()
# ---------------------------------------------------------------------------
# Metric detection
# ---------------------------------------------------------------------------
METRIC_ALIASES = {
    "sales": [
        "sales",
        "sale",
        "revenue",
        "turnover",
        "selling amount",
        "sales amount",
        "total sales",
        "total amount",
        "invoicetotal",
        "invoice total",
        "total invoicetotal",
        "total invoice total",
    ],
    "profit": [
        "profit",
        "gross profit",
        "net profit",
        "profit amount",
        "margin",
    ],
    "discount": [
        "discount",
        "discount amount",
        "discountamt",
        "discount amt",
    ],
    "quantity": [
        "quantity",
        "qty",
        "units",
        "unit quantity",
    ],
    "invoice_count": [
        "invoice count",
        "number of invoices",
        "no of invoices",
        "invoice number",
        "invoices",
        "bill count",
    ],
    "gst": [
        "gst",
        "gst amount",
        "total gst",
    ],
    "cgst": [
        "cgst",
        "cgst amount",
    ],
    "sgst": [
        "sgst",
        "sgst amount",
    ],
    "igst": [
        "igst",
        "igst amount",
    ],
}
def detect_metrics(question: str) -> List[str]:
    """
    Detect requested metrics from natural language.
    Example:
        "show sales and profit month wise"
        -> ["sales", "profit"]
    """
    normalized = _normalize(question)
    detected = []
    # Check longer aliases first.
    aliases = []
    for metric, names in METRIC_ALIASES.items():
        for name in names:
            aliases.append((name, metric))
    aliases.sort(key=lambda item: len(item[0]), reverse=True)
    for alias, metric in aliases:
        if alias in normalized:
            if metric not in detected:
                detected.append(metric)
    return detected
# ---------------------------------------------------------------------------
# Group / dimension detection
# ---------------------------------------------------------------------------
GROUP_ALIASES = {
    "day": [
        "day wise",
        "daily",
        "day",
        "date wise",
        "date-wise",
        "daily wise",
    ],
    "month": [
        "month wise",
        "monthly",
        "month",
    ],
    "quarter": [
        "quarter wise",
        "quarterly",
        "quarter",
    ],
    "year": [
        "year wise",
        "yearly",
        "annual",
        "year",
    ],
    "customer": [
        "customer wise",
        "customer-wise",
        "customers wise",
        "customers-wise",
        "by customer",
        "by customers",
        "per customer",
        "per customers",
        "customer",
        "customers",
    ],
    "party": [
        "party wise",
        "party-wise",
        "by party",
        "per party",
    ],
    "supplier": [
        "supplier wise",
        "supplier-wise",
        "by supplier",
        "per supplier",
    ],
    "product": [
        "product",
        "products",
        "product wise",
        "product-wise",
        "products wise",
        "products-wise",
        "by product",
        "by products",
        "per product",
        "per products",
    ],
    "category": [
        "category wise",
        "category-wise",
        "by category",
        "per category",
    ],
    "payment_mode": [
        "payment mode wise",
        "payment-mode wise",
        "by payment mode",
        "payment wise",
    ],
    "state": [
        "state wise",
        "state-wise",
        "by state",
        "per state",
    ],
}
def detect_group_by(question: str) -> Optional[str]:
    """Detect the primary grouping dimension."""
    normalized = _normalize(question)
    # Time dimensions get priority.
    priority = [
        "day",
        "month",
        "quarter",
        "year",
        "customer",
        "party",
        "supplier",
        "product",
        "category",
        "payment_mode",
        "state",
    ]
    for group in priority:
        for alias in GROUP_ALIASES[group]:
            if alias in normalized:
                return group
    return None
# ---------------------------------------------------------------------------
# Chart type detection
# ---------------------------------------------------------------------------
CHART_ALIASES = {
    "bar": [
        "bar chart",
        "bar graph",
        "bar",
        "bars",
    ],
    "line": [
        "line chart",
        "line graph",
        "line",
    ],
    "pie": [
        "pie chart",
        "pie graph",
        "pie",
    ],
    "area": [
        "area chart",
        "area graph",
        "area",
    ],
    "scatter": [
        "scatter chart",
        "scatter graph",
        "scatter",
    ],
    "stacked_bar": [
        "stacked bar",
        "stacked bar chart",
        "stacked",
    ],
}
def detect_requested_chart_type(question: str) -> Optional[str]:
    """Return explicitly requested chart type, if any."""
    normalized = _normalize(question)
    for chart_type, aliases in CHART_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                return chart_type
    return None
# ---------------------------------------------------------------------------
# Automatic chart selection
# ---------------------------------------------------------------------------
def choose_chart_type(
    question: str,
    group_by: Optional[str],
    metric_count: int,
) -> str:
    """
    Choose a sensible default chart.
    Explicit user chart requests always win.
    """
    requested = detect_requested_chart_type(question)
    if requested:
        return requested
    # Time-series data is generally easier to understand as a line.
    if group_by in {
        "day",
        "month",
        "quarter",
        "year",
    }:
        return "line"
    # Multiple metrics grouped by a category work well as bars.
    if metric_count > 1:
        return "bar"
    # Category composition can use a pie chart when there is
    # only one metric.
    if group_by in {
        "category",
        "payment_mode",
        "state",
    }:
        return "bar"
    return "bar"
# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------
def _find_matching_field(
    fields: List[str],
    metric: str,
) -> Optional[str]:
    """
    Find a real result field corresponding to a logical metric.
    The logical metric name does not have to be identical to the
    actual query-result column.
    Examples:
        sales -> Total Invoice Value
        sales -> Sales Amount
        sales -> Revenue
        quantity -> Qty
        discount -> Discount Amt
        profit -> Gross Profit
    """
    if not fields:
        return None
    normalized_fields = {
        str(field): _normalize(str(field))
        for field in fields
    }

    # Prefer the canonical sales amount when the result contains it.
    # This prevents InvoiceTotal from being selected when the query
    # result contains GrossAmount but does not contain InvoiceTotal.
    if metric == "sales":
        sales_field_priority = [
            "grossamount",
            "gross amount",
            "salesamount",
            "sales amount",
            "grosssales",
            "gross sales",
            "sales",
            "revenue",
            "turnover",
            "invoicevalue",
            "invoice value",
            "totalinvoicevalue",
            "total invoice value",
            "invoiceamount",
            "invoice amount",
            "invoicetotal",
            "invoice total",
            "totalamount",
            "total amount",
            "totalvalue",
            "total value",
            "netamount",
            "net amount",
        ]

        for preferred_name in sales_field_priority:
            for field, normalized in normalized_fields.items():
                if normalized == preferred_name:
                    return field
    aliases = METRIC_ALIASES.get(metric, [])
    # ------------------------------------------------------------
    # 1. Exact logical metric match
    # ------------------------------------------------------------
    metric_normalized = _normalize(metric)
    for field, normalized in normalized_fields.items():
        if normalized == metric_normalized:
            return field
    # ------------------------------------------------------------
    # 2. Exact alias match
    # ------------------------------------------------------------
    for alias in aliases:
        alias_normalized = _normalize(alias)
        for field, normalized in normalized_fields.items():
            if normalized == alias_normalized:
                return field
    # ------------------------------------------------------------
    # 3. Semantic metric matching
    #
    # IMPORTANT:
    # All patterns are written using the SAME normalization
    # format as _normalize().
    # ------------------------------------------------------------
    semantic_patterns = {
        "sales": [
            "sales",
            "sale",
            "revenue",
            "turnover",
            "invoice total",
            "total invoice total",
            "total invoicetotal",
            "invoice value",
            "total invoice value",
            "invoice amount",
            "total invoice amount",
            "sales value",
            "sales amount",
            "gross sales",
            "gross amount",
            "net amount",
            "total amount",
            "total value",
        ],
        "profit": [
            "profit",
            "gross profit",
            "net profit",
            "profit amount",
            "profit value",
            "profit margin",
            "margin",
        ],
        "discount": [
            "discount",
            "discount amount",
            "discount value",
            "discount amt",
        ],
        "quantity": [
            "quantity",
            "qty",
            "units",
            "unit",
            "item quantity",
            "total quantity",
            "total qty",
        ],
        "invoice_count": [
            "invoice count",
            "invoices",
            "total invoices",
            "bill count",
            "bills count",
        ],
        "gst": [
            "gst",
            "total gst",
            "gst amount",
            "gst value",
            "total gst amount",
        ],
        "cgst": [
            "cgst",
            "cgst amount",
            "total cgst",
        ],
        "sgst": [
            "sgst",
            "sgst amount",
            "total sgst",
        ],
        "igst": [
            "igst",
            "igst amount",
            "total igst",
        ],
    }
    patterns = [
        _normalize(pattern)
        for pattern in semantic_patterns.get(metric, [])
    ]
    # ------------------------------------------------------------
    # 4. Exact semantic pattern
    # ------------------------------------------------------------
    for pattern in patterns:
        for field, normalized in normalized_fields.items():
            if normalized == pattern:
                return field
    # ------------------------------------------------------------
    # 5. Contains-based semantic matching
    # ------------------------------------------------------------
    for field, normalized in normalized_fields.items():
        if metric == "sales":
            if (
                "sales" in normalized
                or "sale" in normalized
                or "revenue" in normalized
                or "turnover" in normalized
                or "invoice value" in normalized
                or "invoice total" in normalized
                or "total invoicetotal" in normalized
                or "invoice amount" in normalized
                or "total amount" in normalized
                or "total value" in normalized
                or "net amount" in normalized
                or "gross amount" in normalized
            ):
                return field
        elif metric == "profit":
            if "profit" in normalized:
                return field
        elif metric == "discount":
            if "discount" in normalized:
                return field
        elif metric == "quantity":
            if (
                normalized == "quantity"
                or normalized == "qty"
                or normalized == "units"
                or "quantity" in normalized
                or "total qty" in normalized
            ):
                return field
        elif metric == "invoice_count":
            if (
                "invoice count" in normalized
                or "total invoices" in normalized
                or (
                    "invoice" in normalized
                    and "count" in normalized
                )
            ):
                return field
        elif metric == "gst":
            if (
                normalized == "gst"
                or "total gst" in normalized
                or (
                    "gst" in normalized
                    and "rate" not in normalized
                )
            ):
                return field
        elif metric == "cgst":
            if "cgst" in normalized:
                return field
        elif metric == "sgst":
            if "sgst" in normalized:
                return field
        elif metric == "igst":
            if "igst" in normalized:
                return field
    return None
# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
CURRENCY_METRICS = {
    "sales",
    "profit",
    "discount",
    "gst",
    "cgst",
    "sgst",
    "igst",
}
def _metric_format(metric: str) -> Dict[str, Any]:
    """Return frontend formatting information."""
    if metric in CURRENCY_METRICS:
        return {
            "format": "compact",
            "prefix": "₹",
        }
    if metric == "quantity":
        return {
            "format": "integer",
        }
    if metric == "invoice_count":
        return {
            "format": "integer",
        }
    return {
        "format": "raw",
    }
# ---------------------------------------------------------------------------
# Chart data
# ---------------------------------------------------------------------------
def build_chart_data(
    rows: List[Dict[str, Any]],
    x_field: Optional[str],
    metric_fields: Dict[str, Optional[str]],
) -> List[Dict[str, Any]]:
    """
    Convert query rows into chart rows.
    """
    chart_data = []
    if not rows:
        return chart_data
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        chart_row: Dict[str, Any] = {}
        # X-axis
        if x_field:
            x_value = row.get(x_field)
            if x_value is None:
                # Try case-insensitive lookup.
                for key, value in row.items():
                    if _normalize(key) == _normalize(x_field):
                        x_value = value
                        break
            chart_row["label"] = (
                str(x_value)
                if x_value is not None
                else str(index + 1)
            )
        else:
            chart_row["label"] = str(index + 1)
        # Metrics
        for metric, field in metric_fields.items():
            if not field:
                continue
            value = row.get(field)
            if value is None:
                # Case-insensitive fallback.
                for key, candidate in row.items():
                    if _normalize(key) == _normalize(field):
                        value = candidate
                        break
            chart_row[metric] = _to_number(value)
        chart_data.append(chart_row)
    return chart_data
# ---------------------------------------------------------------------------
# Main chart configuration
# ---------------------------------------------------------------------------
def build_chart_config(
    question: str,
    rows: Optional[List[Dict[str, Any]]] = None,
    group_by: Optional[str] = None,
    metrics: Optional[List[str]] = None,
    x_field: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main entry point.
    Converts a question + already calculated query rows
    into a frontend-friendly chart configuration.
    """
    rows = rows or []
    # Detect automatically when not supplied.
    detected_metrics = metrics or detect_metrics(question)
    detected_group = group_by or detect_group_by(question)
    chart_type = choose_chart_type(
        question=question,
        group_by=detected_group,
        metric_count=len(detected_metrics),
    )
    # No data.
    if not rows:
        return {
            "enabled": False,
            "reason": "No chart data available.",
            "type": chart_type,
            "title": "No chart data",
            "description": "The query returned no rows.",
            "metrics": detected_metrics,
            "group_by": detected_group,
            "series": [],
            "data": [],
        }
    fields = list(rows[0].keys())
    # Find x-axis field.
    actual_x_field = x_field
    # Prefer the actual grouped period field when available.
    if not actual_x_field:
        for candidate in ("period", "year", "year_month"):
            for field in fields:
                if _normalize(field) == _normalize(candidate):
                    actual_x_field = field
                    break
            if actual_x_field:
                break
    if not actual_x_field and detected_group:
        group_candidates = {
            "day": [
                "day",
                "date",
                "transaction_date",
                "bill_date",
            ],
            "month": [
                "month",
                "month_name",
                "transaction_month",
                "bill_month",
            ],
            "quarter": [
                "quarter",
                "transaction_quarter",
                "bill_quarter",
            ],
            "year": [
                "year",
                "date",
                "transaction_date",
                "bill_date",
                "invoice_date",
                "transaction_year",
                "bill_year",
                "invoice_year",
            ],
            "customer": [
                "customer",
                "customer_name",
                "party_name",
                "party",
            ],
            "party": [
                "party",
                "party_name",
                "customer",
                "customer_name",
            ],
            "supplier": [
                "supplier",
                "supplier_name",
            ],
            "product": [
                "product",
                "products",
                "product_name",
                "product names",
                "by product",
                "by products",
                "per product",
                "per products",
                "product wise",
                "product-wise",
                "products wise",
                "products-wise",
            ],
            "category": [
                "category",
                "category_name",
            ],
            "payment_mode": [
                "payment_mode",
                "payment mode",
                "payment",
            ],
            "state": [
                "state",
                "state_name",
            ],
        }
        candidates = group_candidates.get(
            detected_group,
            [],
        )
        for candidate in candidates:
            for field in fields:
                if _normalize(field) == _normalize(candidate):
                    actual_x_field = field
                    break
            if actual_x_field:
                break
        # Fallback: choose first non-numeric field.
        if not actual_x_field:
            for field in fields:
                values = [
                    row.get(field)
                    for row in rows[:10]
                ]
                numeric_count = sum(
                    _is_numeric(value)
                    for value in values
                )
                if numeric_count < len(values):
                    actual_x_field = field
                    break
    # Metric field mapping.
    metric_fields: Dict[str, Optional[str]] = {}
    for metric in detected_metrics:
        field = _find_matching_field(
            fields,
            metric,
        )
        # Invoice count fallback:
        if metric == "invoice_count" and not field:
            for candidate in fields:
                normalized = _normalize(candidate)
                if (
                    "invoice" in normalized
                    and "count" in normalized
                ):
                    field = candidate
                    break
        metric_fields[metric] = field
    chart_rows = build_chart_data(
        rows=rows,
        x_field=actual_x_field,
        metric_fields=metric_fields,
    )
    series = []
    for metric in detected_metrics:
        field = metric_fields.get(metric)
        if not field:
            continue
        formatting = _metric_format(metric)
        series.append(
            {
                "key": metric,
                "field": field,
                "label": _humanize(metric),
                **formatting,
            }
        )
    title_metrics = [
        _humanize(metric)
        for metric in detected_metrics
    ]
    title_group = (
        _humanize(detected_group)
        if detected_group
        else ""
    )
    if title_metrics and title_group:
        title = (
            f"{' & '.join(title_metrics)} "
            f"by {title_group}"
        )
    elif title_metrics:
        title = " & ".join(title_metrics)
    else:
        title = "Business Analytics"
    return {
        "enabled": bool(chart_rows and series),
        "type": chart_type,
        "title": title,
        "description": (
            f"{title_group} analysis of "
            f"{', '.join(title_metrics)}."
            if title_group and title_metrics
            else "Dynamic business data visualization."
        ),
        "metrics": detected_metrics,
        "group_by": detected_group,
        "x_field": actual_x_field,
        "series": series,
        "data": chart_rows,
        "row_count": len(chart_rows),
    }
# ---------------------------------------------------------------------------
# Utility for frontend chart switching
# ---------------------------------------------------------------------------
def change_chart_type(
    chart_config: Dict[str, Any],
    chart_type: str,
) -> Dict[str, Any]:
    """
    Change only the chart type.
    Data does not need to be recalculated.
    """
    allowed = {
        "bar",
        "line",
        "pie",
        "area",
        "scatter",
        "stacked_bar",
    }
    if chart_type not in allowed:
        raise ValueError(
            f"Unsupported chart type: {chart_type}"
        )
    updated = dict(chart_config)
    updated["type"] = chart_type
    return updated
