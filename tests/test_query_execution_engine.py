
import unittest
import pandas as pd

from tests.query_execution_prototype import (
    apply_filters,
    apply_date_filter,
    aggregate_data,
    execute_plan,
)


class TestQueryExecutionEngine(unittest.TestCase):

    def setUp(self):
        self.df = pd.DataFrame({
            "Product": [
                "Watch", "Watch", "Bag",
                "Bag", "Scarf", "Scarf"
            ],
            "UnitPrice": [2000, 1200, 1800, 900, 1600, 800],
            "Qty": [3, 2, 5, 1, 4, 2],
            "GrossAmount": [6000, 2400, 9000, 900, 6400, 1600],
            "Profit": [1500, 600, 3000, 300, 1600, 400],
            "Date": pd.to_datetime([
                "2025-04-01",
                "2025-04-15",
                "2025-05-01",
                "2025-05-15",
                "2025-06-01",
                "2025-06-15",
            ]),
        })

    def test_numeric_greater_filter(self):
        result = apply_filters(
            self.df,
            [{"column": "UnitPrice", "operator": ">", "value": 1500}]
        )
        self.assertEqual(len(result), 3)

    def test_multiple_numeric_filters(self):
        result = apply_filters(
            self.df,
            [
                {"column": "UnitPrice", "operator": ">", "value": 1000},
                {"column": "Qty", "operator": "<", "value": 5},
            ]
        )
        self.assertEqual(len(result), 3)

    def test_date_filter_inclusive(self):
        result = apply_date_filter(
            self.df,
            {
                "column": "Date",
                "start_date": "2025-04-01",
                "end_date": "2025-04-15",
            }
        )
        self.assertEqual(len(result), 2)

    def test_grouped_quantity_sum(self):
        result = aggregate_data(
            self.df,
            ["Qty"],
            {"Qty": "sum"},
            "Product",
        )
        actual = dict(zip(result["Product"], result["Qty"]))
        self.assertEqual(actual["Watch"], 5)
        self.assertEqual(actual["Bag"], 6)
        self.assertEqual(actual["Scarf"], 6)

    def test_multiple_metrics_different_operations(self):
        result = aggregate_data(
            self.df,
            ["Qty", "Profit"],
            {"Qty": "average", "Profit": "sum"},
        )
        self.assertAlmostEqual(result.iloc[0]["Qty"], 17 / 6)
        self.assertAlmostEqual(result.iloc[0]["Profit"], 7400)

    def test_descending_ranking(self):
        plan = {
            "metrics": ["Profit"],
            "metric_operations": {"Profit": "sum"},
            "group_by": "Product",
            "ranking_metric": "Profit",
            "ranking": "descending",
            "limit": 2,
        }
        result = execute_plan(self.df, plan)
        self.assertEqual(result["rows"][0]["Product"], "Bag")
        self.assertEqual(result["rows"][1]["Product"], "Watch")

    def test_ascending_ranking(self):
        plan = {
            "metrics": ["Profit"],
            "metric_operations": {"Profit": "sum"},
            "group_by": "Product",
            "ranking_metric": "Profit",
            "ranking": "ascending",
            "limit": 1,
        }
        result = execute_plan(self.df, plan)
        self.assertEqual(result["rows"][0]["Product"], "Scarf")

    def test_empty_filter_returns_no_data(self):
        plan = {
            "metrics": ["Profit"],
            "filters": [
                {"column": "UnitPrice", "operator": ">", "value": 99999}
            ],
        }
        result = execute_plan(self.df, plan)
        self.assertEqual(result["status"], "no_data")
        self.assertEqual(result["filtered_rows"], 0)

    def test_missing_metric_column_raises_error(self):
        with self.assertRaises(ValueError):
            aggregate_data(
                self.df,
                ["MissingMetric"],
                {"MissingMetric": "sum"},
            )

    def test_missing_group_column_raises_error(self):
        with self.assertRaises(ValueError):
            aggregate_data(
                self.df,
                ["Profit"],
                {"Profit": "sum"},
                "MissingGroup",
            )

    def test_unsupported_operation_raises_error(self):
        with self.assertRaises(ValueError):
            aggregate_data(
                self.df,
                ["Profit"],
                {"Profit": "median"},
            )


    def test_custom_preview_limit(self):
        plan = {
            "filters": [
                {"column": "UnitPrice", "operator": ">", "value": 0}
            ],
            "preview_limit": 3,
        }

        result = execute_plan(self.df, plan)

        self.assertEqual(result["status"], "filtered_data")
        self.assertEqual(result["total_matching_rows"], 6)
        self.assertEqual(result["preview_limit"], 3)
        self.assertEqual(len(result["preview_rows"]), 3)

    def test_invalid_preview_limit_raises_error(self):
        plan = {
            "preview_limit": 0,
        }

        with self.assertRaises(ValueError):
            execute_plan(self.df, plan)

    def test_missing_ranking_metric_raises_error(self):
        plan = {
            "metrics": ["Profit"],
            "metric_operations": {"Profit": "sum"},
            "group_by": "Product",
            "ranking_metric": "Revenue",
            "ranking": "descending",
        }

        with self.assertRaisesRegex(
            ValueError,
            "Ranking metric 'Revenue'",
        ):
            execute_plan(self.df, plan)

    def test_empty_dataset_ranking_returns_no_data(self):
        empty_df = self.df.iloc[0:0].copy()

        plan = {
            "metrics": ["Profit"],
            "metric_operations": {"Profit": "sum"},
            "group_by": "Product",
            "ranking_metric": "Profit",
            "ranking": "descending",
            "limit": 5,
        }

        result = execute_plan(empty_df, plan)

        self.assertEqual(result["status"], "no_data")
        self.assertEqual(result["source_rows"], 0)
        self.assertEqual(result["filtered_rows"], 0)
        self.assertEqual(result["total_matching_rows"], 0)
        self.assertEqual(result["rows"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)



