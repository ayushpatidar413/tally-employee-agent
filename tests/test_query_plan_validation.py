from services.query_engine.query_models import (
    normalize_query_plan,
    validate_query_plan,
)
from services.query_engine.query_understanding import understand_query


SCHEMA = [
    "Date",
    "Product",
    "PartyName",
    "Category",
    "HSN_Code",
    "GrossAmount",
    "Profit",
    "Qty",
    "Cost",
    "TaxableAmount",
]


def check(name, condition):
    assert condition, f"FAILED: {name}"
    print(f"PASS: {name}")


def test_invalid_aggregation():
    plan, errors = normalize_query_plan({
        "status": "OK",
        "operation": "aggregate",
        "metrics": ["sales"],
        "aggregate_function": "total_magic",
        "filters": [],
    })

    check(
        "Unsupported aggregation detected",
        any("Unsupported aggregation" in e for e in errors),
    )


def test_invalid_filter_operator():
    plan, errors = normalize_query_plan({
        "status": "OK",
        "operation": "filter",
        "filters": [{
            "column": "Product",
            "operator": "starts_with_magic",
            "value": "Watch",
        }],
    })

    check(
        "Unsupported filter operator detected",
        any("unsupported operator" in e for e in errors),
    )


def test_missing_filter_value():
    plan, errors = normalize_query_plan({
        "status": "OK",
        "operation": "filter",
        "filters": [{
            "column": "Product",
            "operator": "=",
        }],
    })

    check(
        "Missing filter value detected",
        any("no value" in e.lower() for e in errors),
    )


def test_invalid_aggregate_column():
    plan, errors = normalize_query_plan({
        "status": "OK",
        "operation": "aggregate",
        "aggregate_column": "FakeSalesColumn",
        "aggregate_function": "sum",
        "filters": [],
    })

    validation_errors = validate_query_plan(plan, SCHEMA)

    check(
        "Invalid aggregate column detected",
        any("FakeSalesColumn" in e for e in validation_errors),
    )


def test_invalid_group_column():
    plan, errors = normalize_query_plan({
        "status": "OK",
        "operation": "group_aggregate",
        "metrics": ["sales"],
        "aggregate_function": "sum",
        "group_by": "FakeCategory",
        "filters": [],
    })

    validation_errors = validate_query_plan(plan, SCHEMA)

    check(
        "Invalid group column detected",
        any("FakeCategory" in e for e in validation_errors),
    )


def test_invalid_filter_column():
    plan, errors = normalize_query_plan({
        "status": "OK",
        "operation": "filter",
        "filters": [{
            "column": "FakeProduct",
            "operator": "=",
            "value": "Watch",
        }],
    })

    validation_errors = validate_query_plan(plan, SCHEMA)

    check(
        "Invalid filter column detected",
        any("FakeProduct" in e for e in validation_errors),
    )


def test_valid_plan():
    plan, errors = normalize_query_plan({
        "status": "OK",
        "operation": "group_aggregate",
        "metrics": ["sales"],
        "aggregate_function": "sum",
        "group_by": "Category",
        "filters": [{
            "column": "Product",
            "operator": "contains",
            "value": "Watch",
        }],
    })

    validation_errors = validate_query_plan(plan, SCHEMA)

    check("Valid plan has no normalization errors", not errors)
    check("Valid plan has no schema errors", not validation_errors)


class MockResponse:
    def __init__(self, content):
        self.content = content


class MockLLM:
    def invoke(self, prompt):
        import json

        return MockResponse(json.dumps({
            "status": "OK",
            "operation": "group_aggregate",
            "metrics": ["sales"],
            "aggregate_function": "sum",
            "group_by": "FakeCategory",
            "filters": [],
        }))


def test_understand_query_rejects_invalid_group_column():
    result = understand_query(
        question="Show sales by category",
        schema=[
            {"source_column": c, "data_type": "text"}
            for c in SCHEMA
        ],
        llm=MockLLM(),
    )

    errors = result.get("validation_errors", [])

    check(
        "understand_query rejects invalid group_by",
        result.get("status") == "NEEDS_CLARIFICATION"
        and result.get("group_by") == "FakeCategory"
        and any("FakeCategory" in str(error) for error in errors),
    )

    print("  CONFIRMED: invalid group_by rejected by schema validation")


def test_invalid_requested_column():
    errors = validate_query_plan(
        {
            "operation": "projection",
            "requested_columns": ["FakeProduct"],
        },
        SCHEMA,
    )

    check(
        "Invalid requested column detected",
        any("FakeProduct" in e for e in errors),
    )


def test_valid_requested_column():
    errors = validate_query_plan(
        {
            "operation": "projection",
            "requested_columns": ["Product", "Date"],
        },
        SCHEMA,
    )

    check(
        "Valid requested columns accepted",
        not errors,
    )


def test_invalid_direct_metric_source():
    errors = validate_query_plan(
        {
            "operation": "aggregate",
            "metrics": ["sales"],
            "resolved_metrics": [
                {
                    "key": "sales",
                    "kind": "column",
                    "column": "FakeGrossAmount",
                }
            ],
        },
        SCHEMA,
    )

    check(
        "Invalid direct metric source detected",
        any("FakeGrossAmount" in e for e in errors),
    )


