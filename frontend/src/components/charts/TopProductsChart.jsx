import { useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const clean = (value) =>
  String(value ?? "").trim().toLowerCase().replace(/[^a-z0-9]/g, "");

function findColumn(columns, aliases) {
  return columns.find((column) =>
    aliases.some((alias) => clean(column) === clean(alias))
  );
}

function toNumber(value) {
  if (value === null || value === undefined || value === "") return 0;
  const parsed = Number(String(value).replace(/[₹,%\s]/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

export default function TopProductsChart({ rows = [], columns = [] }) {
  const [metric, setMetric] = useState("sales");

  const productColumn = useMemo(
    () => findColumn(columns, ["Product", "Product Name", "Item Name", "Item", "Stock Item"]),
    [columns]
  );

  const metricColumns = useMemo(() => ({
    sales: findColumn(columns, [
      "GrossAmount", "Sales", "Sale Amount", "InvoiceTotal", "Invoice Value", "Amount"
    ]),
    profit: findColumn(columns, ["Profit", "Net Profit"]),
    quantity: findColumn(columns, ["Qty", "Quantity", "Product Quantity"]),
  }), [columns]);

  const chartData = useMemo(() => {
    if (!productColumn || !metricColumns[metric] || !rows.length) return [];

    const totals = new Map();
    const valueColumn = metricColumns[metric];

    for (const row of rows) {
      const product = String(row?.[productColumn] ?? "").trim();
      if (!product) continue;

      totals.set(
        product,
        (totals.get(product) || 0) + toNumber(row?.[valueColumn])
      );
    }

    return Array.from(totals, ([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 5);
  }, [rows, productColumn, metricColumns, metric]);

  const formatValue = (value) =>
    metric === "quantity"
      ? Number(value).toLocaleString("en-IN")
      : `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

  return (
    <section className="chart-card top-products-card">
      <div className="chart-header top-products-header">
        <div>
          <span className="section-kicker">PRODUCT PERFORMANCE</span>
          <h3>Top 5 Products by {metric === "sales" ? "Sales" : metric === "profit" ? "Profit" : "Quantity"}</h3>
        </div>

        <select
          aria-label="Product metric"
          value={metric}
          onChange={(event) => setMetric(event.target.value)}
        >
          <option value="sales">Sales</option>
          <option value="profit">Profit</option>
          <option value="quantity">Quantity</option>
        </select>
      </div>

      {!productColumn ? (
        <div className="chart-empty">
          Product information is not available in the selected dataset.
        </div>
      ) : !metricColumns[metric] ? (
        <div className="chart-empty">
          The selected dataset does not contain a compatible {metric} column.
        </div>
      ) : !chartData.length ? (
        <div className="chart-empty">No product data available to display.</div>
      ) : (
        <div className="top-products-plot">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 6, right: 24, left: 12, bottom: 6 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tickFormatter={(value) =>
                metric === "quantity"
                  ? Number(value).toLocaleString("en-IN")
                  : value >= 100000
                    ? `₹${(value / 100000).toFixed(1)}L`
                    : `₹${Number(value).toLocaleString("en-IN")}`
              } />
              <YAxis
                type="category"
                dataKey="label"
                width={115}
                tick={{ fontSize: 12 }}
              />
              <Tooltip formatter={(value) => formatValue(value)} />
              <Bar dataKey="value" name={metric} fill="#4F46E5" radius={[0, 5, 5, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
