import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3, ChevronLeft, ChevronRight, Database, Download, FileText, Plus, RotateCcw,
  ShoppingCart, Users, X, ZoomIn, ZoomOut, Columns3,
} from "lucide-react";
import {
  MONTHS, addMonths, compactMoney, downloadCsv, endOfMonth, findColumn, fmtMonth, formatMoney,
  formatNumber, greeting, isNumericColumn, numericValue, parseDate, pctChange, startOfMonth,
} from "../../lib/helpers.js";
import { DataTable, EmptyState, FullscreenButton } from "../common.jsx";
import {
  DateRangePicker, DonutChart, FilterPopover, KpiCard, RangeSlider, TopList, TrendChart,
} from "./widgets.jsx";

/* --------------------------------------------------------- helpers */
const GRAINS = [["day", "Daily"], ["week", "Weekly"], ["month", "Monthly"], ["quarter", "Quarterly"], ["year", "Yearly"]];
const pad = (n) => String(n).padStart(2, "0");
const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

function keyOf(d, grain) {
  if (grain === "day") return iso(d);
  if (grain === "week") {
    const back = (d.getDay() + 6) % 7;
    return iso(new Date(d.getFullYear(), d.getMonth(), d.getDate() - back));
  }
  if (grain === "quarter") return `${d.getFullYear()}-Q${Math.floor(d.getMonth() / 3) + 1}`;
  if (grain === "year") return String(d.getFullYear());
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
}

function labelOf(key, grain) {
  if (grain === "year") return key;
  if (grain === "quarter") { const [y, q] = key.split("-"); return `${q} ${y}`; }
  if (grain === "month") { const [y, m] = key.split("-"); return `${MONTHS[+m - 1]} ${y}`; }
  const [y, m, d] = key.split("-");
  return grain === "week" ? `Wk ${+d} ${MONTHS[+m - 1]}` : `${+d} ${MONTHS[+m - 1]} ${y.slice(2)}`;
}

function buildSeries(rows, grain, hasProfit) {
  const map = new Map();
  for (const r of rows) {
    if (!r.d) continue;
    const k = keyOf(r.d, grain);
    const cur = map.get(k) || { key: k, label: labelOf(k, grain), sales: 0, profit: 0, count: 0, hasProfit };
    cur.sales += r.sales;
    cur.profit += r.profit;
    cur.count += 1;
    map.set(k, cur);
  }
  return [...map.values()].sort((a, b) => (a.key < b.key ? -1 : 1)).map((s) => ({ ...s, sales: Math.round(s.sales * 100) / 100, profit: Math.round(s.profit * 100) / 100 }));
}

function resolveRange(preset, custom, bounds) {
  if (!bounds || preset === "all") return null;
  const maxD = bounds.max;
  if (preset === "custom" && custom.from && custom.to) {
    const [fy, fm] = custom.from.split("-").map(Number);
    const [ty, tm] = custom.to.split("-").map(Number);
    return { start: new Date(fy, fm - 1, 1), end: endOfMonth(new Date(ty, tm - 1, 1)) };
  }
  if (preset === "ytd") return { start: new Date(maxD.getFullYear(), 0, 1), end: endOfMonth(maxD) };
  const n = { "1m": 1, "3m": 3, "6m": 6, "12m": 12 }[preset];
  if (!n) return null;
  return { start: addMonths(startOfMonth(maxD), -(n - 1)), end: endOfMonth(maxD) };
}

