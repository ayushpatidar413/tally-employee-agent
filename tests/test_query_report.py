"""Checks that the generated Excel report preserves query result columns and metric semantics."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from services import dynamic_export_service as export_service


class QueryReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates = [
            Path(os.getenv("VYAPAR_TEST_WORKBOOK", "")),
            Path("Vyapar_Style_Accessories_Sales_Report(7).xlsx"),
            Path("Vyapar_Style_Accessories_Sales_Report.xlsx"),
        ]
        cls.workbook = next((p for p in candidates if str(p) not in {".", ""} and p.is_file()), None)
        if cls.workbook is None:
            raise unittest.SkipTest("Workbook not found; set VYAPAR_TEST_WORKBOOK")
        cls.raw = pd.read_excel(cls.workbook, sheet_name="Sale Invoices")

    def monthly_rows(self):
        raw = self.raw.copy()
        raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce", dayfirst=True)
        raw = raw.dropna(subset=["Date"])
        raw["Month"] = raw["Date"].dt.to_period("M").astype(str)
        out = raw.groupby("Month", sort=True).agg(
            Sales=("GrossAmount", "sum"), Profit=("Profit", "sum"),
            IGST=("IGST", "sum"), GST=("TotalGST", "sum"),
            CGST=("CGST", "sum"), Discount=("DiscountAmt", "sum"),
        ).reset_index()
        for col in out.columns[1:]:
            out[col] = out[col].round(2)
        return out.to_dict(orient="records")

    def test_query_report_preserves_requested_metrics_and_query_title(self):
        rows = self.monthly_rows()
        expected_columns = ["Month", "Sales", "Profit", "IGST", "GST", "CGST", "Discount"]
        self.assertEqual(list(rows[0]), expected_columns)
        with tempfile.TemporaryDirectory() as tmp:
            old_dir = export_service.GENERATED_DIR
            export_service.GENERATED_DIR = Path(tmp)
            try:
                chart = {
                    "enabled": True, "type": "line", "x": "Month", "group_by": "Month",
                    "series": expected_columns[1:], "data": rows,
                    "title": "Month-wise Sales, Profit, IGST, GST, CGST and Discount",
                }
                result = export_service.export_rows(
                    rows=rows, file_format="xlsx", filename="query_report.xlsx",
                    title="Vyapar — Query: show total sales profit igst gst cgst discount month wise",
                    chart=chart,
                )
                self.assertTrue(result["success"], result)
                wb = load_workbook(result["path"], data_only=False)
                ws = wb["Analysis Report"]
                self.assertEqual([ws.cell(1, c).value for c in range(1, len(expected_columns) + 1)], expected_columns)
                self.assertEqual(ws.max_row, len(rows) + 1)
                self.assertAlmostEqual(float(ws["B2"].value), float(rows[0]["Sales"]), places=2)
                self.assertIn("Query: show total sales profit igst gst cgst discount month wise", str(wb["Dashboard"]["A1"].value))
                self.assertIn("Sales", [wb["Chart Data"].cell(1, c).value for c in range(1, wb["Chart Data"].max_column + 1)])
                wb.close()
            finally:
                export_service.GENERATED_DIR = old_dir

    def test_rate_columns_use_average_not_sum_in_business_summary(self):
        rows = [
            {"Month": "2025-04", "GST Rate": 5.0, "Discount %": 2.0},
            {"Month": "2025-05", "GST Rate": 18.0, "Discount %": 4.0},
            {"Month": "2025-06", "GST Rate": 12.0, "Discount %": 6.0},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            old_dir = export_service.GENERATED_DIR
            export_service.GENERATED_DIR = Path(tmp)
            try:
                result = export_service.export_rows(
                    rows=rows, file_format="xlsx", filename="rate_report.xlsx",
                    title="Query: GST rate and discount percentage month wise",
                    chart={"enabled": True, "type": "line", "x": "Month", "group_by": "Month",
                           "series": ["GST Rate", "Discount %"], "data": rows},
                )
                self.assertTrue(result["success"], result)
                wb = load_workbook(result["path"], data_only=False)
                ws = wb["Business Summary"]
                headers = [ws.cell(8, c).value for c in range(1, 6)]
                self.assertEqual(headers, ["Metric", "Total / Average", "Average", "Highest", "Lowest"])
                values = {}
                for r in range(9, ws.max_row + 1):
                    name = ws.cell(r, 1).value
                    if name in {"GST Rate", "Discount %"}:
                        values[name] = ws.cell(r, 2).value
                self.assertAlmostEqual(values["GST Rate"], 35 / 3, places=2)
                self.assertAlmostEqual(values["Discount %"], 4.0, places=2)
                self.assertFalse(any(str(ws.cell(r, 1).value or "").startswith("TOP 5 BY GST RATE") for r in range(1, ws.max_row + 1)))
                wb.close()
            finally:
                export_service.GENERATED_DIR = old_dir


if __name__ == "__main__":
    unittest.main(verbosity=2)
