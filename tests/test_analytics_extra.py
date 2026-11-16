import pandas as pd
import pytest
from pathlib import Path
from graph.analytics_extra import handle


@pytest.fixture(scope="module")
def sales_df():
    path = (
        Path(__file__).resolve().parents[1]
        / "test_data"
        / "Vyapar_Style_Accessories_Sales_Report.xlsx"
    )
    if not path.exists():
        pytest.skip(f"Test Excel file not found: {path}")

    return pd.read_excel(path, sheet_name="Sale Invoices")


def test_date_range_sales(sales_df):
    result = handle(
        "Show total sales between 15-08-2026 to 30-08-2026",
        sales_df,
    )
    assert result is not None

    data = result["result"]
    assert data["filtered_rows"] == 235
    assert data["total_value"] == pytest.approx(541172.87, abs=0.01)
    assert len(data["table"]) == 16


def test_single_day_sales(sales_df):
    result = handle("Show sales for 15 August 2026", sales_df)
    assert result is not None

    data = result["result"]
    assert data["filtered_rows"] == 10
    assert float(data["value"]) == pytest.approx(18748.45, abs=0.01)
    assert len(data["table"]) == 1


def test_month_wise_sales(sales_df):
    result = handle("Show total sales month wise", sales_df)
    assert result is not None

    data = result["result"]
    table = pd.DataFrame(data["table"])

    assert data["filtered_rows"] == 8325
    assert len(table) == 17
    assert {"period", "Sales"}.issubset(table.columns)

    august_2026 = table.loc[table["period"] == "2026-08", "Sales"]
    assert len(august_2026) == 1
    assert float(august_2026.iloc[0]) == pytest.approx(
        1126603.11, abs=0.01
    )


def test_product_wise_quantity_and_sales(sales_df):
    result = handle("Show quantity and sales product wise", sales_df)
    assert result is not None

    data = result["result"]
    table = pd.DataFrame(data["table"])

    assert data["filtered_rows"] == 8325
    assert len(table) == 40
    assert {"Product", "Quantity", "Sales"}.issubset(table.columns)

    product = table.loc[table["Product"] == "Ladies Watch"].iloc[0]
    assert float(product["Quantity"]) == pytest.approx(561)
    assert float(product["Sales"]) == pytest.approx(
        1177275.94, abs=0.01
    )


def test_year_wise_invoice_count_and_discount(sales_df):
    result = handle(
        "Show invoice count and discount year wise",
        sales_df,
    )
    assert result is not None

    data = result["result"]
    table = pd.DataFrame(data["table"])

    assert data["filtered_rows"] == 8325
    assert {"period", "Invoice Count", "Discount"}.issubset(
        table.columns
    )

    row_2025 = table.loc[table["period"].astype(str) == "2025"].iloc[0]
    row_2026 = table.loc[table["period"].astype(str) == "2026"].iloc[0]

    assert float(row_2025["Invoice Count"]) == pytest.approx(4480)
    assert float(row_2025["Discount"]) == pytest.approx(
        407536.36, abs=0.01
    )
    assert float(row_2026["Invoice Count"]) == pytest.approx(3845)
    assert float(row_2026["Discount"]) == pytest.approx(
        360188.45, abs=0.01
    )
