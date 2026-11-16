"""
Central business metric registry.

This module resolves business metric names to actual uploaded
dataset columns. It does not calculate numeric results.

Derived metrics are described separately because their formulas
and denominators must be validated before execution.
"""

import re
from typing import Any, Dict, List, Optional


METRIC_REGISTRY = {
    "sales": {
        "label": "Sales",
        "aliases": [
            "sales",
            "sale",
            "revenue",
            "turnover",
            "gross sales",
            "sales revenue",
            "gross billing",
            "billing",
        ],
        "columns": [
            "GrossAmount",
            "Gross Amount",
            "SalesAmount",
            "Sales Amount",
            "Revenue",
            "Sales",
        ],
        "aggregation": "sum",
        "kind": "column",
        "format": "currency",
    },

    "profit": {
        "label": "Profit",
        "aliases": [
            "profit",
            "profits",
            "net profit",
            "gross profit",
            "earnings",
            "munafa",
        ],
        "columns": [
            "Profit",
            "NetProfit",
            "Net Profit",
            "GrossProfit",
        ],
        "aggregation": "sum",
        "kind": "column",
        "format": "currency",
    },

    "quantity": {
        "label": "Quantity",
        "aliases": [
            "quantity",
            "qty",
            "units",
            "units sold",
            "total units",
            "items sold",
            "pieces sold",
        ],
        "columns": [
            "Qty",
            "Quantity",
            "Units",
            "UnitsSold",
        ],
        "aggregation": "sum",
        "kind": "column",
        "format": "number",
    },

    "taxable_sales": {
        "label": "Taxable Sales",
        "aliases": [
            "taxable sales",
            "taxable amount",
            "taxable value",
            "taxable",
        ],
        "columns": [
            "TaxableAmount",
            "Taxable Amount",
            "TaxableValue",
        ],
        "aggregation": "sum",
        "kind": "column",
        "format": "currency",
    },

    "cost": {
        "label": "Cost",
        "aliases": [
            "cost",
            "total cost",
            "purchase cost",
            "cost amount",
        ],
        "columns": [
            "Cost",
            "TotalCost",
            "Total Cost",
            "PurchaseCost",
        ],
        "aggregation": "sum",
        "kind": "column",
        "format": "currency",
    },

    "gst": {
        "label": "GST",
        "aliases": [
            "gst",
            "total gst",
            "gst amount",
            "tax amount",
        ],
        "columns": [
            "TotalGST",
            "Total GST",
            "GST",
            "GSTAmount",
        ],
        "aggregation": "sum",
        "kind": "column",
        "format": "currency",
    },

    "cgst": {
        "label": "CGST",
        "aliases": ["cgst", "central gst"],
        "columns": ["CGST", "CentralGST"],
        "aggregation": "sum",
        "kind": "column",
        "format": "currency",
    },

    "sgst": {
        "label": "SGST",
        "aliases": ["sgst", "state gst"],
        "columns": ["SGST", "StateGST"],
        "aggregation": "sum",
        "kind": "column",
        "format": "currency",
    },

    "igst": {
        "label": "IGST",
        "aliases": ["igst", "integrated gst"],
        "columns": ["IGST", "IntegratedGST"],
        "aggregation": "sum",
        "kind": "column",
        "format": "currency",
    },

    "discount_amount": {
        "label": "Discount Amount",
        "aliases": [
            "discount amount",
            "total discount",
            "discount value",
            "discount",
        ],
        "columns": [
            "DiscountAmt",
            "Discount Amount",
            "Discount",
        ],
        "aggregation": "sum",
        "kind": "column",
        "format": "currency",
    },

    "discount_percentage": {
        "label": "Discount Percentage",
        "aliases": [
            "discount percentage",
            "discount percent",
            "discount rate",
        ],
        "columns": [
            "DiscountPct",
            "Discount Percentage",
            "DiscountPercent",
        ],
        "aggregation": "average",
        "kind": "column",
        "format": "percentage",
    },

    "invoice_value": {
        "label": "Invoice Value",
        "aliases": [
            "invoice value",
            "invoice total",
            "bill value",
            "bill amount",
            "invoice amount",
            "total invoice value",
        ],
        "columns": [
            "InvoiceTotal",
            "Invoice Total",
            "InvoiceValue",
            "BillAmount",
        ],
        "aggregation": "sum",
        "kind": "column",
        "format": "currency",
    },

    "unit_price": {
        "label": "Unit Price",
        "aliases": [
            "unit price",
            "price per unit",
            "selling price",
            "product price",
        ],
        "columns": [
            "UnitPrice",
            "Unit Price",
            "SellingPrice",
        ],
        "aggregation": "average",
        "kind": "column",
        "format": "currency",
    },
}


