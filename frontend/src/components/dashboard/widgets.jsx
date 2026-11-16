import { useEffect, useRef, useState } from "react";
import { Bar, Cell, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowDownRight, ArrowUpRight, Calendar, ChevronDown, Filter, X } from "lucide-react";
import { RUPEE, compactMoney, formatMoney, fmtMonth, monthInputValue } from "../../lib/helpers.js";

/* ------------------------------------------------------------ utils */
function useOutsideClose(ref, open, close) {
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) close(); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [ref, open, close]);
}

const axisMoney = (v) => compactMoney(v, 1);

/* -------------------------------------------------------------- KPI */
export function KpiCard({ icon: Icon, tone, label, value, delta, note }) {
  const hasDelta = delta !== undefined;
  const dir = delta === null || delta === undefined ? "flat" : delta >= 0 ? "up" : "down";
  return (
    <div className={`vx-kpi vx-tone-${tone}`}>
      <div className="vx-kpi-icon"><Icon size={22} /></div>
      <div className="vx-kpi-body">
        <span className="vx-kpi-label">{label}</span>
        <strong className="vx-kpi-value" title={String(value)}>{value}</strong>
        {hasDelta && (
          <span className={`vx-kpi-delta ${dir}`}>
            {dir === "flat" ? "\u2014" : (
              <>
                {dir === "up" ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                {Math.abs(delta).toFixed(1)}%
              </>
            )}
          </span>
        )}
        <small className="vx-kpi-note">{note}</small>
      </div>
    </div>
  );
}

/* ------------------------------------------------------ trend chart */
function TrendTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0].payload;
  const margin = p.sales ? (p.profit / p.sales) * 100 : null;
  return (
    <div className="vx-tip">
      <strong>{p.label}</strong>
      <div><i className="vx-dot blue" />Sales: <b>{compactMoney(p.sales)}</b> <small>({formatMoney(p.sales)})</small></div>
      {p.hasProfit && <div><i className="vx-dot orange" />Profit: <b>{compactMoney(p.profit)}</b></div>}
      {p.hasProfit && margin !== null && <div className="vx-tip-muted">Margin {margin.toFixed(1)}%</div>}
      <div className="vx-tip-muted">{p.count} records · click bar to focus</div>
    </div>
  );
}

