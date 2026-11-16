export const API =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_URL) ||
  "http://127.0.0.1:8000";
export const RUPEE = "\u20B9";

const NON_NUMERIC_CHARS = /[\u20B9,%\s]|\u00e2\u0082\u00b9|\u00e2\u201a\u00b9/g;
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/* ---------------------------------------------------------- numbers */
export function numericValue(value) {
  if (value === null || value === undefined || value === "") return 0;
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const n = Number(String(value).replace(NON_NUMERIC_CHARS, "").trim());
  return Number.isFinite(n) ? n : 0;
}

export function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "-";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

/** Full Indian grouping, no decimals: ₹1,92,54,393 */
export function formatMoney(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return RUPEE + "0";
  return RUPEE + Math.round(n).toLocaleString("en-IN");
}

/** ₹1.92Cr / ₹19.2L / ₹4.5K */
export function compactMoney(value, digits = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return RUPEE + "0";
  const a = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (a >= 1e7) return `${sign}${RUPEE}${(a / 1e7).toFixed(2)}Cr`;
  if (a >= 1e5) return `${sign}${RUPEE}${(a / 1e5).toFixed(digits)}L`;
  if (a >= 1e3) return `${sign}${RUPEE}${(a / 1e3).toFixed(digits)}K`;
  return `${sign}${RUPEE}${Math.round(a)}`;
}

export function pctChange(current, previous) {
  if (previous === null || previous === undefined || !Number.isFinite(previous) || previous === 0) return null;
  return ((current - previous) / Math.abs(previous)) * 100;
}

/* ------------------------------------------------------------ dates */
export function parseDate(value) {
  if (value === null || value === undefined || value === "") return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  const s = String(value).trim();
  let m = s.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
  m = s.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})/);
  if (m) return new Date(+m[3], +m[2] - 1, +m[1]);
  m = s.match(/^(\d{4})-(\d{2})$/);
  if (m) return new Date(+m[1], +m[2] - 1, 1);
  const t = Date.parse(s);
  return Number.isNaN(t) ? null : new Date(t);
}