DERIVED_METRICS = {
    "profit_margin": {
        "label": "Profit Margin",
        "aliases": [
            "profit margin",
            "margin percentage",
            "profit percentage",
        ],
        "numerator": "profit",
        "denominator_candidates": [
            "taxable_sales",
            "sales",
        ],
        "formula": "(total_profit / denominator) * 100",
        "format": "percentage",
        "requires_denominator_policy": True,
    },

    "average_invoice_value": {
        "label": "Average Invoice Value",
        "aliases": [
            "average invoice value",
            "avg invoice value",
            "average value per invoice",
        ],
        "components": [
            {
                "role": "numerator",
                "metric": "invoice_value",
                "aggregation": "sum",
            },
            {
                "role": "denominator",
                "column_candidates": [
                    "InvoiceNo", "Invoice No", "Invoice Number"
                ],
                "aggregation": "nunique",
            },
        ],
        "formula": "SUM(InvoiceTotal) / COUNT(DISTINCT InvoiceNo)",
        "format": "currency",
        "multiplier": 1,
    },

    "weighted_taxable_price": {
        "label": "Quantity-Weighted Average Taxable Price",
        "aliases": [
            "quantity weighted average taxable price per unit",
            "quantity-weighted average taxable price per unit",
            "weighted average taxable price per unit",
            "weighted taxable price per unit",
        ],
        "components": [
            {
                "role": "numerator",
                "metric": "taxable_sales",
                "aggregation": "sum",
            },
            {
                "role": "denominator",
                "metric": "quantity",
                "aggregation": "sum",
            },
        ],
        "formula": "SUM(TaxableAmount) / SUM(Qty)",
        "format": "currency",
        "multiplier": 1,
    },

    "markup_on_cost": {
        "label": "Markup on Cost",
        "aliases": [
            "markup",
            "markup on cost",
            "profit markup",
            "markup percentage",
        ],
        "numerator": "profit",
        "denominator_candidates": ["cost"],
        "formula": "(total_profit / total_cost) * 100",
        "format": "percentage",
        "requires_denominator_policy": False,
    },
}