export function TrendChart({ data, selectedKey, onSelect, showProfit }) {
  const tilt = data.length > 8;
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={data} margin={{ top: 12, right: 14, left: 2, bottom: 4 }}>
        <defs>
          <linearGradient id="vxSalesGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" />
            <stop offset="100%" stopColor="#2f4fe0" />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="currentColor" strokeOpacity={0.12} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: "currentColor", fillOpacity: 0.65 }}
          tickLine={false}
          axisLine={{ stroke: "currentColor", strokeOpacity: 0.15 }}
          interval={data.length > 24 ? "preserveStartEnd" : 0}
          angle={tilt ? -35 : 0}
          textAnchor={tilt ? "end" : "middle"}
          height={tilt ? 58 : 30}
        />
        <YAxis
          tickFormatter={axisMoney}
          tick={{ fontSize: 11, fill: "currentColor", fillOpacity: 0.65 }}
          tickLine={false}
          axisLine={false}
          width={64}
        />
        <Tooltip content={<TrendTooltip />} cursor={{ fill: "rgba(59,130,246,0.10)" }} />
        <Bar
          dataKey="sales"
          name="Sales"
          radius={[5, 5, 0, 0]}
          maxBarSize={40}
          cursor="pointer"
          animationDuration={450}
          onClick={(d) => onSelect((d && (d.payload ? d.payload.key : d.key)) ?? null)}
        >
          {data.map((d) => (
            <Cell key={d.key} fill={selectedKey === d.key ? "#1e3a8a" : "url(#vxSalesGrad)"} fillOpacity={selectedKey && selectedKey !== d.key ? 0.55 : 1} />
          ))}
        </Bar>
        {showProfit && (
          <Line
            type="monotone"
            dataKey="profit"
            name="Profit"
            stroke="#f97316"
            strokeWidth={2.6}
            dot={{ r: 3, fill: "#f97316", strokeWidth: 0 }}
            activeDot={{ r: 6 }}
            animationDuration={450}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/* ---------------------------------------------- draggable range slider */
export function RangeSlider({ data, start, end, onChange, minSize = 3 }) {
  const ref = useRef(null);
  const drag = useRef(null);
  const total = data.length;
  const max = Math.max(1, ...data.map((d) => d.sales || 0));
  const min = Math.min(minSize, total);

  const down = (mode) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    drag.current = { mode, x: e.clientX, start, end };
    ref.current.setPointerCapture(e.pointerId);
  };
  const move = (e) => {
    const d = drag.current;
    if (!d || !ref.current) return;
    const step = ref.current.getBoundingClientRect().width / Math.max(1, total);
    const delta = Math.round((e.clientX - d.x) / step);
    let s = d.start;
    let en = d.end;
    if (d.mode === "pan") {
      const size = d.end - d.start;
      s = Math.min(total - 1 - size, Math.max(0, d.start + delta));
      en = s + size;
    } else if (d.mode === "left") {
      s = Math.min(d.end - (min - 1), Math.max(0, d.start + delta));
    } else {
      en = Math.max(d.start + (min - 1), Math.min(total - 1, d.end + delta));
    }
    if (s !== start || en !== end) onChange(s, en);
  };
  const up = (e) => {
    drag.current = null;
    try { ref.current.releasePointerCapture(e.pointerId); } catch (err) { /* ignore */ }
  };
  const trackClick = (e) => {
    if (!e.target.dataset || !e.target.dataset.track) return;
    const r = ref.current.getBoundingClientRect();
    const idx = Math.floor(((e.clientX - r.left) / r.width) * total);
    const size = end - start;
    const s = Math.min(total - 1 - size, Math.max(0, idx - Math.floor(size / 2)));
    onChange(s, s + size);
  };

  return (
    <div
      className="vx-slider"
      ref={ref}
      data-track="1"
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={up}
      onClick={trackClick}
      role="group"
      aria-label="Drag to slide or resize the visible period"
    >
      <div className="vx-slider-bars" data-track="1">
        {data.map((d) => (
          <i key={d.key} data-track="1" style={{ height: `${Math.max(8, ((d.sales || 0) / max) * 100)}%` }} />
        ))}
      </div>
      <div
        className="vx-slider-window"
        style={{ left: `${(start / total) * 100}%`, width: `${((end - start + 1) / total) * 100}%` }}
        onPointerDown={down("pan")}
      >
        <span className="vx-slider-handle left" onPointerDown={down("left")} />
        <span className="vx-slider-handle right" onPointerDown={down("right")} />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ donut */
const PALETTE = ["#2f7cf6", "#ff7a2f", "#ffc233", "#9aa5d6", "#ff6b57", "#a24be0"];

function arcPath(cx, cy, r0, r1, a0, a1) {
  const end = Math.min(a1, a0 + Math.PI * 2 - 0.0001);
  const large = end - a0 > Math.PI ? 1 : 0;
  const p = (r, a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const [x0, y0] = p(r1, a0);
  const [x1, y1] = p(r1, end);
  const [x2, y2] = p(r0, end);
  const [x3, y3] = p(r0, a0);
  return `M${x0} ${y0}A${r1} ${r1} 0 ${large} 1 ${x1} ${y1}L${x2} ${y2}A${r0} ${r0} 0 ${large} 0 ${x3} ${y3}Z`;
}

export function DonutChart({ items, total, focus, onFocus }) {
  const [hover, setHover] = useState(null);
  const sum = items.reduce((t, i) => t + i.value, 0) || 1;
  let angle = -Math.PI / 2;
  const slices = items.map((it, idx) => {
    const a0 = angle;
    const a1 = angle + (it.value / sum) * Math.PI * 2;
    angle = a1;
    return { ...it, a0, a1, color: PALETTE[idx % PALETTE.length], pct: (it.value / sum) * 100 };
  });
  const active = hover !== null ? slices[hover] : null;

  return (
    <div className="vx-donut-wrap">
      <div className="vx-donut">
        <svg viewBox="0 0 220 220" role="img" aria-label="Sales by category">
          {slices.map((s, i) => {
            const isHover = hover === i;
            const isFocus = focus && focus === s.label;
            const dim = (focus && focus !== s.label) || (hover !== null && !isHover);
            return (
              <path
                key={s.label}
                d={arcPath(110, 110, 62, isHover || isFocus ? 98 : 92, s.a0, s.a1)}
                fill={s.color}
                opacity={dim ? 0.35 : 1}
                className={`vx-slice ${s.clickable ? "clickable" : ""}`}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                onClick={() => s.clickable && onFocus(isFocus ? "" : s.label)}
              />
            );
          })}
        </svg>
        <div className="vx-donut-center">
          {active ? (
            <>
              <span>{active.label}</span>
              <strong>{compactMoney(active.value)}</strong>
              <small>{active.pct.toFixed(1)}%</small>
            </>
          ) : (
            <>
              <strong>{compactMoney(total)}</strong>
              <small>Total Sales</small>
            </>
          )}
        </div>
      </div>
      <div className="vx-legend">
        {slices.map((s, i) => (
          <button
            type="button"
            key={s.label}
            className={`vx-legend-row ${focus === s.label ? "active" : ""} ${hover === i ? "hover" : ""}`}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            onClick={() => s.clickable && onFocus(focus === s.label ? "" : s.label)}
            title={`${s.label}: ${formatMoney(s.value)}`}
          >
            <i style={{ background: s.color }} />
            <span>{s.label}</span>
            <b>{s.pct.toFixed(1)}%</b>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------- top customers */
export function TopList({ items, focus, onFocus, total }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <div className="vx-toplist">
      {items.map((it, idx) => (
        <button
          type="button"
          key={it.label}
          className={`vx-toprow ${focus === it.label ? "active" : ""}`}
          onClick={() => onFocus(focus === it.label ? "" : it.label)}
          title={`${it.label}: ${formatMoney(it.value)}${total ? ` (${((it.value / total) * 100).toFixed(1)}% of sales)` : ""}`}
        >
          <span className="vx-toprow-name">{it.label}</span>
          <span className="vx-toprow-bar">
            <i style={{ width: `${(it.value / max) * 100}%`, opacity: Math.max(0.45, 1 - idx * 0.1) }} />
          </span>
          <span className="vx-toprow-val">{formatMoney(it.value)}</span>
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------- date range picker */
const PRESETS = [
  ["all", "All time"],
  ["1m", "Latest month"],
  ["3m", "Last 3 months"],
  ["6m", "Last 6 months"],
  ["12m", "Last 12 months"],
  ["ytd", "This year (YTD)"],
];

export function DateRangePicker({ label, preset, setPreset, custom, setCustom, bounds, disabled }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useOutsideClose(ref, open, () => setOpen(false));
  const minV = bounds ? monthInputValue(bounds.min) : undefined;
  const maxV = bounds ? monthInputValue(bounds.max) : undefined;
  const [draft, setDraft] = useState(custom);
  useEffect(() => { if (open) setDraft(custom.from ? custom : { from: minV || "", to: maxV || "" }); }, [open]); // eslint-disable-line

  return (
    <div className="vx-pop" ref={ref}>
      <button type="button" className="vx-select-btn" onClick={() => !disabled && setOpen((v) => !v)} disabled={disabled} aria-expanded={open}>
        <Calendar size={17} />
        <span>{disabled ? "No date column" : label}</span>
        <ChevronDown size={16} />
      </button>
      {open && (
        <div className="vx-popover right">
          <div className="vx-pop-title">Date range</div>
          <div className="vx-preset-list">
            {PRESETS.map(([id, text]) => (
              <button type="button" key={id} className={preset === id ? "active" : ""} onClick={() => { setPreset(id); setOpen(false); }}>
                {text}
              </button>
            ))}
          </div>
          <div className="vx-pop-title">Custom (month to month)</div>
          <div className="vx-custom-range">
            <input type="month" value={draft.from} min={minV} max={maxV} onChange={(e) => setDraft({ ...draft, from: e.target.value })} />
            <span>to</span>
            <input type="month" value={draft.to} min={minV} max={maxV} onChange={(e) => setDraft({ ...draft, to: e.target.value })} />
          </div>
          <button
            type="button"
            className="vx-apply"
            disabled={!draft.from || !draft.to || draft.from > draft.to}
            onClick={() => { setCustom(draft); setPreset("custom"); setOpen(false); }}
          >
            Apply range
          </button>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------ filter popover */
export function FilterPopover({ options, values, setValues, disabled }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useOutsideClose(ref, open, () => setOpen(false));
  const count = Object.values(values).filter(Boolean).length;
  const fields = [
    ["category", "Category"],
    ["customer", "Customer"],
    ["location", "Location"],
  ].filter(([k]) => options[k] && options[k].length);

  return (
    <div className="vx-pop" ref={ref}>
      <button type="button" className="vx-select-btn" onClick={() => setOpen((v) => !v)} disabled={disabled || !fields.length} aria-expanded={open}>
        <Filter size={17} />
        <span>Filters{count ? ` (${count})` : ""}</span>
        <ChevronDown size={16} />
      </button>
      {open && (
        <div className="vx-popover right wide">
          <div className="vx-pop-title">Filter dashboard</div>
          {fields.map(([key, text]) => (
            <label className="vx-field" key={key}>
              <span>{text}</span>
              <select value={values[key]} onChange={(e) => setValues({ ...values, [key]: e.target.value })}>
                <option value="">All</option>
                {options[key].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </label>
          ))}
          <button type="button" className="vx-apply ghost" onClick={() => setValues({ category: "", customer: "", location: "" })}>
            <X size={14} /> Clear all filters
          </button>
        </div>
      )}
    </div>
  );
}

export { fmtMonth, RUPEE };
