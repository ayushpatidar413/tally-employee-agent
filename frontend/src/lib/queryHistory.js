import { classifyResponse, pickRows } from "../components/dashboard/QueryView.jsx";

const KEY = "vyapar-query-history-v1";
const MAX_ITEMS = 40;
const MAX_ROWS = 300; // keep localStorage small

export function loadQueryHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    return [];
  }
}

export function saveQueryHistory(list) {
  let l = list.slice(0, MAX_ITEMS);
  while (l.length) {
    try {
      localStorage.setItem(KEY, JSON.stringify(l));
      return l;
    } catch (e) {
      l = l.slice(0, Math.floor(l.length / 2)); // quota full -> drop oldest half
    }
  }
  try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ }
  return [];
}

function slimData(data) {
  try {
    const copy = JSON.parse(JSON.stringify(data || {}));
    const r = copy.result;
    if (r && typeof r === "object") {
      if (Array.isArray(r.rows) && r.rows.length > MAX_ROWS) { r.rows = r.rows.slice(0, MAX_ROWS); r.__truncated = true; }
      if (Array.isArray(r.table) && r.table.length > MAX_ROWS) { r.table = r.table.slice(0, MAX_ROWS); r.__truncated = true; }
      if (r.chart_spec?.data?.length > MAX_ROWS) r.chart_spec.data = r.chart_spec.data.slice(0, MAX_ROWS);
    }
    if (copy.chart?.data?.length > MAX_ROWS) copy.chart.data = copy.chart.data.slice(0, MAX_ROWS);
    return copy;
  } catch (e) {
    return data;
  }
}

export function makeQueryEntry({ question, data, datasetId, datasetName, conversationId }) {
  const rows = pickRows(data);
  const spec = data?.result?.chart_spec?.data?.length || data?.chart?.data?.length;
  return {
    id: `q-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    question,
    time: new Date().toISOString(),
    datasetId: datasetId ?? null,
    datasetName: datasetName || data?.dataset?.original_filename || "",
    conversationId: conversationId ?? null,
    kind: classifyResponse(data),
    rowCount: rows.length,
    hasChart: Boolean(spec) || rows.length > 1,
    data: slimData(data),
  };
}
