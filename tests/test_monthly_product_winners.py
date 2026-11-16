"""Regression tests for monthly product winners in semantic_query_service.py."""
import ast
import re
import unittest
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE = PROJECT_ROOT / "services" / "semantic_query_service.py"
source = SERVICE.read_text(encoding="utf-8-sig")
tree = ast.parse(source)
needed = {"_monthly_product_winners_only", "_product_month_winner_result"}
funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in needed]


def _parse_dates(values):
    # Mirrors the service's general-first date parser for the ISO dates in this test.
    return pd.to_datetime(values, errors="coerce")


namespace = {
    "re": re,
    "pd": pd,
    "_to_dt": _parse_dates,
    "_col": lambda wanted, df: next((c for c in df.columns if c.casefold() == wanted.casefold()), None),
    "_inr": lambda value: f"₹{value:,.2f}",
    "_state": lambda dataset_id, answer, **kwargs: {"dataset_id": dataset_id, "answer": answer, **kwargs},
}
exec(compile(ast.Module(body=funcs, type_ignores=[]), str(SERVICE), "exec"), namespace)


class MonthlyProductWinnerTests(unittest.TestCase):
    def setUp(self):
        # Deliberately make quantity leader different from gross-sales leader.
        self.df = pd.DataFrame([
            {"Product": "Unit King", "Date": "2026-07-01", "GrossAmount": 100, "Qty": 1000, "Profit": 20},
            {"Product": "Sales King", "Date": "2026-07-02", "GrossAmount": 900, "Qty": 10, "Profit": 200},
            {"Product": "Unit King", "Date": "2026-08-01", "GrossAmount": 200, "Qty": 900, "Profit": 30},
            {"Product": "Sales King", "Date": "2026-08-02", "GrossAmount": 800, "Qty": 20, "Profit": 180},
        ])

    def test_monthwise_winner_is_ranked_by_gross_sales(self):
        result = namespace["_monthly_product_winners_only"](self.df, 1, "show month wise product winner")
        self.assertIsNotNone(result)
        self.assertEqual([row["Product"] for row in result["rows"]], ["Sales King", "Sales King"])
        self.assertEqual([row["TotalGrossAmount"] for row in result["rows"]], [900.0, 800.0])
        self.assertEqual([row["Month"] for row in result["rows"]], ["2026-07", "2026-08"])

    def test_gross_amount_followup_metric_is_supported(self):
        result = namespace["_monthly_product_winners_only"](self.df, 1, "show monthly product winner by gross amount")
        self.assertIsNotNone(result)
        self.assertEqual(result["rows"][1]["TotalGrossAmount"], 800.0)

    def test_single_month_question_is_not_captured_by_monthwise_handler(self):
        result = namespace["_monthly_product_winners_only"](self.df, 1, "which product has highest sales in last month")
        self.assertIsNone(result)

    def test_compound_monthwise_report_uses_sales_metric(self):
        result = namespace["_product_month_winner_result"](
            self.df, 1, "overall highest sales product and month wise product winner"
        )
        self.assertIsNotNone(result)
        self.assertEqual([row["Product"] for row in result["rows"]], ["Sales King", "Sales King"])
        self.assertEqual([row["TotalGrossAmount"] for row in result["rows"]], [900.0, 800.0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
