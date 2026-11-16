"""Regression tests for data-driven relative periods, monthly winners and plan guards."""
import ast
import re
import unittest
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "test_data" / "Vyapar_Style_Accessories_Sales_Report.xlsx"

try:
    from graph.analytics_extra import handle
except Exception:
    handle = None


def _normalise(value):
    if value is None:
        return ""
    value = str(value).strip().lower().replace("_", " ")
    value = re.sub(r"(?<!\d)-|-(?!\d)", " ", value)
    return re.sub(r"\s+", " ", value)


def _load_filter_guard():
    source = (ROOT / "graph" / "dynamic_nodes.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_filter_planner_filters_by_question")
    ns = {"_normalize_text": _normalise, "re": re}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "dynamic_nodes.py", "exec"), ns)
    return ns[fn.name]


class GeneralQueryReliabilityPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if handle is None or not WORKBOOK.exists():
            raise unittest.SkipTest("analytics_extra or test workbook unavailable")
        cls.df = pd.read_excel(WORKBOOK, sheet_name="Sale Invoices")

    def test_month_wise_winner_uses_explicit_gross_amount_and_no_invented_product_filter(self):
        result = handle("Show month-wise product winner by GrossAmount", self.df)
        self.assertIsNotNone(result)
        table = result["result"]["table"]
        self.assertEqual(len(table), 17)
        self.assertEqual(table[-1]["period"], "2026-08")
        self.assertEqual(table[-1]["product"], "Kids Watch")
        self.assertAlmostEqual(table[-1]["value"], 95422.41, places=2)

    def test_three_months_before_latest_uses_dataset_latest_month(self):
        result = handle("What were the sales 3 months before the latest month?", self.df)
        self.assertIsNotNone(result)
        payload = result["result"]
        self.assertEqual(payload["period_label"], "2026-05")
        self.assertAlmostEqual(payload["totals"]["Sales"], 1001896.74, places=2)

    def test_relative_month_supports_multiple_metrics(self):
        result = handle("What were total sales and total profit 3 months before the latest month?", self.df)
        self.assertIsNotNone(result)
        totals = result["result"]["totals"]
        self.assertAlmostEqual(totals["Sales"], 1001896.74, places=2)
        self.assertAlmostEqual(totals["Profit"], 463093.61, places=2)

    def test_planner_drops_unmentioned_categorical_values_but_keeps_grounded_and_date_filters(self):
        guard = _load_filter_guard()
        filters = [
            {"column": "Product", "operator": "=", "value": "Winter Beanie", "type": "categorical"},
            {"column": "Product", "operator": "=", "value": "Kids Watch", "type": "categorical"},
            {"column": "Date", "operator": ">=", "value": "2026-08-01", "type": "date"},
        ]
        kept, rejected = guard(filters, "Show month-wise product winner for Kids Watch")
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["value"], "Winter Beanie")


if __name__ == "__main__":
    unittest.main(verbosity=2)
