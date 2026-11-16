import { useMemo, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, Brush, CartesianGrid, Cell, ComposedChart,
  Funnel, FunnelChart, LabelList, Legend, Line, LineChart, Pie, PieChart,
  PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart,
  ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, Treemap,
  XAxis, YAxis,
} from "recharts";

const RUPEE = "\u20B9";
const CLEAN = /[\u20B9,%\s,]/g;
const PALETTE = ["#2878f0", "#f59e0b", "#10b981", "#8b5cf6", "#ec4899", "#06b6d4", "#ef4444", "#84cc16"];

function num(value) {
  if (value === null || value === undefined || value === "") return 0;
  const n = Number(String(value).replace(CLEAN, "").trim());
  return Number.isFinite(n) ? n : 0;
}
const MONEY_METRIC = /sales|revenue|profit|earning|amount|gst|tax|discount|cost|price|value|turnover|billing|invoice|salary|wage|income|commission|expense|payment/i;
const NON_MONEY_METRIC = /count|quantity|qty|units?|employees?|customers?|products?|orders?|invoices? count|number of|percent|percentage|margin|share|attendance|hours?|days?|score|rate %/i;
function short(v, metricLabel = "") {
  const n = num(v), a = Math.abs(n);
  const money = Boolean(metricLabel && MONEY_METRIC.test(metricLabel) && !NON_MONEY_METRIC.test(metricLabel));
  const prefix = money ? RUPEE : "";
  if (a >= 1e7) return `${prefix}${(n / 1e7).toFixed(2)}Cr`;
  if (a >= 1e5) return `${prefix}${(n / 1e5).toFixed(2)}L`;
  if (a >= 1e3) return `${prefix}${(n / 1e3).toFixed(1)}K`;
  return `${prefix}${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}
function percentile(sorted, p) {
  if (!sorted.length) return 0;
  const index = (sorted.length - 1) * p;
  const low = Math.floor(index), high = Math.ceil(index);
  return sorted[low] + (sorted[high] - sorted[low]) * (index - low);
}
function Empty({ title, message }) {
  return <div className="chart-wrapper"><h4 className="chart-title">{title}</h4><div className="chart-empty-state">{message}</div></div>;
}

export default function ChartRenderer({
  type = "bar",
  data = [],
  series = null,
  title = "",
  dualAxis = false,
}) {
  const [selectedCell, setSelectedCell] = useState(null);
  const [selectedPoint, setSelectedPoint] = useState(null);
  const [selectedMetric, setSelectedMetric] = useState(null);

  const selectPoint = (point, metricKey = null) => {
    const row = point?.payload?.payload ?? point?.payload ?? point;
    if (!row || row.label == null) return;

    setSelectedPoint(row);
    setSelectedMetric(metricKey);
  };
  const chartSeries = useMemo(() => {
    if (Array.isArray(series) && series.length) {
      return series.map((s, i) => typeof s === "string"
        ? { key: s, field: s, label: s, color: PALETTE[i % PALETTE.length] }
        : { ...s, key: s.key || s.field || s.column, field: s.field || s.key || s.column,
            label: s.label || s.field || s.key || `Metric ${i + 1}`, color: s.color || PALETTE[i % PALETTE.length] });
    }
    if (!data.length) return [];
    const sample = data[0] || {};
    return Object.keys(sample).filter((k) => k !== "label" && k !== "name" && k !== "period" && Number.isFinite(Number(sample[k])))
      .map((k, i) => ({ key: k, field: k, label: k, color: PALETTE[i % PALETTE.length] }));
  }, [series, data]);

  const points = useMemo(() => data.map((item, index) => {
    const label = item?.label ?? item?.name ?? item?.period ?? item?.date ?? item?.month ?? `Item ${index + 1}`;
    const point = { ...item, label: String(label) };
    chartSeries.forEach((s) => { point[s.key] = num(item?.[s.key] ?? item?.[s.field]); });
    return point;
  }), [data, chartSeries]);

  if (!points.length) return <Empty title={title || "Visualization"} message="No query result data is available for this chart." />;
  if (!chartSeries.length) return <Empty title={title || "Visualization"} message="This result does not contain numeric metrics to plot." />;

  const crowded = points.length > 8;
  const xProps = { dataKey: "label", tick: { fontSize: 11 }, interval: crowded ? "preserveStartEnd" : "preserveEnd",
    angle: crowded ? -30 : 0, textAnchor: crowded ? "end" : "middle", height: crowded ? 65 : 30 };
  const yProps = { tick: { fontSize: 11 }, tickFormatter: (v) => short(v, chartSeries.length === 1 ? chartSeries[0].label : "") };
  const tooltip = (value, name) => { const metric = chartSeries.find((s) => s.key === name || s.label === name); return [short(value, metric?.label || name), metric?.label || name]; };
  const base = <><Tooltip formatter={tooltip} cursor={false} /><Legend /></>;
  
  

  const selectedDetails = selectedPoint ? (
    <div
      style={{
        marginTop: 12,
        padding: 14,
        border: "1px solid #dbe5f4",
        borderRadius: 10,
        background: "#f8fbff",
      }}
    >
      <strong>Selected period: {selectedPoint.label}</strong>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: 10,
          marginTop: 10,
        }}
      >
        {chartSeries
          .filter((metric) => !selectedMetric || metric.key === selectedMetric)
          .map((metric) => (
          <div
            key={metric.key}
            style={{
              padding: 10,
              background: "#ffffff",
              border: "1px solid #e5edf8",
              borderRadius: 8,
            }}
          >
            <div style={{ fontSize: 12, color: "#64748b" }}>
              {metric.label}
            </div>
            <strong>
              {num(selectedPoint[metric.key]).toLocaleString("en-IN", {
                maximumFractionDigits: 2,
              })}
            </strong>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => {
          setSelectedPoint(null);
          setSelectedMetric(null);
        }}
        style={{ marginTop: 10, cursor: "pointer" }}
      >
        Clear selection
      </button>
    </div>
  ) : null;

  if (type === "heatmap") {
    const max = Math.max(1, ...points.flatMap((p) => chartSeries.map((s) => Math.abs(num(p[s.key])))));
    return <div className="chart-wrapper">{title && <h4 className="chart-title">{title}</h4>}
      <div style={{ overflowX: "auto" }}><div style={{ display: "grid", gridTemplateColumns: `minmax(110px,1.2fr) repeat(${chartSeries.length}, minmax(85px,1fr))`, gap: 5, minWidth: 260 }}>
        <div style={{ padding: 8, fontWeight: 700 }}>Category</div>
        {chartSeries.map((s) => <div key={s.key} style={{ padding: 8, fontWeight: 700, textAlign: "center" }}>{s.label}</div>)}
        {points.map((p, i) => <div key={p.label + i} style={{ display: "contents" }}>
          <div style={{ padding: 8, overflowWrap: "anywhere", alignSelf: "center" }}>{p.label}</div>
          {chartSeries.map((s) => {
            const value = num(p[s.key]); const intensity = Math.min(0.88, Math.abs(value) / max * 0.88);
            return <button key={s.key} type="button" onClick={() => setSelectedCell({ label: p.label, metric: s.label, value })}
              title={`${p.label} . ${s.label}: ${short(value, s.label)}`}
              style={{ minHeight: 42, border: selectedCell?.label === p.label && selectedCell?.metric === s.label ? "2px solid #111827" : "1px solid #ffffff80",
                borderRadius: 5, cursor: "pointer", background: value >= 0 ? `rgba(37, 120, 240, ${intensity})` : `rgba(239, 68, 68, ${intensity})`,
                color: intensity > 0.48 ? "#fff" : "inherit", padding: 6 }}>{short(value, s.label)}</button>;
          })}
        </div>)}
      </div></div>
      {selectedCell && <p style={{ marginTop: 12 }}>Selected: <b>{selectedCell.label}</b> Â· {selectedCell.metric}: <b>{short(selectedCell.value, selectedCell.metric)}</b></p>}
    </div>;
  }

  if (type === "boxplot") {
    const boxes = chartSeries.map((s) => {
      const values = points.map((p) => num(p[s.key])).sort((a, b) => a - b);
      return { label: s.label, min: values[0], q1: percentile(values, .25), median: percentile(values, .5),
        q3: percentile(values, .75), max: values[values.length - 1] };
    }).filter((b) => Number.isFinite(b.min));
    return <div className="chart-wrapper">{title && <h4 className="chart-title">{title}</h4>}
      <p style={{ color: "var(--muted, #64748b)", fontSize: 12 }}>Five-number summary calculated from the numeric observations in this query result.</p>
      <ResponsiveContainer width="100%" height={360}><BarChart data={boxes} margin={{ top: 16, right: 20, bottom: 20, left: 8 }}>
        <XAxis dataKey="label" interval={0} angle={boxes.length > 4 ? -25 : 0} height={boxes.length > 4 ? 60 : 30} />
        <YAxis tickFormatter={(v) => short(v, chartSeries.length === 1 ? chartSeries[0].label : "")} /><Tooltip formatter={tooltip} cursor={false} />
        <Bar dataKey="q1" stackId="box" fill="transparent" />
        <Bar dataKey={(row) => row.q3 - row.q1} name="Interquartile range" stackId="range" fill="#2878f0">
          <LabelList content={({ x, y, width, value }) => value == null ? null : <text x={x + width / 2} y={y - 5} textAnchor="middle" fontSize={10}>{short(value)}</text>} />
        </Bar>
      </BarChart></ResponsiveContainer>
      <div className="table-scroll"><table><thead><tr>{["Metric","Min","Q1","Median","Q3","Max"].map((h) => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>{boxes.map((b) => <tr key={b.label}><td>{b.label}</td><td>{short(b.min, b.label)}</td><td>{short(b.q1, b.label)}</td><td>{short(b.median, b.label)}</td><td>{short(b.q3, b.label)}</td><td>{short(b.max, b.label)}</td></tr>)}</tbody></table></div>
    </div>;
  }

  if (type === "pie" || type === "donut") {
    const metric = chartSeries[0];
    const pieData = points.map((p) => ({ name: p.label, value: num(p[metric.key]) })).filter((p) => p.value > 0).sort((a, b) => b.value - a.value).slice(0, 12);
    if (!pieData.length) return <Empty title={title || "Pie chart"} message="Pie and Donut charts require positive values in the selected metric." />;
    return <div className="chart-wrapper">{title && <h4 className="chart-title">{title}</h4>}
      <ResponsiveContainer width="100%" height={360}><PieChart><Tooltip formatter={(v, name) => { const metric = chartSeries.find((s) => s.key === name || s.label === name) || chartSeries[0]; return short(v, metric?.label || ""); }} /><Legend />
        <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={125} innerRadius={type === "donut" ? 72 : 0} paddingAngle={2} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
          {pieData.map((p, i) => <Cell key={p.name} fill={PALETTE[i % PALETTE.length]} />)}
        </Pie>
      </PieChart></ResponsiveContainer></div>;
  }

  if (type === "funnel") {
    const metric = chartSeries[0];
    const funnelData = points.map((p) => ({ name: p.label, value: Math.max(0, num(p[metric.key])) })).filter((p) => p.value > 0);
    if (!funnelData.length) return <Empty title={title || "Funnel"} message="Funnel needs positive stage values in the result." />;
    return <div className="chart-wrapper">{title && <h4 className="chart-title">{title}</h4>}
      <ResponsiveContainer width="100%" height={380}><FunnelChart><Tooltip formatter={(v, name) => { const metric = chartSeries.find((s) => s.key === name || s.label === name) || chartSeries[0]; return short(v, metric?.label || ""); }} /><Funnel dataKey="value" data={funnelData} isAnimationActive>
        {funnelData.map((entry, i) => <Cell key={entry.name} fill={PALETTE[i % PALETTE.length]} />)}
        <LabelList position="right" dataKey="name" fill="currentColor" />
      </Funnel></FunnelChart></ResponsiveContainer></div>;
  }

  if (type === "treemap") {
    const metric = chartSeries[0];
    const treeData = points.map((p) => ({ name: p.label, size: Math.max(0, num(p[metric.key])) })).filter((p) => p.size > 0);
    if (!treeData.length) return <Empty title={title || "Treemap"} message="Treemap needs positive values in the selected metric." />;
    return <div className="chart-wrapper">{title && <h4 className="chart-title">{title}</h4>}
      <ResponsiveContainer width="100%" height={380}><Treemap data={treeData} dataKey="size" nameKey="name" aspectRatio={4 / 3} stroke="#fff" content={({ x, y, width, height, name, size, index }) => (
        <g><rect x={x} y={y} width={width} height={height} fill={PALETTE[(index || 0) % PALETTE.length]} stroke="#fff" />
          {width > 65 && height > 35 && <><text x={x + 7} y={y + 18} fill="#fff" fontSize={12}>{String(name).slice(0, 20)}</text><text x={x + 7} y={y + 35} fill="#fff" fontSize={11}>{short(size, metric.label)}</text></>}</g>
      )}><Tooltip formatter={(v, name) => { const metric = chartSeries.find((s) => s.key === name || s.label === name) || chartSeries[0]; return short(v, metric?.label || ""); }} /></Treemap></ResponsiveContainer></div>;
  }

  if (type === "radar") {
    return <div className="chart-wrapper">{title && <h4 className="chart-title">{title}</h4>}
      <ResponsiveContainer width="100%" height={390}><RadarChart data={points}><PolarGrid /><PolarAngleAxis dataKey="label" tick={{ fontSize: 11 }} /><PolarRadiusAxis tickFormatter={(v) => short(v, chartSeries.length === 1 ? chartSeries[0].label : "")} />
        <Tooltip formatter={tooltip} cursor={false} /><Legend />{chartSeries.map((s) => <Radar key={s.key} name={s.label} dataKey={s.key} stroke={s.color} fill={s.color} fillOpacity={0.18} />)}
      </RadarChart></ResponsiveContainer></div>;
  }

  if (type === "scatter" || type === "bubble") {
    const xMetric = chartSeries[0], yMetric = chartSeries[1] || chartSeries[0], sizeMetric = chartSeries[2];
    const scatterData = points.map((p) => ({ ...p, __x: num(p[xMetric.key]), __y: num(p[yMetric.key]),
      __z: sizeMetric ? Math.max(30, Math.min(600, Math.abs(num(p[sizeMetric.key])) / Math.max(1, ...points.map((q) => Math.abs(num(q[sizeMetric.key]))) ) * 600)) : 90 }));
    return <div className="chart-wrapper">{title && <h4 className="chart-title">{title}</h4>}
      <p style={{ fontSize: 12, color: "var(--muted, #64748b)" }}>X: {xMetric.label} Â· Y: {yMetric.label}{type === "bubble" && sizeMetric ? ` Â· Bubble size: ${sizeMetric.label}` : ""}</p>
      <ResponsiveContainer width="100%" height={390}><ScatterChart margin={{ bottom: 15, left: 10, right: 15 }}>
        <CartesianGrid /><XAxis type="number" dataKey="__x" name={xMetric.label} tickFormatter={(v) => short(v, xMetric.label)} /><YAxis type="number" dataKey="__y" name={yMetric.label} tickFormatter={(v) => short(v, yMetric.label)} />
        <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(v, name) => { const metric = chartSeries.find((s) => s.key === name || s.label === name) || (name === xMetric.label ? xMetric : yMetric); return [short(v, metric?.label || name), name]; }} labelFormatter={(_, payload) => payload?.[0]?.payload?.label || ""} />
        {type === "bubble" ? <Scatter
          name={`${xMetric.label} / ${yMetric.label}`}
          data={scatterData}
          shape={(props) => {
            const radius = Math.max(4, Math.min(24, Math.sqrt(props.payload?.__z || 90) / 2));
            return <circle cx={props.cx} cy={props.cy} r={radius} fill={props.fill || "#2878f0"} fillOpacity={0.65} stroke="#fff" strokeWidth={1} />;
          }}
          fill="#2878f0"
        >
          {scatterData.map((p, i) => <Cell key={p.label + i} fill={PALETTE[i % PALETTE.length]} />)}
        </Scatter> : <>{chartSeries.slice(1).map((s, i) => <Scatter key={s.key} name={`${xMetric.label} Ã— ${s.label}`} data={points.map((p) => ({ ...p, __x: num(p[xMetric.key]), __y: num(p[s.key]) }))} dataKey="__y" fill={s.color} />)}
          {chartSeries.length === 1 && <Scatter name={xMetric.label} data={scatterData} dataKey="__y" fill={xMetric.color} />}</>}
      </ScatterChart></ResponsiveContainer></div>;
  }

  if (type === "waterfall") {
    const metric = chartSeries[0];
    let running = 0;
    const waterfall = points.map((p) => {
      const change = num(p[metric.key]), start = running;
      running += change;
      return { label: p.label, change, base: Math.min(start, running), positive: Math.max(0, change), negative: Math.min(0, change), end: running };
    });
    return <div className="chart-wrapper">{title && <h4 className="chart-title">{title}</h4>}
      <p style={{ fontSize: 12, color: "var(--muted, #64748b)" }}>Cumulative running total of {metric.label}; use ordered increments/decrements for a meaningful waterfall.</p>
      <ResponsiveContainer width="100%" height={390}><ComposedChart data={waterfall}><XAxis {...xProps} /><YAxis tickFormatter={(v) => short(v, metric.label)} /><Tooltip formatter={tooltip} cursor={false} /><ReferenceLine y={0} stroke="#64748b" />
        <Bar dataKey="base" stackId="w" fill="transparent" />
        <Bar dataKey="positive" stackId="w" name="Increase" fill="#10b981" />
        <Bar dataKey="negative" stackId="w" name="Decrease" fill="#ef4444" />
        <Line dataKey="end" name="Running total" stroke="#2878f0" dot />
      </ComposedChart></ResponsiveContainer></div>;
  }

  const common = (
    <>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis {...xProps} />
      <YAxis
        yAxisId={dualAxis ? "left" : "default"}
        tickFormatter={(v) => short(v, chartSeries.length === 1 ? chartSeries[0].label : "")}
      />
      {dualAxis && (
        <YAxis
          yAxisId="right"
          orientation="right"
          tickFormatter={(v) => short(v, chartSeries.length === 1 ? chartSeries[0].label : "")}
        />
      )}
      <Tooltip formatter={tooltip} />
      <Legend />
      {points.length > 12 && <Brush dataKey="label" height={20} travellerWidth={10} stroke="#2878f0" fill="#eaf1ff" />}
    </>
  );
  if (type === "line") return <div className="chart-wrapper">{title && <h4 className="chart-title">{title}</h4>}<ResponsiveContainer width="100%" height={360}><LineChart data={points}>{common}{chartSeries.map((s,index) =>
    <Line
      key={s.key}
      type="monotone"
      dataKey={s.key}
      name={s.label}
      stroke={s.color}
      strokeWidth={2.5}
      yAxisId={dualAxis ? (index === 0 ? "left" : "right") : "default"}
      dot={{ r: 4, cursor: "pointer", onClick: (event, payload) => selectPoint(payload?.payload) }}
      activeDot={{
        r: 7,
        cursor: "pointer",
        onClick: (event, payload) => selectPoint(payload?.payload),
      }}
    /> )}{points.length > 8 && <Brush dataKey="label" height={18} travellerWidth={9} stroke="#2878f0" fill="#eaf1ff" />}</LineChart></ResponsiveContainer>{selectedDetails}</div>;
  if (type === "area" || type === "stacked-area") return <div className="chart-wrapper">{title && <h4 className="chart-title">{title}</h4>}<ResponsiveContainer width="100%" height={360}><AreaChart data={points}>{common}{chartSeries.map((s) => <Area key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={s.color} fill={s.color} fillOpacity={0.2} stackId={type === "stacked-area" ? "area" : undefined} />)}{points.length > 8 && <Brush dataKey="label" height={18} travellerWidth={9} stroke="#2878f0" fill="#eaf1ff" />}</AreaChart></ResponsiveContainer>{selectedDetails}</div>;
  return (
  <div className="chart-wrapper">
    {title && <h4 className="chart-title">{title}</h4>}

    <ResponsiveContainer width="100%" height={390}>
      <BarChart data={points} barCategoryGap="25%" barGap={0} margin={{ top: 12, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid vertical={false} stroke="#e5e7eb" strokeWidth={1} />
        {common}

        {chartSeries.map((s,index) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.label}
            fill={s.color}
            radius={0}
            yAxisId={dualAxis ? (index === 0 ? "left" : "right") : "default"}
            stackId={type === "stacked-bar" ? "stack" : undefined}
            cursor="pointer"
            onClick={(entry, index) => { const row = entry?.payload ?? points[index]; if (row) selectPoint(row); }}
            shape={(props) => {
              const isSelected =
                selectedPoint?.label === props.payload?.label;

              return (
                <rect
                  x={props.x}
                  y={props.y}
                  width={props.width}
                  height={props.height}
                  rx={0}
                  fill={s.color}
                  stroke={isSelected ? "#111827" : "#ffffff"}
                  strokeWidth={isSelected ? 3 : 0.5}
                  style={{
                    cursor: "pointer",
                    filter: isSelected
                      ? "drop-shadow(0 4px 5px rgba(15,23,42,.35))"
                      : "none",
                    transition: "filter .15s ease",
                  }}
                />
              );
            }}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>

    {selectedDetails}
  </div>
);
  }