def normalize_metric_text(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"[^a-z0-9%]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _column_lookup(available_columns: List[str]) -> Dict[str, str]:
    result = {}

    for column in available_columns or []:
        original = str(column).strip()

        if not original:
            continue

        normalized = normalize_metric_text(original)
        compact = normalized.replace(" ", "")

        result.setdefault(normalized, original)
        result.setdefault(compact, original)

    return result


def _find_actual_column(
    candidates: List[str],
    lookup: Dict[str, str],
) -> Optional[str]:

    for candidate in candidates:
        normalized = normalize_metric_text(candidate)
        compact = normalized.replace(" ", "")

        if normalized in lookup:
            return lookup[normalized]

        if compact in lookup:
            return lookup[compact]

    return None


def get_metric_definition(metric_key: str) -> Optional[Dict[str, Any]]:
    key = normalize_metric_text(metric_key).replace(" ", "")

    for registry_key, definition in METRIC_REGISTRY.items():
        if key == registry_key.replace("_", ""):
            return {
                "key": registry_key,
                **definition,
            }

    return None


def resolve_metric(
    metric_text: str,
    available_columns: List[str],
) -> Optional[Dict[str, Any]]:
    """
    Resolve a metric to an actual uploaded source column.

    Returns None if the metric is unknown or its source column
    is not available. It never substitutes an unrelated column.
    """

    query = normalize_metric_text(metric_text)

    if not query:
        return None

    lookup = _column_lookup(available_columns)

    matches = []

    for key, definition in METRIC_REGISTRY.items():
        aliases = [key.replace("_", " ")] + definition["aliases"]

        for alias in aliases:
            normalized_alias = normalize_metric_text(alias)

            if query == normalized_alias:
                matches.append((len(normalized_alias), key))
                break

    # If the LLM returns an exact uploaded source-column
    # name (for example DiscountPct), map it back to the
    # unique registry metric that owns that column.
    if not matches:
        column_matches = []

        for registry_key, definition in METRIC_REGISTRY.items():
            source_columns = definition.get("columns", [])

            if any(
                query == normalize_metric_text(column)
                for column in source_columns
            ):
                column_matches.append(registry_key)

        # Resolve only an unambiguous exact source-column match.
        if len(column_matches) == 1:
            matches.append((len(query), column_matches[0]))
        else:
            return None

    matches.sort(reverse=True)

    key = matches[0][1]
    definition = METRIC_REGISTRY[key]

    actual_column = _find_actual_column(
        definition["columns"],
        lookup,
    )

    if actual_column is None:
        return {
            "key": key,
            "label": definition["label"],
            "column": None,
            "aggregation": definition["aggregation"],
            "kind": "column",
            "format": definition["format"],
            "status": "DATA_NOT_AVAILABLE",
            "reason": (
                f"No source column found for metric "
                f"'{definition['label']}'"
            ),
        }

    return {
        "key": key,
        "label": definition["label"],
        "column": actual_column,
        "aggregation": definition["aggregation"],
        "kind": "column",
        "format": definition["format"],
        "status": "OK",
        "reason": None,
    }


def resolve_derived_metric(
    metric_text: str,
    available_columns: List[str],
    denominator_policy: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve derived metric formulas without calculating results."""

    query = normalize_metric_text(metric_text)
    matched_key = None

    for key, definition in DERIVED_METRICS.items():
        aliases = [key.replace("_", " ")] + definition["aliases"]

        if any(
            query == normalize_metric_text(alias)
            for alias in aliases
        ):
            matched_key = key
            break

    if matched_key is None:
        return None

    definition = DERIVED_METRICS[matched_key]

    # Component-based derived metrics.
    if definition.get("components"):
        lookup = _column_lookup(available_columns)
        resolved_components = []

        for component in definition["components"]:
            metric_key = component.get("metric")

            if metric_key:
                resolved = resolve_metric(
                    metric_key,
                    available_columns,
                )

                if not resolved or resolved.get("status") != "OK":
                    return {
                        "key": matched_key,
                        "label": definition["label"],
                        "status": "DATA_NOT_AVAILABLE",
                        "kind": "derived",
                        "reason": (
                            f"Required component '{metric_key}' "
                            "is unavailable."
                        ),
                    }

                actual_column = resolved["column"]
                component_key = resolved["key"]
                component_label = resolved["label"]

            else:
                candidates = component.get("column_candidates") or []
                actual_column = _find_actual_column(candidates, lookup)

                if actual_column is None:
                    return {
                        "key": matched_key,
                        "label": definition["label"],
                        "status": "DATA_NOT_AVAILABLE",
                        "kind": "derived",
                        "reason": (
                            "Required source column unavailable: "
                            f"{candidates}"
                        ),
                    }

                component_key = None
                component_label = actual_column

            resolved_components.append({
                "role": component["role"],
                "key": component_key,
                "label": component_label,
                "column": actual_column,
                "aggregation": component["aggregation"],
            })

        return {
            "key": matched_key,
            "label": definition["label"],
            "status": "OK",
            "kind": "derived",
            "components": resolved_components,
            "formula": definition["formula"],
            "multiplier": definition.get("multiplier", 1),
            "format": definition["format"],
        }

    # Preserve existing Profit Margin and Markup behavior.
    numerator = resolve_metric(
        definition["numerator"],
        available_columns,
    )

    if not numerator or numerator.get("status") != "OK":
        return {
            "key": matched_key,
            "status": "DATA_NOT_AVAILABLE",
            "reason": "Required numerator column is unavailable",
        }

    candidates = []

    for candidate_key in definition["denominator_candidates"]:
        resolved = resolve_metric(
            candidate_key,
            available_columns,
        )

        if resolved and resolved.get("status") == "OK":
            candidates.append(resolved)

    selected = None

    if denominator_policy:
        policy = normalize_metric_text(
            denominator_policy
        ).replace(" ", "_")

        for candidate in candidates:
            if candidate["key"] == policy:
                selected = candidate
                break

        if selected is None:
            return {
                "key": matched_key,
                "status": "DATA_NOT_AVAILABLE",
                "reason": "Requested denominator is unavailable",
            }

    elif len(candidates) == 1:
        selected = candidates[0]

    elif len(candidates) > 1:
        return {
            "key": matched_key,
            "status": "NEEDS_CLARIFICATION",
            "reason": (
                "Multiple denominator columns are available. "
                "An explicit denominator policy is required."
            ),
            "available_denominators": [
                item["key"] for item in candidates
            ],
        }

    else:
        return {
            "key": matched_key,
            "status": "DATA_NOT_AVAILABLE",
            "reason": "Required denominator column is unavailable",
        }

    return {
        "key": matched_key,
        "label": definition["label"],
        "status": "OK",
        "kind": "derived",
        "numerator": numerator,
        "denominator": selected,
        "formula": definition["formula"],
        "format": definition["format"],
    }


def resolve_multiple_metrics(
    metric_texts: List[str],
    available_columns: List[str],
) -> Dict[str, Any]:
    resolved = []
    unavailable = []
    seen = set()

    for metric_text in metric_texts or []:
        result = resolve_metric(
            metric_text,
            available_columns,
        )

        if result is None:
            unavailable.append({
                "requested": metric_text,
                "reason": "Metric is not recognized",
            })
            continue

        key = result["key"]

        if key in seen:
            continue

        seen.add(key)

        if result["status"] == "OK":
            resolved.append(result)
        else:
            unavailable.append({
                "requested": metric_text,
                "reason": result["reason"],
            })

    return {
        "metrics": resolved,
        "unavailable": unavailable,
        "status": (
            "OK" if not unavailable
            else "PARTIAL"
        ),
    }
