"""Regression tests for the semantic query engine's deterministic period calculations.

Run from the project root after installing requirements:
    python -m unittest tests.test_semantic_periods -v """
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from services import semantic_query_service as sem


class SemanticPeriodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates = [
            Path(os.getenv("VYAPAR_TEST_WORKBOOK", "")),
            Path("Vyapar_Style_Accessories_Sales_Report(7).xlsx"),
            Path("Vyapar_Style_Accessories_Sales_Report.xlsx"),
            Path("uploads/Vyapar_Style_Accessories_Sales_Report.xlsx"),
        ]
        workbook = next((p for p in candidates if str(p) not in {".", ""} and p.is_file()), None)
        if workbook is None and Path("uploads").is_dir():
            workbook = next(iter(Path("uploads").glob("*Vyapar_Style_Accessories_Sales_Report*.xlsx")), None)
        if workbook is None:
            raise unittest.SkipTest("Workbook not found; set VYAPAR_TEST_WORKBOOK to its path")
        cls.workbook = workbook
        cls.raw = pd.read_excel(workbook, sheet_name="Sale Invoices")
        cls.df = sem._clean(cls.raw)
        cls._state_patch = patch.object(
            sem, "_state",
            side_effect=lambda dataset_id, answer, **extra: {
                "dataset_id": dataset_id, "answer": answer, "result": extra
            },
        )
        cls._state_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls._state_patch.stop()

    def period_result(self, query):
        state = sem._monthwise_metric_result(self.df, 70, query)
        self.assertIsNotNone(state, f"Expected deterministic handler to answer: {query}")
        return state["result"]

    def test_requested_six_monthly_metrics_match_raw_excel(self):
        result = self.period_result("show total sales profit igst gst cgst discount month wise")
        rows = result["rows"]
        self.assertEqual(len(rows), 17)
        self.assertEqual(
            list(rows[0]), ["Month", "Sales", "Profit", "IGST", "GST", "CGST", "Discount"]
        )
        self.assertEqual(result["source_rows"], len(self.df))
        raw = self.raw.copy()
        raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
        april = raw[raw["Date"].dt.to_period("M").astype(str) == "2025-04"]
        expected = {
            "Sales": round(april["GrossAmount"].sum(), 2),
            "Profit": round(april["Profit"].sum(), 2),
            "IGST": round(april["IGST"].sum(), 2),
            "GST": round(april["TotalGST"].sum(), 2),
            "CGST": round(april["CGST"].sum(), 2),
            "Discount": round(april["DiscountAmt"].sum(), 2),
        }
        for metric, value in expected.items():
            self.assertAlmostEqual(float(rows[0][metric]), float(value), places=2, msg=metric)

        # Compare every monthly bucket to a separate pandas calculation, not only April.
        raw["MonthKey"] = raw["Date"].dt.to_period("M").astype(str)
        expected_months = raw.groupby("MonthKey").agg(
            Sales=("GrossAmount", "sum"), Profit=("Profit", "sum"),
            IGST=("IGST", "sum"), GST=("TotalGST", "sum"),
            CGST=("CGST", "sum"), Discount=("DiscountAmt", "sum"),
        )
        for row in rows:
            for metric in expected:
                self.assertAlmostEqual(
                    float(row[metric]), round(float(expected_months.loc[row["Month"], metric]), 2),
                    places=2, msg=f"{row['Month']} {metric}",
                )
        for metric, column in (("Sales", "GrossAmount"), ("Profit", "Profit"), ("IGST", "IGST"),
                               ("GST", "TotalGST"), ("CGST", "CGST"), ("Discount", "DiscountAmt")):
            self.assertAlmostEqual(sum(float(row[metric]) for row in rows), round(float(raw[column].sum()), 2), places=2)

    def test_supported_time_groupings(self):
        cases = {
            "sales daywise": ("Day", 518),
            "sales weekwise": ("Week", 75),
            "sales month wise": ("Month", 17),
            "sales quarter wise": ("Quarter", 6),
            "sales year wise": ("Year", 2),
            "sales financial quarter wise": ("Financial Quarter", 6),
            "sales financial year wise": ("Financial Year", 2),
            "sales financial halfyear wise": ("Financial Half-year", 3),
        }
        for query, (key, expected_count) in cases.items():
            with self.subTest(query=query):
                result = self.period_result(query)
                self.assertEqual(len(result["rows"]), expected_count)
                self.assertIn(key, result["rows"][0])
                total = sum(float(row["Sales"]) for row in result["rows"])
                expected_total = round(float(pd.to_numeric(self.raw["GrossAmount"], errors="coerce").sum()), 2)
                self.assertAlmostEqual(total, expected_total, places=2, msg=query)

    def test_rate_and_percentage_are_not_summed(self):
        gst = self.period_result("gst rate month wise")["rows"][0]
        discount = self.period_result("discount percentage month wise")["rows"][0]
        raw = self.raw.copy()
        raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
        april = raw[raw["Date"].dt.to_period("M").astype(str) == "2025-04"]
        self.assertAlmostEqual(gst["GST Rate"], round(april["GST_Rate"].mean(), 2), places=2)
        self.assertAlmostEqual(discount["Discount %"], round(april["DiscountPct"].mean() * 100, 2), places=2)

    def test_average_unit_price_does_not_become_quantity(self):
        rows = self.period_result("sales average unit price month wise")["rows"]
        self.assertIn("Sales", rows[0])
        self.assertIn("Unit Price", rows[0])
        self.assertNotIn("Quantity", rows[0])

    def test_filtered_and_ranking_questions_are_left_for_planner(self):
        self.assertIsNone(sem._monthwise_metric_result(self.df, 70, "July 2026 sales by product"))
        self.assertIsNone(sem._monthwise_metric_result(self.df, 70, "sales month wise for 2025"))


    def test_answer_with_context_handles_six_metrics_without_gemini(self):
        rows = self.raw.to_dict(orient="records")
        dataset = {"id": 70, "original_filename": "Vyapar.xlsx — Sale Invoices", "data_type": "sales",
                   "row_count": len(rows), "columns": list(self.raw.columns)}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}), \
             patch.object(sem, "get_datasets", return_value=[dataset]), \
             patch.object(sem, "get_dataset", return_value=dataset), \
             patch.object(sem, "load_dataset_rows", return_value=rows):
            sem._CACHE.clear()
            out = sem.answer_with_context("show total sales profit igst gst cgst discount month wise", 70, history=[])
        self.assertTrue(out["handled"], out)
        self.assertEqual(out["engine"], "semantic-deterministic")
        result_rows = out["state"]["result"]["rows"]
        self.assertEqual(len(result_rows), 17)
        self.assertEqual(list(result_rows[0]), ["Month", "Sales", "Profit", "IGST", "GST", "CGST", "Discount"])


    def test_planner_retries_when_it_omits_an_explicitly_requested_metric(self):
        base = {
            "kind": "data", "derived": [], "filters": [], "having": [], "group_by": [],
            "time_grain": None, "date_column": None, "add_change": False,
            "order_by": "Sales", "direction": "desc", "limit": None,
            "intent": "total sales and profit", "metric_reasoning": "sum requested columns",
        }
        first = {**base, "metrics": [{"alias": "Sales", "column": "GrossAmount", "agg": "sum"}]}
        second = {**base, "metrics": [
            {"alias": "Sales", "column": "GrossAmount", "agg": "sum"},
            {"alias": "Profit", "column": "Profit", "agg": "sum"},
        ]}
        with patch.object(sem, "_llm", side_effect=[first, second]) as planner:
            plan, clean, result, error = sem._plan_loop(
                "show total sales and total profit", self.df, sem._profile(self.df)
            )
        self.assertEqual(planner.call_count, 2)
        self.assertIsNone(error)
        self.assertEqual([m["column"] for m in clean["metrics"]], ["GrossAmount", "Profit"])
        self.assertIsNotNone(result)

    def test_planner_supports_week_and_financial_period_grains(self):
        plan_base = {
            "kind": "data", "metrics": [{"alias": "Sales", "column": "GrossAmount", "agg": "sum"}],
            "derived": [], "filters": [], "having": [], "group_by": [], "date_column": "Date",
            "add_change": False, "order_by": "period", "direction": "asc", "limit": None,
            "intent": "period test", "metric_reasoning": "sum sales",
        }
        for grain in ("week", "financial_quarter", "financial_year", "halfyear", "financial_halfyear"):
            with self.subTest(grain=grain):
                clean, error = sem._validate({**plan_base, "time_grain": grain}, self.df)
                self.assertIsNone(error)
                self.assertEqual(clean["time_grain"], grain)
                records, *_ = sem._execute(self.df, clean)
                self.assertGreater(len(records), 1)

    def test_dataset_router_does_not_stick_to_incompatible_selected_sheet(self):
        catalog = [
            {"id": 69, "original_filename": "Vyapar.xlsx — Business Summary", "row_count": 19,
             "columns": ["Unnamed: 1", "Unnamed: 2"]},
            {"id": 70, "original_filename": "Vyapar.xlsx — Sale Invoices", "row_count": 8325,
             "columns": list(self.df.columns)},
            {"id": 71, "original_filename": "Vyapar.xlsx — GST Summary", "row_count": 5,
             "columns": ["GST Rate (%)", "Taxable Value", "CGST", "SGST", "IGST", "Total GST", "Invoice Value"]},
            {"id": 74, "original_filename": "Vyapar.xlsx — Category Summary", "row_count": 8,
             "columns": ["Category", "HSN", "GST Rate %", "Qty Sold", "Taxable Value", "GST", "Invoice Value", "Profit", "Margin %"]},
        ]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
            self.assertEqual(sem._route("sales month wise", catalog, 69), 70)
            self.assertEqual(sem._route("show GST Summary sheet", catalog, 70), 71)
            self.assertEqual(sem._route("show Category Summary", catalog, 70), 74)
            self.assertIsNone(sem._route("show attendance status summary", catalog, 70))


if __name__ == "__main__":
    unittest.main(verbosity=2)
