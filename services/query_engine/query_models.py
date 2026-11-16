"""
Canonical query models and structural validation.

This module does not execute queries or calculate business metrics.
It normalizes query plans into a predictable dictionary structure.
"""

from typing import Any, Dict, List, Optional, Tuple


SUPPORTED_OPERATIONS = {
    "aggregate",
    "group_aggregate",
    "ranking",
    "comparison",
    "filter",
    "projection",
    "lookup",
    "count",
    "search",
}

SUPPORTED_AGGREGATIONS = {
    "sum",
    "average",
    "avg",
    "mean",
    "max",
    "min",
    "median",
    "count",
    None,
}

SUPPORTED_FILTER_OPERATORS = {
    "=",
    "!=",
    ">",
    "<",
    ">=",
    "<=",
    "in",
    "contains",
    "year",
    "month",
    "date",
}

VALID_STATUSES = {
    "OK",
    "DATA_NOT_AVAILABLE",
    "FALLBACK",
    "NEEDS_CLARIFICATION",
}


def _clean_string(value: Any) -> Optional[str]:
    if value is None:
        return None

    value = str(value).strip()
    return value or None


def _normalize_metrics(raw: Any) -> List[str]:
    if raw is None:
        return []

    if isinstance(raw, str):
        values = raw.split(",")
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        return []

    result = []
    seen = set()

    for value in values:
        if value is None:
            continue

        name = str(value).strip()

        if not name:
            continue

        key = name.casefold()

        if key not in seen:
            seen.add(key)
            result.append(name)

    return result


def _normalize_filters(raw: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    filters = []
    errors = []

    if raw is None:
        return filters, errors

    if not isinstance(raw, list):
        return [], ["Filters must be a list"]

    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"Filter {index} must be an object")
            continue

        column = _clean_string(item.get("column"))
        operator = _clean_string(item.get("operator"))

        if not column:
            errors.append(f"Filter {index} has no column")
            continue

        if not operator:
            errors.append(f"Filter {index} has no operator")
            continue

        operator = operator.lower()

        if operator not in SUPPORTED_FILTER_OPERATORS:
            errors.append(
                f"Filter {index} has unsupported operator: {operator}"
            )
            continue

        if "value" not in item:
            errors.append(f"Filter {index} has no value")
            continue

        normalized_filter = {
            "column": column,
            "operator": operator,
            "value": item["value"],
        }

        filter_type = _clean_string(item.get("type"))

        if filter_type and filter_type.lower() == "date":
            normalized_filter["type"] = "date"

        filters.append(normalized_filter)

    return filters, errors