def test_valid_direct_metric_source():
    errors = validate_query_plan(
        {
            "operation": "aggregate",
            "metrics": ["sales"],
            "resolved_metrics": [
                {
                    "key": "sales",
                    "kind": "column",
                    "column": "GrossAmount",
                }
            ],
        },
        SCHEMA,
    )

    check(
        "Valid direct metric source accepted",
        not errors,
    )


def test_invalid_derived_metric_source():
    errors = validate_query_plan(
        {
            "operation": "aggregate",
            "metrics": ["profit_margin"],
            "resolved_metrics": [
                {
                    "key": "profit_margin",
                    "kind": "derived",
                    "numerator": {
                        "column": "FakeProfit",
                    },
                    "denominator": {
                        "column": "GrossAmount",
                    },
                }
            ],
        },
        SCHEMA,
    )

    check(
        "Invalid derived metric source detected",
        any("FakeProfit" in e for e in errors),
    )


def test_valid_derived_metric_sources():
    errors = validate_query_plan(
        {
            "operation": "aggregate",
            "metrics": ["profit_margin"],
            "resolved_metrics": [
                {
                    "key": "profit_margin",
                    "kind": "derived",
                    "numerator": {
                        "column": "Profit",
                    },
                    "denominator": {
                        "column": "GrossAmount",
                    },
                }
            ],
        },
        SCHEMA,
    )

    check(
        "Valid derived metric sources accepted",
        not errors,
    )


class ConfigurableMockLLM:
    def __init__(self, payload):
        self.payload = payload

    def invoke(self, prompt):
        import json
        return MockResponse(json.dumps(self.payload))


def test_understand_query_rejects_invalid_requested_column():
    llm = ConfigurableMockLLM({
        "status": "OK",
        "operation": "projection",
        "metrics": [],
        "requested_columns": ["FakeProduct"],
        "filters": [],
    })

    result = understand_query(
        question="Show fake product column",
        schema=[
            {"source_column": c, "data_type": "text"}
            for c in SCHEMA
        ],
        llm=llm,
    )

    errors = result.get("validation_errors", [])

    check(
        "understand_query rejects invalid requested column",
        result.get("status") == "NEEDS_CLARIFICATION"
        and any("FakeProduct" in str(e) for e in errors),
    )


def test_understand_query_accepts_valid_requested_columns():
    llm = ConfigurableMockLLM({
        "status": "OK",
        "operation": "projection",
        "metrics": [],
        "requested_columns": ["Product", "Date"],
        "filters": [],
    })

    result = understand_query(
        question="Show product and date",
        schema=[
            {"source_column": c, "data_type": "text"}
            for c in SCHEMA
        ],
        llm=llm,
    )

    check(
        "understand_query accepts valid requested columns",
        result.get("status") == "OK"
        and not result.get("validation_errors"),
    )


def test_understand_query_resolves_direct_metric_source():
    llm = ConfigurableMockLLM({
        "status": "OK",
        "operation": "aggregate",
        "metrics": ["sales"],
        "aggregate_function": "sum",
        "filters": [],
    })

    result = understand_query(
        question="What are total sales?",
        schema=[
            {"source_column": c, "data_type": "number"}
            for c in SCHEMA
        ],
        llm=llm,
    )

    resolved = result.get("resolved_metrics", [])

    check(
        "understand_query resolves sales to actual source column",
        result.get("status") == "OK"
        and len(resolved) == 1
        and resolved[0].get("column") == "GrossAmount"
        and not result.get("validation_errors"),
    )


def test_understand_query_resolves_derived_metric_sources():
    llm = ConfigurableMockLLM({
        "status": "OK",
        "operation": "aggregate",
        "metrics": ["profit margin"],
        "aggregate_function": "average",
        "filters": [],
    })

    result = understand_query(
        question="What is the profit margin?",
        schema=[
            {"source_column": c, "data_type": "number"}
            for c in SCHEMA
        ],
        llm=llm,
        denominator_policy="sales",
    )

    resolved = result.get("resolved_metrics", [])

    metric = resolved[0] if resolved else {}
    numerator = metric.get("numerator") or {}
    denominator = metric.get("denominator") or {}

    check(
        "understand_query resolves derived metric source columns",
        result.get("status") == "OK"
        and metric.get("kind") == "derived"
        and numerator.get("column") == "Profit"
        and denominator.get("column") == "GrossAmount"
        and not result.get("validation_errors"),
    )
if __name__ == "__main__":
    print("\n===== QUERY PLAN VALIDATION TESTS =====\n")

    tests = [
        test_invalid_aggregation,
        test_invalid_filter_operator,
        test_missing_filter_value,
        test_invalid_aggregate_column,
        test_invalid_group_column,
        test_invalid_filter_column,
        test_valid_plan,
        test_understand_query_rejects_invalid_group_column,
        test_invalid_requested_column,
        test_valid_requested_column,
        test_invalid_direct_metric_source,
        test_valid_direct_metric_source,
        test_invalid_derived_metric_source,
        test_valid_derived_metric_sources,
        test_understand_query_rejects_invalid_requested_column,
        test_understand_query_accepts_valid_requested_columns,
        test_understand_query_resolves_direct_metric_source,
        test_understand_query_resolves_derived_metric_sources,
    ]

    for test in tests:
        test()

    print("\nALL VALIDATION AUDIT TESTS PASSED")