function previousRange(range) {
  if (!range) return null;
  const months = (range.end.getFullYear() - range.start.getFullYear()) * 12 + (range.end.getMonth() - range.start.getMonth()) + 1;
  return { start: addMonths(range.start, -months), end: endOfMonth(addMonths(range.start, -1)) };
}

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/* ------------------------------------------------------- component */
export default function Dashboard({
  datasets, selectedDataset, selectedDatasetId, onSelectDataset, rows, columns, loading, userName, onUpload,
}) {
  /* ---- detect columns once per dataset ---- */
  const cols = useMemo(() => ({
    sales: findColumn(columns, ["grossamount", "salesamount", "sales", "revenue", "invoicetotal", "totalamount", "netamount", "amount"], /discount|gst|tax|cost|profit|return|rate|qty|quantity/),
    profit: findColumn(columns, ["profit", "netprofit"]),
    qty: findColumn(columns, ["quantity", "qty", "units"]),
    customer: findColumn(columns, ["partyname", "customername", "customer", "party", "client", "buyer"], /type|state|city|gst/),
    category: findColumn(columns, ["category", "productcategory", "itemgroup"]),
    location: findColumn(columns, ["partystate", "state", "city", "region", "location", "territory"]),
    invoice: findColumn(columns, ["invoiceno", "invoicenumber", "invoiceid", "billno", "voucherno", "invoice"], /date|total|value|amount/),
    date: findColumn(columns, ["invoicedate", "billdate", "transactiondate", "orderdate", "date"]),
  }), [columns]);

  const parsed = useMemo(() => rows.map((r) => ({
    d: cols.date ? parseDate(r[cols.date]) : null,
    sales: cols.sales ? numericValue(r[cols.sales]) : 0,
    profit: cols.profit ? numericValue(r[cols.profit]) : 0,
    qty: cols.qty ? numericValue(r[cols.qty]) : 0,
    cust: cols.customer ? String(r[cols.customer] ?? "").trim() : "",
    cat: cols.category ? String(r[cols.category] ?? "").trim() : "",
    loc: cols.location ? String(r[cols.location] ?? "").trim() : "",
    inv: cols.invoice ? String(r[cols.invoice] ?? "").trim() : "",
  })), [rows, cols]);

  const bounds = useMemo(() => {
    let min = null;
    let max = null;
    for (const p of parsed) {
      if (!p.d) continue;
      if (!min || p.d < min) min = p.d;
      if (!max || p.d > max) max = p.d;
    }
    return min ? { min, max } : null;
  }, [parsed]);

  /* ---- ui state ---- */
  const [preset, setPreset] = useState("all");
  const [custom, setCustom] = useState({ from: "", to: "" });
  const [filters, setFilters] = useState({ category: "", customer: "", location: "" });
  const [grain, setGrain] = useState("month");
  const [win, setWin] = useState(null);
  const [selectedKey, setSelectedKey] = useState(null);
  const [showAllCust, setShowAllCust] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    setPreset("all");
    setCustom({ from: "", to: "" });
    setFilters({ category: "", customer: "", location: "" });
    setSelectedKey(null);
  }, [selectedDatasetId]);

  const range = useMemo(() => resolveRange(preset, custom, bounds), [preset, custom, bounds]);
  const prevRange = useMemo(() => previousRange(range), [range]);
  const rangeLabel = bounds
    ? range ? `${fmtMonth(range.start)} - ${fmtMonth(range.end)}` : `${fmtMonth(bounds.min)} - ${fmtMonth(bounds.max)}`
    : "All dates";

  const pick = useCallback((rng, skip = {}) => parsed.filter((p) => {
    if (rng && (!p.d || p.d < rng.start || p.d > rng.end)) return false;
    if (!skip.cat && filters.category && p.cat !== filters.category) return false;
    if (!skip.cust && filters.customer && p.cust !== filters.customer) return false;
    if (!skip.loc && filters.location && p.loc !== filters.location) return false;
    return true;
  }), [parsed, filters]);

  const main = useMemo(() => pick(range), [pick, range]);
  const forCategory = useMemo(() => pick(range, { cat: true }), [pick, range]);
  const forCustomer = useMemo(() => pick(range, { cust: true }), [pick, range]);
  const prev = useMemo(() => (prevRange ? pick(prevRange) : null), [pick, prevRange]);

  const kpi = useCallback((arr) => ({
    sales: arr.reduce((t, r) => t + r.sales, 0),
    profit: arr.reduce((t, r) => t + r.profit, 0),
    invoices: cols.invoice ? new Set(arr.map((r) => r.inv).filter(Boolean)).size : arr.length,
    customers: new Set(arr.map((r) => r.cust).filter(Boolean)).size,
  }), [cols.invoice]);
  const cur = useMemo(() => kpi(main), [kpi, main]);
  const old = useMemo(() => (prev ? kpi(prev) : null), [kpi, prev]);
  const delta = (k) => (old ? pctChange(cur[k], old[k]) : null);
  const deltaNote = old ? "vs previous period" : preset === "all" ? "vs previous period (pick a range)" : "no earlier data";

  /* ---- trend series + sliding window ---- */
  const series = useMemo(() => buildSeries(main, grain, Boolean(cols.profit)), [main, grain, cols.profit]);
  useEffect(() => {
    const n = series.length;
    if (!n) { setWin(null); return; }
    const size = grain === "day" ? Math.min(n, 31) : grain === "week" ? Math.min(n, 26) : n;
    setWin([n - size, n - 1]);
    setSelectedKey(null);
  }, [series.length, grain]); // eslint-disable-line react-hooks/exhaustive-deps

  const len = series.length;
  const visible = win ? series.slice(win[0], win[1] + 1) : series;
  const minSize = Math.min(3, len);

  const zoom = useCallback((dir) => setWin((w) => {
    if (!w || !len) return w;
    const size = w[1] - w[0] + 1;
    const next = dir === "in" ? Math.max(minSize, Math.round(size * 0.6)) : Math.min(len, Math.max(size + 1, Math.round(size / 0.6)));
    const start = clamp(Math.round((w[0] + w[1]) / 2 - (next - 1) / 2), 0, len - next);
    return [start, start + next - 1];
  }), [len, minSize]);

  const pan = useCallback((dir) => setWin((w) => {
    if (!w || !len) return w;
    const size = w[1] - w[0] + 1;
    const step = Math.max(1, Math.round(size / 3)) * dir;
    const start = clamp(w[0] + step, 0, len - size);
    return [start, start + size - 1];
  }), [len]);

  const resetWin = () => { if (len) setWin(grain === "day" ? [Math.max(0, len - 31), len - 1] : grain === "week" ? [Math.max(0, len - 26), len - 1] : [0, len - 1]); setSelectedKey(null); };

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return undefined;
    const onWheel = (e) => {
      if (!(e.ctrlKey || e.metaKey || e.shiftKey)) return;
      e.preventDefault();
      if (e.shiftKey && !e.ctrlKey && !e.metaKey) pan(e.deltaY > 0 || e.deltaX > 0 ? 1 : -1);
      else zoom(e.deltaY < 0 ? "in" : "out");
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoom, pan, len]);

  const selected = series.find((s) => s.key === selectedKey) || null;

  /* ---- category donut + top customers ---- */
  const aggregate = (arr, field) => {
    const m = new Map();
    for (const r of arr) {
      const k = r[field] || "Unknown";
      m.set(k, (m.get(k) || 0) + r.sales);
    }
    return [...m.entries()].map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
  };
  const categoryItems = useMemo(() => {
    if (!cols.category) return [];
    const all = aggregate(forCategory, "cat").filter((i) => i.value > 0);
    const top = all.slice(0, 5).map((i) => ({ ...i, clickable: true }));
    const rest = all.slice(5).reduce((t, i) => t + i.value, 0);
    return rest > 0 ? [...top, { label: "Others", value: rest, clickable: false }] : top;
  }, [forCategory, cols.category]); // eslint-disable-line react-hooks/exhaustive-deps
  const categoryTotal = categoryItems.reduce((t, i) => t + i.value, 0);

  const customerAll = useMemo(() => (cols.customer ? aggregate(forCustomer, "cust").filter((i) => i.value > 0) : []), [forCustomer, cols.customer]); // eslint-disable-line react-hooks/exhaustive-deps
  const customerItems = customerAll.slice(0, showAllCust ? 10 : 5);
  const customerTotal = customerAll.reduce((t, i) => t + i.value, 0);

  const options = useMemo(() => {
    const uniq = (f) => [...new Set(parsed.map((p) => p[f]).filter(Boolean))].sort((a, b) => a.localeCompare(b)).slice(0, 400);
    return { category: cols.category ? uniq("cat") : [], customer: cols.customer ? uniq("cust") : [], location: cols.location ? uniq("loc") : [] };
  }, [parsed, cols]);

  const activeFilters = Object.entries(filters).filter(([, v]) => v);
  const setFocus = (key) => (value) => setFilters((f) => ({ ...f, [key]: value }));

  const exportCsv = () => downloadCsv(`${(selectedDataset?.name || "dashboard").replace(/\.[^.]+$/, "")}_${grain}_trend.csv`,
    series.map((s) => ({ Period: s.label, Sales: s.sales, ...(cols.profit ? { Profit: s.profit } : {}), Records: s.count })));

  /* ---- generic (non-sales) datasets ---- */
  const isBusiness = Boolean(cols.sales || cols.profit);
  const numericCount = useMemo(() => columns.filter((c) => isNumericColumn(rows, c)).length, [columns, rows]);

  /* ---------------------------------------------------------- render */
  return (
    <div className="vx-dash">
      <header className="vx-dash-head">
        <div>
          <h1>{greeting()}, {userName}</h1>
          <p>Business Overview</p>
        </div>
        <div className="vx-head-actions">
          <label className="vx-dataset-select" title="Active dataset">
            <Database size={16} />
            <select value={selectedDatasetId ?? ""} onChange={(e) => onSelectDataset(Number(e.target.value))} disabled={!datasets.length}>
              {!datasets.length && <option value="">No dataset</option>}
              {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>
          <FilterPopover options={options} values={filters} setValues={setFilters} disabled={!isBusiness} />
          <DateRangePicker label={rangeLabel} preset={preset} setPreset={setPreset} custom={custom} setCustom={setCustom} bounds={bounds} disabled={!bounds} />
          <button type="button" className="vx-icon-btn solid" onClick={exportCsv} disabled={!series.length} title="Export trend as CSV"><Download size={17} /></button>
          <button type="button" className="vx-icon-btn solid" onClick={onUpload} title="Upload data"><Plus size={18} /></button>
        </div>
      </header>

      {!datasets.length && !loading ? (
        <EmptyState icon={Database} title="No business data yet" text="Upload a CSV, Excel, JSON or PDF file to build your dashboard from your own data." buttonText="Upload your first file" onClick={onUpload} />
      ) : !isBusiness ? (
        <>
          <div className="vx-kpis">
            <KpiCard icon={FileText} tone="blue" label="Records" value={formatNumber(rows.length)} note="Rows in this dataset" />
            <KpiCard icon={Columns3} tone="green" label="Columns" value={formatNumber(columns.length)} note="Detected fields" />
            <KpiCard icon={BarChart3} tone="orange" label="Numeric fields" value={formatNumber(numericCount)} note="Can be summed / averaged" />
            <KpiCard icon={Database} tone="purple" label="Text fields" value={formatNumber(columns.length - numericCount)} note="Names, labels, dates" />
          </div>
          <section className="vx-card">
            <div className="vx-card-head"><h3>Dataset preview</h3><span className="vx-chip">{selectedDataset?.name || "Dataset"}</span></div>
            <p className="vx-muted">No sales or profit columns were detected, so business charts are hidden. Ask the assistant anything about this file in the chat.</p>
            {rows.length > 0 && <div className="vx-table-wrap"><DataTable rows={rows.slice(0, 50)} columns={columns} /></div>}
          </section>
        </>
      ) : (
        <>
          {activeFilters.length > 0 && (
            <div className="vx-focus-bar">
              <span>Focused on:</span>
              {activeFilters.map(([k, v]) => (
                <button type="button" key={k} className="vx-focus-chip" onClick={() => setFocus(k)("")} title="Remove focus">
                  {k}: <b>{v}</b> <X size={13} />
                </button>
              ))}
              <button type="button" className="vx-link" onClick={() => setFilters({ category: "", customer: "", location: "" })}>Clear all</button>
            </div>
          )}

          <div className="vx-kpis">
            <KpiCard icon={ShoppingCart} tone="blue" label="Total Sales" value={formatMoney(cur.sales)} delta={delta("sales")} note={deltaNote} />
            <KpiCard icon={BarChart3} tone="green" label="Total Profit" value={cols.profit ? formatMoney(cur.profit) : "\u2014"} delta={cols.profit ? delta("profit") : undefined} note={cols.profit ? deltaNote : "Profit column not found"} />
            <KpiCard icon={FileText} tone="orange" label="Total Invoices" value={formatNumber(cur.invoices)} delta={delta("invoices")} note={cols.invoice ? deltaNote : "Counted by rows"} />
            <KpiCard icon={Users} tone="purple" label="Total Customers" value={cols.customer ? formatNumber(cur.customers) : "\u2014"} delta={cols.customer ? delta("customers") : undefined} note={cols.customer ? deltaNote : "Customer column not found"} />
          </div>

          <section className="vx-card vx-trend" ref={wrapRef}>
            <div className="vx-card-head">
              <h3>{GRAINS.find(([g]) => g === grain)?.[1]} Sales &amp; Profit Trend</h3>
              <div className="vx-card-tools">
                <div className="vx-zoom-group" role="group" aria-label="Chart zoom">
                  <button type="button" className="vx-icon-btn" onClick={() => pan(-1)} disabled={!win || win[0] === 0} title="Slide left"><ChevronLeft size={16} /></button>
                  <button type="button" className="vx-icon-btn" onClick={() => zoom("in")} disabled={!win || win[1] - win[0] + 1 <= minSize} title="Zoom in (Ctrl + scroll)"><ZoomIn size={16} /></button>
                  <button type="button" className="vx-icon-btn" onClick={() => zoom("out")} disabled={!win || win[1] - win[0] + 1 >= len} title="Zoom out"><ZoomOut size={16} /></button>
                  <button type="button" className="vx-icon-btn" onClick={resetWin} disabled={!win} title="Reset view"><RotateCcw size={15} /></button>
                  <button type="button" className="vx-icon-btn" onClick={() => pan(1)} disabled={!win || win[1] === len - 1} title="Slide right (Shift + scroll)"><ChevronRight size={16} /></button>
                </div>
                <select className="vx-mini-select" value={grain} onChange={(e) => setGrain(e.target.value)} aria-label="Group by">
                  {GRAINS.map(([g, text]) => <option key={g} value={g}>{text}</option>)}
                </select>
                <FullscreenButton />
              </div>
            </div>
            <div className="vx-legend-inline">
              <span><i className="vx-dot blue" />Sales</span>
              {cols.profit && <span><i className="vx-dot orange" />Profit</span>}
              {win && len > 0 && <span className="vx-muted">Showing {visible.length} of {len} periods · Ctrl+scroll to zoom · Shift+scroll to slide</span>}
            </div>
            {!cols.date ? (
              <div className="vx-empty">This dataset has no date column, so a trend cannot be drawn.</div>
            ) : !visible.length ? (
              <div className="vx-empty">No records for the selected range / filters.</div>
            ) : (
              <>
                <div className="vx-chart-box">
                  <TrendChart data={visible} selectedKey={selectedKey} onSelect={(k) => setSelectedKey((c) => (c === k ? null : k))} showProfit={Boolean(cols.profit)} />
                </div>
                {len > 3 && win && <RangeSlider data={series} start={win[0]} end={win[1]} onChange={(s, e) => setWin([s, e])} />}
                {selected && (
                  <div className="vx-focus-detail">
                    <div><span>Period</span><b>{selected.label}</b></div>
                    <div><span>Sales</span><b>{formatMoney(selected.sales)}</b></div>
                    {cols.profit && <div><span>Profit</span><b>{formatMoney(selected.profit)}</b></div>}
                    {cols.profit && selected.sales > 0 && <div><span>Margin</span><b>{((selected.profit / selected.sales) * 100).toFixed(1)}%</b></div>}
                    <div><span>Records</span><b>{formatNumber(selected.count)}</b></div>
                    <button type="button" className="vx-link" onClick={() => setSelectedKey(null)}>Clear focus</button>
                  </div>
                )}
              </>
            )}
          </section>

          <div className="vx-grid-2">
            <section className="vx-card">
              <div className="vx-card-head"><h3>Sales by Category</h3><FullscreenButton /></div>
              {!cols.category ? <div className="vx-empty">No category column in this dataset.</div>
                : !categoryItems.length ? <div className="vx-empty">No category sales in this range.</div>
                : <DonutChart items={categoryItems} total={categoryTotal} focus={filters.category} onFocus={setFocus("category")} />}
            </section>
            <section className="vx-card">
              <div className="vx-card-head">
                <h3>Top Customers by Sales</h3>
                <div className="vx-card-tools">
                  {customerAll.length > 5 && <button type="button" className="vx-link" onClick={() => setShowAllCust((v) => !v)}>{showAllCust ? "Show top 5" : "Show top 10"}</button>}
                  <FullscreenButton />
                </div>
              </div>
              {!cols.customer ? <div className="vx-empty">No customer column in this dataset.</div>
                : !customerItems.length ? <div className="vx-empty">No customer sales in this range.</div>
                : <TopList items={customerItems} focus={filters.customer} onFocus={setFocus("customer")} total={customerTotal} />}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