export const startOfMonth = (d) => new Date(d.getFullYear(), d.getMonth(), 1);
export const endOfMonth = (d) => new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59, 999);
export const addMonths = (d, n) => new Date(d.getFullYear(), d.getMonth() + n, 1);
export const fmtMonth = (d) => `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
export const monthInputValue = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;

export function fmtClock(value) {
  if (!value) return "";
  const d = new Date(String(value).includes("T") ? value : String(value).replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" }).toUpperCase();
}

export function fmtStamp(value) {
  if (!value) return "";
  const d = new Date(String(value).includes("T") ? value : String(value).replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return String(value);
  return `${d.getDate()} ${MONTHS[d.getMonth()]}, ${fmtClock(d)}`;
}

/* ---------------------------------------------------------- columns */
const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");

/** Finds the best column for a list of aliases (priority = alias order). */
export function findColumn(columns, aliases, exclude = null) {
  const list = (columns || [])
    .map((c) => [c, norm(c)])
    .filter(([, n]) => !(exclude && exclude.test(n)));
  for (const a of aliases) {
    const hit =
      list.find(([, n]) => n === a) ||
      list.find(([, n]) => n.endsWith(a) || n.startsWith(a)) ||
      (a.length >= 5 ? list.find(([, n]) => n.includes(a)) : null);
    if (hit) return hit[0];
  }
  return "";
}

export function isNumericColumn(rows, column) {
  const values = rows
    .slice(0, 500)
    .map((row) => row?.[column])
    .filter((v) => v !== null && v !== undefined && v !== "");
  if (!values.length) return false;
  const ok = values.filter((v) => {
    const cleaned = String(v).replace(NON_NUMERIC_CHARS, "");
    return cleaned !== "" && Number.isFinite(Number(cleaned));
  });
  return ok.length / values.length >= 0.6;
}

export function getColumns(rows, dataset) {
  if (rows.length) return Object.keys(rows[0]);
  if (dataset?.columnNames?.length) return dataset.columnNames;
  const schema = dataset?.schema;
  if (Array.isArray(schema)) {
    return schema
      .map((i) => (typeof i === "string" ? i : i?.name || i?.column || i?.source_column))
      .filter(Boolean);
  }
  return [];
}

export function normalizeDataset(item) {
  const dataset = item?.dataset || item || {};
  const rawColumns = Array.isArray(dataset.columns) ? dataset.columns : [];
  return {
    id: dataset.id ?? null,
    name: dataset.original_filename || dataset.filename || dataset.file_name || dataset.name || `Dataset ${dataset.id ?? ""}`,
    type: dataset.data_type || dataset.dataset_type || dataset.type || "custom",
    fileType: dataset.file_type || "",
    stored_filename: dataset.stored_filename || null,
    original_filename: dataset.original_filename || null,
    rows: Number(dataset.row_count ?? dataset.rows ?? dataset.total_rows ?? 0) || 0,
    columns: Number(dataset.column_count ?? dataset.columns_count ?? rawColumns.length ?? 0) || 0,
    schema: dataset.schema || {},
    columnNames: rawColumns.map((c) => (typeof c === "string" ? c : c?.name || "")).filter(Boolean),
    status: dataset.status || "SUCCESS",
    uploaded_at: dataset.uploaded_at || null,
    file_size: Number(dataset.file_size || 0),
    raw: item,
  };
}

// Explicit non-currency measures take priority over broad words such as "total".
// Example: "Total Quantity" is a unit count, not money.
const NON_MONEY_WORDS =
  /\b(quantity|qty|units?|count|number|rows?|records?|transactions?|invoices?|customers?|categories?|category|products?\s*count|days?|hours?|weeks?|months?|years?|score|percentage|percent|pct|rate|margin|share)\b/i;
const MONEY_WORDS = /amount|price|sales|profit|cost|discount|gst|tax|revenue|value|turnover|payment|expense|income|commission|average\s*ticket|ticket\s*size/i;

export function formatReportValue(value, column = "") {
  if (value === null || value === undefined || value === "") return "\u2014";
  const name = String(column);

  // A decrease is a positive magnitude; display its meaning explicitly.
  if (/percent(?:age)?[_\s-]?(?:decreased|decrease|declined|drop)/i.test(name)) {
    const p = Number(value);
    if (Number.isFinite(p)) return `${Math.abs(p).toFixed(2)}% decrease`;
  }

  if (/pct[_\s-]?change|percentage[_\s-]?change|percent|change\s*%/i.test(name)) {
    const p = Number(value);
    if (Number.isFinite(p)) return p > 0 ? `+${p.toFixed(2)}%` : p < 0 ? `-${Math.abs(p).toFixed(2)}%` : "0.00%";
  }
  if (/(pct|percent|percentage|contribution|gst[_\s-]?rate|share\s*%|margin)/i.test(name)) {
    const p = Number(value);
    if (Number.isFinite(p)) return `${p.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
  }
  // Never render a rupee symbol for quantities/counts, even if the header
  // contains a broad word such as "Total" (e.g. "Total Quantity").
  if (!NON_MONEY_WORDS.test(name) && MONEY_WORDS.test(name)) {
    const n = typeof value === "number" ? value : /^[+-]?[\d,]+(?:\.\d+)?$/.test(String(value).trim()) ? Number(String(value).replace(/,/g, "")) : NaN;
    if (Number.isFinite(n)) return RUPEE + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (typeof value === "number") return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  return String(value);
}

/* ------------------------------------------------------------ misc */
export function downloadCsv(filename, rows) {
  if (!rows?.length) return;
  const cols = Object.keys(rows[0]);
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const csv = [cols.map(esc).join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good Morning" : h < 17 ? "Good Afternoon" : "Good Evening";
}
