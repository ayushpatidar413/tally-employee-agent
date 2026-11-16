"""Shared query understanding and metric resolution components."""

from .query_models import (
    build_query_plan,
    normalize_query_plan,
    validate_query_plan,
)

from .metric_registry import (
    METRIC_REGISTRY,
    DERIVED_METRICS,
    resolve_metric,
    resolve_derived_metric,
    resolve_multiple_metrics,
)

__all__ = [
    "build_query_plan",
    "normalize_query_plan",
    "validate_query_plan",
    "METRIC_REGISTRY",
    "DERIVED_METRICS",
    "resolve_metric",
    "resolve_derived_metric",
    "resolve_multiple_metrics",
]

from .query_understanding import understand_query, QueryUnderstandingError
