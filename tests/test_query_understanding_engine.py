import json

from services.query_engine.query_understanding import understand_query


class MockResponse:
    def __init__(self, content):
        self.content = content


class MockLLM:
    def __init__(self, plan):
        self.plan = plan
        self.last_prompt = None

    def invoke(self, prompt):
        self.last_prompt = prompt
        return MockResponse(json.dumps(self.plan))


SCHEMA = [
    {"source_column": "Date", "data_type": "date"},
    {"source_column": "Product", "data_type": "text"},
    {"source_column": "PartyName", "data_type": "text"},
    {"source_column": "Category", "data_type": "text"},
    {"source_column": "HSN_Code", "data_type": "text"},
    {"source_column": "GrossAmount", "data_type": "number"},
    {"source_column": "Profit", "data_type": "number"},
    {"source_column": "Qty", "data_type": "number"},
    {"source_column": "Cost", "data_type": "number"},
    {"source_column": "TaxableAmount", "data_type": "number"},
    {"source_column": "DiscountPct", "data_type": "number"},
]


def run_test(name, question, plan, expected_operation):
    llm = MockLLM(plan)

    result = understand_query(
        question=question,
        schema=SCHEMA,
        llm=llm,
        dataset_name="Test Sales Dataset",
    )

    assert result["operation"] == expected_operation, result

    print(f"PASS: {name}")
    print("  Intent:", result.get("operation"))
    print("  Metrics:", result.get("metrics"))
    print("  Status:", result.get("status"))


def test_aggregate():
    run_test(
        "Total sales",
        "What is total sales?",
        {
            "operation": "aggregate",
            "metrics": ["sales"],
            "aggregate_function": "sum",
            "filters": [],
        },
        "aggregate",
    )


def test_multiple_metrics():
    run_test(
        "Multiple metrics",
        "Total sales and total profit",
        {
            "operation": "aggregate",
            "metrics": ["sales", "profit"],
            "aggregate_function": "sum",
            "filters": [],
        },
        "aggregate",
    )


def test_ranking():
    run_test(
        "Product ranking",
        "Which product has highest sales?",
        {
            "operation": "ranking",
            "metrics": ["sales"],
            "aggregate_function": "sum",
            "group_by": "Product",
            "direction": "desc",
            "limit": 1,
            "filters": [],
        },
        "ranking",
    )


def test_comparison():
    run_test(
        "Category comparison",
        "Compare sales of Watches and Bags",
        {
            "operation": "comparison",
            "metrics": ["sales"],
            "aggregate_function": "sum",
            "group_by": "Category",
            "comparison_type": "category",
            "filters": [],
        },
        "comparison",
    )


def test_hsn_comparison():
    run_test(
        "HSN comparison",
        "Compare selected HSN sales with remaining HSN sales",
        {
            "operation": "comparison",
            "metrics": ["sales"],
            "aggregate_function": "sum",
            "group_by": "HSN_Code",
            "comparison_type": "selected_vs_remaining",
            "filters": [],
        },
        "comparison",
    )


def test_followup_context():
    context = {
        "last_entity_type": "HSN",
        "last_entity_value": "6505",
        "last_metric": "sales",
    }

    llm = MockLLM({
        "operation": "comparison",
        "metrics": ["sales"],
        "aggregate_function": "sum",
        "group_by": "HSN_Code",
        "comparison_type": "selected_vs_remaining",
        "filters": [
            {
                "column": "HSN_Code",
                "operator": "=",
                "value": "6505",
            }
        ],
    })

    result = understand_query(
        question="Compare this HSN with remaining HSNs",
        schema=SCHEMA,
        llm=llm,
        conversation_context=context,
    )

    assert result["operation"] == "comparison"
    assert "6505" in llm.last_prompt

    print("PASS: Follow-up context supplied to LLM")


def test_ambiguous_margin():
    llm = MockLLM({
        "operation": "aggregate",
        "metrics": ["profit margin"],
        "aggregate_function": "sum",
        "filters": [],
    })

    result = understand_query(
        question="What is profit margin?",
        schema=SCHEMA,
        llm=llm,
    )

    assert result["status"] == "NEEDS_CLARIFICATION"

    print("PASS: Ambiguous profit margin requires clarification")



def test_discount_percentage_source_column():
    llm = MockLLM({
        "operation": "group_aggregate",
        "metrics": ["discount percentage"],
        "aggregate_function": "average",
        "group_by": "Category",
        "filters": [],
        "needs_clarification": False,
    })

    result = understand_query(
        question="Show average discount percentage by category",
        schema=SCHEMA,
        llm=llm,
    )

    assert result["status"] == "OK", result
    assert result["group_by"] == "Category"
    assert result["resolved_metrics"][0]["column"] == "DiscountPct"
    assert result["resolved_metrics"][0]["aggregation"] == "average"
    assert result["resolved_metrics"][0]["format"] == "percentage"

    print("PASS: Existing discount percentage column resolves directly")



if __name__ == "__main__":
    tests = [
        test_aggregate,
        test_multiple_metrics,
        test_ranking,
        test_comparison,
        test_hsn_comparison,
        test_followup_context,
        test_ambiguous_margin,
    ]

    print("\n===== QUERY UNDERSTANDING TESTS =====\n")

    for test in tests:
        test()

    print("\nALL MOCK TESTS PASSED")