def normalize_query_plan(
    raw_plan: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Normalize an existing planner dictionary.

    Existing additional fields are preserved.
    Invalid fields are reported instead of silently guessed.
    """

    if not isinstance(raw_plan, dict):
        return {}, ["Query plan must be a dictionary"]

    plan = dict(raw_plan)
    errors = []

    status = str(plan.get("status") or "FALLBACK").strip().upper()

    if status not in VALID_STATUSES:
        errors.append(f"Unsupported plan status: {status}")
        status = "FALLBACK"

    operation = _clean_string(plan.get("operation"))

    if operation:
        operation = operation.lower()

        if operation not in SUPPORTED_OPERATIONS:
            errors.append(f"Unsupported operation: {operation}")
            operation = None

    aggregate_function = _clean_string(
        plan.get("aggregate_function")
    )

    if aggregate_function:
        aggregate_function = aggregate_function.lower()

        if aggregate_function not in SUPPORTED_AGGREGATIONS:
            errors.append(
                f"Unsupported aggregation: {aggregate_function}"
            )
            aggregate_function = None

    metrics = _normalize_metrics(plan.get("metrics"))

    if not metrics and plan.get("metric"):
        metrics = _normalize_metrics(plan.get("metric"))

    filters, filter_errors = _normalize_filters(
        plan.get("filters")
    )

    errors.extend(filter_errors)

    limit = plan.get("limit")

    if limit is not None:
        try:
            limit = int(limit)

            if limit < 1:
                raise ValueError

        except (TypeError, ValueError):
            errors.append("Limit must be a positive integer")
            limit = None

    direction = _clean_string(plan.get("direction"))

    if direction:
        direction = direction.lower()

        if direction not in {"asc", "desc"}:
            errors.append("Direction must be asc or desc")
            direction = None

    raw_group_by = plan.get("group_by")

    if isinstance(raw_group_by, (list, tuple)):
        if len(raw_group_by) == 1:
            group_by_value = _clean_string(raw_group_by[0])
        elif len(raw_group_by) == 0:
            group_by_value = None
        else:
            errors.append(
                "Multiple group_by columns are not supported"
            )
            group_by_value = None
    else:
        group_by_value = _clean_string(raw_group_by)

    normalized = {
        **plan,
        "status": status,
        "operation": operation,
        "metric": _clean_string(plan.get("metric")),
        "metrics": metrics,
        "aggregate_function": aggregate_function,
        "aggregate_column": _clean_string(
            plan.get("aggregate_column")
        ),
        "group_by": group_by_value,
        "filters": filters,
        "time": plan.get("time"),
        "limit": limit,
        "direction": direction,
        "canonical_query": str(
            plan.get("canonical_query") or ""
        ).strip(),
        "reason": str(plan.get("reason") or "").strip(),
    }

    return normalized, errors


def validate_query_plan(
    plan: Dict[str, Any],
    available_columns: Optional[List[str]] = None,
) -> List[str]:
    """
    Validate references against actual uploaded dataset columns.

    This function does not invent or replace missing columns.
    """

    errors = []

    if not isinstance(plan, dict):
        return ["Plan must be a dictionary"]

    columns = {
        str(column).strip().casefold(): str(column).strip()
        for column in (available_columns or [])
        if str(column).strip()
    }

    if available_columns is not None:
        references = []

        for key in ("aggregate_column", "group_by"):
            value = plan.get(key)

            if value:
                references.append((key, value))

        for item in plan.get("filters") or []:
            if isinstance(item, dict) and item.get("column"):
                references.append(("filter column", item["column"]))

        # Validate explicitly requested output columns.
        requested_columns = plan.get("requested_columns") or []

        if not isinstance(requested_columns, (list, tuple)):
            errors.append("requested_columns must be a list")
            requested_columns = []

        for item in requested_columns:
            if isinstance(item, dict):
                value = (
                    item.get("source_column")
                    or item.get("column")
                    or item.get("name")
                )
            else:
                value = item

            if value:
                references.append(("requested column", value))
            else:
                errors.append(
                    "Requested column has no valid column name"
                )

        # Validate actual source columns resolved for metrics.
        resolved_metrics = plan.get("resolved_metrics") or []

        if not isinstance(resolved_metrics, (list, tuple)):
            errors.append("resolved_metrics must be a list")
            resolved_metrics = []

        for index, metric in enumerate(resolved_metrics):
            if not isinstance(metric, dict):
                errors.append(
                    f"Resolved metric {index} must be an object"
                )
                continue

            kind = str(metric.get("kind") or "").strip().lower()

            if kind == "column":
                value = metric.get("column")

                if value:
                    references.append(("metric source column", value))
                else:
                    errors.append(
                        f"Resolved metric {index} has no source column"
                    )

            elif kind == "derived":
                components = metric.get("components")

                if components is not None:
                    if not isinstance(components, (list, tuple)) or not components:
                        errors.append(
                            f"Derived metric {index} has invalid components"
                        )
                        continue

                    supported_component_aggregations = {
                        "sum", "average", "avg", "mean",
                        "max", "min", "median", "count", "nunique",
                    }

                    for component_index, component in enumerate(components):
                        if not isinstance(component, dict):
                            errors.append(
                                f"Derived metric {index} component "
                                f"{component_index} must be an object"
                            )
                            continue

                        value = component.get("column")
                        aggregation = str(
                            component.get("aggregation") or ""
                        ).strip().lower()

                        if value:
                            references.append(
                                (
                                    f"derived metric component "
                                    f"{component_index} column",
                                    value,
                                )
                            )
                        else:
                            errors.append(
                                f"Derived metric {index} component "
                                f"{component_index} has no source column"
                            )

                        if aggregation not in supported_component_aggregations:
                            errors.append(
                                f"Derived metric {index} component "
                                f"{component_index} has unsupported "
                                f"aggregation: {aggregation}"
                            )

                else:
                    # Backward compatibility for legacy derived metrics.
                    for source_name in ("numerator", "denominator"):
                        source = metric.get(source_name)

                        if isinstance(source, dict):
                            value = source.get("column")
                        elif isinstance(source, str):
                            value = source
                        else:
                            value = None

                        if value:
                            references.append(
                                (f"derived metric {source_name} column", value)
                            )
                        else:
                            errors.append(
                                f"Derived metric {index} has no "
                                f"{source_name} source column"
                            )

        for key, value in references:
            if str(value).strip().casefold() not in columns:
                errors.append(
                    f"{key} does not exist in dataset: {value}"
                )

    operation = plan.get("operation")

    if operation == "group_aggregate" and not plan.get("group_by"):
        errors.append("Group aggregation requires group_by")

    if operation in {"aggregate", "group_aggregate"}:
        if not plan.get("aggregate_column") and not plan.get("metrics"):
            errors.append(
                "Aggregation requires an aggregate column or metrics"
            )

    return errors


def build_query_plan(
    operation: str,
    metrics: Optional[List[str]] = None,
    aggregate_function: Optional[str] = None,
    aggregate_column: Optional[str] = None,
    group_by: Optional[str] = None,
    filters: Optional[List[Dict[str, Any]]] = None,
    canonical_query: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    """
    Build a standard query plan.

    Extra fields are preserved for compatibility with the existing engine.
    """

    raw = {
        **extra,
        "status": extra.pop("status", "OK"),
        "operation": operation,
        "metrics": metrics or [],
        "aggregate_function": aggregate_function,
        "aggregate_column": aggregate_column,
        "group_by": group_by,
        "filters": filters or [],
        "canonical_query": canonical_query,
    }

    normalized, errors = normalize_query_plan(raw)

    if errors:
        raise ValueError("; ".join(errors))

    return normalized

