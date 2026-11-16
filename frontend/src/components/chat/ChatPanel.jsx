import { useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Bot, Download, History, Maximize2, MessageSquare, Minimize2, Paperclip, Plus, Send, Trash2, User } from "lucide-react";
import { API, downloadCsv, fmtClock, fmtStamp, formatReportValue } from "../../lib/helpers.js";
import "./ChatPanelHistory.css";

const COLORS = ["#2563eb", "#f97316", "#10b981", "#8b5cf6"];

/* ---------------------------------------------- tiny markdown renderer */
function inline(text) {
  return String(text).split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    p.startsWith("**") && p.endsWith("**") && p.length > 4 ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>
  );
}

function parseBlocks(text) {
  const lines = String(text || "").split("\n");
  const blocks = [];
  const isList = (l) => /^\s*[-*]\s+/.test(l);
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim().startsWith("|")) {
      const tbl = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) { tbl.push(lines[i]); i += 1; }
      blocks.push({ type: "table", lines: tbl });
    } else if (isList(line)) {
      const items = [];
      while (i < lines.length && isList(lines[i])) { items.push(lines[i].replace(/^\s*[-*]\s+/, "")); i += 1; }
      blocks.push({ type: "list", items });
    } else if (line.trim() === "") {
      i += 1;
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() !== "" && !lines[i].trim().startsWith("|") && !isList(lines[i])) { para.push(lines[i]); i += 1; }
      blocks.push({ type: "p", text: para.join("\n") });
    }
  }
  return blocks;
}

function RichText({ text, hideTables }) {
  const blocks = useMemo(() => parseBlocks(text), [text]);
  return (
    <div className="vx-richtext">
      {blocks.map((b, i) => {
        if (b.type === "p") return <p key={i}>{inline(b.text)}</p>;
        if (b.type === "list") return <ul key={i}>{b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}</ul>;
        if (hideTables) return null;
        const rows = b.lines
          .map((l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()))
          .filter((cells) => !cells.every((c) => /^:?-{2,}:?$/.test(c)));
        if (!rows.length) return null;
        return (
          <div className="vx-md-table" key={i}>
            <table>
              <thead><tr>{rows[0].map((c, j) => <th key={j}>{inline(c)}</th>)}</tr></thead>
              <tbody>{rows.slice(1).map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{inline(c)}</td>)}</tr>)}</tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}

/* --------------------------------------------------- result table/chart */
function ResultTable({ rows }) {
  const [all, setAll] = useState(true);

  const cols = useMemo(
    () => [...new Set(rows.slice(0, 50).flatMap((r) => Object.keys(r || {})))],
    [rows]
  );

  const shown = all ? rows.slice(0, 200) : rows.slice(0, 8);

  console.log(
    "RESULT TABLE RENDER DEBUG =",
    JSON.stringify({
      rowsLength: rows?.length,
      columns: cols,
      shownLength: shown.length,
      firstRow: rows?.[0],
      firstRowValues: cols.map((c) => rows?.[0]?.[c]),
    }, null, 2)
  );

  return (
    <div className="vx-result-table">
      <div className="vx-md-table">
        <table>
          <thead>
            <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c}>{formatReportValue(r[c], [c, r.Part, r.Answer].filter(Boolean).join(" "))}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length > 8 && (
        <button
          type="button"
          className="vx-link"
          onClick={() => setAll((v) => !v)}
        >
          {all ? "Show fewer rows" : `Show all ${Math.min(rows.length, 200)} rows`}
        </button>
      )}
    </div>
  );
}

function PartyTypeProductReport({ rich }) {
  const [selectedParty, setSelectedParty] = useState("All");

  const partytypes = rich?.uniquePartytypes || [];
  const partySales = rich?.partytypeSalesRanking || [];
  const productSales = rich?.partytypeProductSales || [];

  const visibleProducts = useMemo(() => {
    const filtered = selectedParty === "All"
      ? productSales
      : productSales.filter((row) => row.PartyType === selectedParty);

    return [...filtered].sort((a, b) => {
      const partyCompare = String(a.PartyType).localeCompare(String(b.PartyType));
      if (selectedParty === "All" && partyCompare !== 0) return partyCompare;
      return Number(b["Total Sales"] || 0) - Number(a["Total Sales"] || 0);
    });
  }, [productSales, selectedParty]);

  const money = (value) =>
    typeof value === "number"
      ? `\u20B9${value.toLocaleString("en-IN", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}`
      : value ?? "\u2014";

  if (!partytypes.length && !productSales.length) return null;

  return (
    <div className="vx-party-report">
      {partytypes.length > 0 && (
        <section className="vx-party-report-section">
          <h3>Unique PartyTypes ({partytypes.length})</h3>
          <div className="vx-party-chips">
            {partytypes.map((party) => (
              <span className="vx-party-chip" key={party}>{party}</span>
            ))}
          </div>
        </section>
      )}

      {partySales.length > 0 && (
        <section className="vx-party-report-section">
          <h3>PartyType Sales Summary</h3>
          <div className="vx-md-table">
            <table>
              <thead>
                <tr><th>PartyType</th><th>Total Sales</th></tr>
              </thead>
              <tbody>
                {partySales.map((row) => (
                  <tr key={row.PartyType}>
                    <td>{row.PartyType}</td>
                    <td>{money(row["Total Sales"])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {productSales.length > 0 && (
        <section className="vx-party-report-section">
          <h3>PartyType-wise Product Sales ({productSales.length} combinations)</h3>

          <label className="vx-party-filter">
            Filter PartyType
            <select
              value={selectedParty}
              onChange={(event) => setSelectedParty(event.target.value)}
            >
              <option value="All">All PartyTypes</option>
              {partytypes.map((party) => (
                <option key={party} value={party}>{party}</option>
              ))}
            </select>
          </label>

          <div className="vx-md-table">
            <table>
              <thead>
                <tr><th>PartyType</th><th>Product</th><th>Total Sales</th></tr>
              </thead>
              <tbody>
                {visibleProducts.map((row, index) => (
                  <tr key={`${row.PartyType}-${row.Product}-${index}`}>
                    <td>{row.PartyType}</td>
                    <td>{row.Product}</td>
                    <td>{money(row["Total Sales"])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="vx-party-report-count">
            Showing {visibleProducts.length} of {productSales.length} combinations
          </p>
        </section>
      )}
    </div>
  );
}

function ResultChart({ spec }) {
  const [type, setType] = useState(spec.type === "line" ? "line" : "bar");
  const data = useMemo(() => (spec.data || []).slice(0, 30), [spec]);
  const xKey = spec.x || spec.x_field || spec.group_by || "label";
  const series = useMemo(() => {
    const first = data[0] || {};
    const named = (spec.series || []).map((s) => (typeof s === "string" ? s : s.key || s.field || s.column)).filter((k) => k && typeof first[k] === "number");
    if (named.length) return named.slice(0, 3);
    return Object.keys(first).filter((k) => k !== xKey && typeof first[k] === "number" && !/share|change|rank/i.test(k)).slice(0, 3);
  }, [spec, data, xKey]);
  if (data.length < 2 || !series.length) return null;
  const points = data.map((d, i) => ({ ...d, __x: String(d[xKey] ?? d.label ?? d.period ?? `#${i + 1}`) }));
  const fmt = (v) => (Math.abs(v) >= 1e7 ? `${(v / 1e7).toFixed(1)}Cr` : Math.abs(v) >= 1e5 ? `${(v / 1e5).toFixed(1)}L` : Math.abs(v) >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : String(v));
  const Chart = type === "line" ? LineChart : BarChart;
  return (
    <div className="vx-result-chart">
      <div className="vx-result-chart-head">
        <strong>{spec.title && spec.title.length < 60 ? spec.title : "Chart"}</strong>
        <div className="vx-seg">
          <button type="button" className={type === "bar" ? "on" : ""} onClick={() => setType("bar")}>Bar</button>
          <button type="button" className={type === "line" ? "on" : ""} onClick={() => setType("line")}>Line</button>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <Chart data={points} margin={{ top: 6, right: 6, left: -8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="currentColor" strokeOpacity={0.12} />
          <XAxis dataKey="__x" tick={{ fontSize: 10, fill: "currentColor", fillOpacity: 0.65 }} tickLine={false} interval={0} height={points.length > 6 ? 46 : 24} angle={points.length > 6 ? -30 : 0} textAnchor={points.length > 6 ? "end" : "middle"} />
          <YAxis tick={{ fontSize: 10, fill: "currentColor", fillOpacity: 0.65 }} tickLine={false} axisLine={false} tickFormatter={fmt} width={48} />
          <Tooltip formatter={(v) => (typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : v)} cursor={{ fill: "rgba(59,130,246,0.08)" }} />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
          {series.map((k, i) => type === "line"
            ? <Line key={k} type="monotone" dataKey={k} stroke={COLORS[i % 4]} strokeWidth={2.4} dot={{ r: 3 }} activeDot={{ r: 5 }} />
            : <Bar key={k} dataKey={k} fill={COLORS[i % 4]} radius={[4, 4, 0, 0]} maxBarSize={34} />)}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}

const partyReportStyles = `
.vx-party-report { display: grid; gap: 18px; margin-top: 14px; min-width: 0; }
.vx-party-report-section { min-width: 0; }
.vx-party-report-section h3 { margin: 0 0 10px; font-size: 0.98rem; font-weight: 750; }
.vx-party-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.vx-party-chip { padding: 7px 11px; border: 1px solid var(--vx-border, #dbe3ee); border-radius: 999px; font-size: 0.84rem; }
.vx-party-filter { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 10px 0; font-size: 0.85rem; }
.vx-party-filter select { max-width: 100%; padding: 7px 10px; border: 1px solid var(--vx-border, #dbe3ee); border-radius: 8px; background: var(--vx-card, white); color: inherit; }
.vx-party-report-count { margin: 8px 0 0; font-size: 0.78rem; opacity: 0.7; }
.vx-party-report .vx-md-table { max-width: 100%; overflow-x: auto; }
.vx-party-report table { width: 100%; border-collapse: collapse; }
.vx-party-report th, .vx-party-report td { padding: 9px 11px; text-align: left; border-bottom: 1px solid var(--vx-border, #e5e7eb); white-space: normal; }
.vx-party-report th { font-size: 0.8rem; font-weight: 750; }
.vx-party-report td { font-size: 0.85rem; }
`;

/* ------------------------------------------------------------- message */
function Message({ m }) {
  useEffect(() => {
    const styleId = "vx-party-report-styles";
    if (!document.getElementById(styleId)) {
      const style = document.createElement("style");
      style.id = styleId;
      style.textContent = partyReportStyles;
      document.head.appendChild(style);
    }
  }, []);

  const isUser = m.role === "user";
  const rich = m.rich;
  console.log(
    "CHAT PANEL TABLE DEBUG =",
    JSON.stringify(
      {
        question: m.text,
        richExists: Boolean(rich),
        rows: rich?.rows,
        rowsLength: rich?.rows?.length,
        firstRow: rich?.rows?.[0],
        hasRows: Boolean(rich?.rows?.length),
      },
      null,
      2
    )
  );
  const hasRows = Boolean(rich && rich.rows && rich.rows.length);
  const hasTransactions = Boolean(rich?.detailRows?.length);
  const isPaymentShare = Boolean(
    rich?.rows?.some(
      (row) =>
        Object.prototype.hasOwnProperty.call(row || {}, "Payment Mode") &&
        Object.prototype.hasOwnProperty.call(row || {}, "Revenue Share %")
    )
  );
  const chartSpec = useMemo(() => {
    if (rich?.chart?.data?.length) return rich.chart;

    const rows = Array.isArray(rich?.rows) ? rich.rows : [];
    if (rows.length < 2) return null;

    const first = rows[0] || {};
    const keys = Object.keys(first);

    const xKey =
      keys.find((k) =>
        typeof first[k] === "string" &&
        /product|month|category|party|name/i.test(k)
      ) ||
      keys.find((k) => typeof first[k] === "string");

    const metricKey = keys.find(
      (k) =>
        typeof first[k] === "number" &&
        !/rank|id/i.test(k)
    );

    if (!xKey || !metricKey) return null;

    return {
      type: "bar",
      title: `${metricKey} by ${xKey}`,
      x: xKey,
      series: [{ key: metricKey, label: metricKey }],
      data: rows,
    };
  }, [rich]);

  const hasChart = Boolean(chartSpec?.data?.length);
  const [resultMode, setResultMode] = useState("answer");
  const [reportView, setReportView] = useState("summary");
  console.log(
    "RESULT MODE DEBUG =",
    JSON.stringify({
      resultMode,
      hasRows,
      rowsLength: rich?.rows?.length,
      hasChart,
    })
  );
  const safeFilename = String(m.text || "query-report").slice(0, 48).replace(/[^\w-]+/g, "_");
  return (
    <div className={`vx-msg ${isUser ? "user" : "ai"} ${m.error ? "error" : ""}`}>
      <div className="vx-msg-meta">
        <span>{isUser ? "You" : "AI Assistant"}</span>
        {!isUser && (m.engine || rich?.engine) && <span title={m.engineDiagnostic || rich?.engineDiagnostic || "Engine used for this response"} style={{ fontSize: "0.72rem", fontWeight: 700, color: (m.engine || rich?.engine) === "legacy" ? "#d97706" : (m.engine || rich?.engine) === "semantic-unavailable" ? "#dc2626" : "#16a34a" }}>{(m.engine || rich?.engine) === "legacy" ? "Legacy engine" : (m.engine || rich?.engine) === "semantic-unavailable" ? "AI engine unavailable" : (m.engine || rich?.engine) === "semantic-deterministic" ? "AI engine . verified calculation" : "AI engine"}</span>}
        <time>{fmtClock(m.time)}</time>
      </div>
      <div className="vx-msg-row">
        {!isUser && <div className="vx-avatar ai"><Bot size={20} /></div>}
        <div className="vx-bubble">
          
        {isUser ? (
          m.text ? (
            <div className="vx-user-question">{m.text}</div>
          ) : null
        ) : (
        !isUser && m.text ? (
            <RichText text={m.text} hideTables={hasRows} />
          ) : null
        )}


          {!isUser && rich && (hasRows || hasChart || rich.downloadUrl) && (
            <div className="vx-saved-result-tools" role="group" aria-label="Saved answer result views">
              <button type="button" className={resultMode === "answer" ? "active" : ""} onClick={() => setResultMode("answer")}>Answer</button>
              {hasRows && (
                <button
                  type="button"
                  className={resultMode === "table" ? "active" : ""}
                  onClick={() => {
                    console.log("TABLE BUTTON CLICKED");
                    setResultMode("table");
                  }}
                >
                  Table
                </button>
              )}
              {hasChart && <button type="button" className={resultMode === "chart" ? "active" : ""} onClick={() => setResultMode("chart")}>Chart</button>}
              {(hasRows || rich.downloadUrl) && <button type="button" className={resultMode === "report" ? "active" : ""} onClick={() => setResultMode("report")}>Report</button>}
            </div>
          )}

          {/* Show compact result table directly inside Answer */}
          {resultMode === "answer" && hasRows && rich.rows.length <= 10 && (
            <div className="vx-answer-inline-table">
              {rich?.partytypeProductSales?.length > 0
                ? <PartyTypeProductReport rich={rich} />
                : <ResultTable rows={rich.rows} />
              }
            </div>
          )}

          {resultMode === "answer" && hasRows && rich.rows.length > 10 && (
            <p className="vx-answer-table-hint">
              {rich.rows.length} records are available. Open Table to view all records.
            </p>
          )}

          {resultMode === "table" && hasRows && (
            rich?.partytypeProductSales?.length > 0
              ? <PartyTypeProductReport rich={rich} />
              : <ResultTable rows={rich.rows} />
          )}
          {resultMode === "chart" && hasChart && <ResultChart spec={chartSpec} />}
          {resultMode === "report" && (
            <div className="vx-saved-report">
              {(hasRows || hasTransactions) && (
                <div className="vx-saved-result-tools" role="group" aria-label="Data report views">
                  {hasRows && !isPaymentShare && (
                    <button
                      type="button"
                      className={reportView === "summary" ? "active" : ""}
                      onClick={() => setReportView("summary")}
                    >
                      Daily Summary
                    </button>
                  )}
                  {hasTransactions && (
                    <button type="button" className={reportView === "transactions" ? "active" : ""}
                      onClick={() => setReportView("transactions")}>
                      Individual Transactions ({rich.detailRows.length})
                    </button>
                  )}
                </div>
              )}

              {reportView === "summary" && hasRows && (
                rich?.partytypeProductSales?.length > 0
                  ? <PartyTypeProductReport rich={rich} />
                  : <ResultTable rows={rich.rows} />
              )}

              {reportView === "transactions" && hasTransactions && (
                <ResultTable rows={rich.detailRows} />
              )}

              {!isPaymentShare &&
                ((reportView === "transactions" && hasTransactions) ||
                (reportView === "summary" && hasRows)) && (
                <button type="button" className="vx-download"
                  onClick={() => downloadCsv(
                    `${safeFilename}-${reportView}.csv`,
                    reportView === "transactions" ? rich.detailRows : rich.rows
                  )}>
                  <Download size={14} />
                  Download {reportView === "transactions" ? "transactions" : "daily summary"} CSV
                </button>
              )}

              {rich?.downloadUrl && !isPaymentShare && (
                <a
                  className="vx-download"
                  href={`${API}${rich.downloadUrl}`}
                  download
                >
                  <Download size={14} /> Download report file
                </a>
              )}
              {!hasRows && !hasTransactions && !rich?.downloadUrl && <p>No table or downloadable report was saved for this answer.</p>}
            </div>
          )}

          {rich && (rich.period || rich.source) && (
            <div className="vx-source">
              {rich.source && <span>Source: {rich.source}</span>}
              {rich.period && <span>Period: {rich.period}</span>}
            </div>
          )}
        </div>
        {isUser && <div className="vx-avatar user"><User size={19} /></div>}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- panel */
const SUGGESTIONS = [
  "Which is my hero product and why?",
  "Show total sales and profit month wise",
  "Top 5 customers by sales",
  "Which category is growing?",
  "Compare July and June sales",
];

export default function ChatPanel({
  mode = "panel", messages, loading, onSend, onUpload, datasetName,
  conversations, activeId, loadingConversations, onOpen, onDelete, onNew, onRefreshHistory,
  expanded, onToggleExpand,
}) {
  const [tab, setTab] = useState("chat");
  const [text, setText] = useState("");
  const scrollRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => {
    if (tab !== "chat" || !scrollRef.current) return;
    scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, loading, tab]);

  const submit = (e) => {
    e.preventDefault();

    const q = text.trim();

    console.log("========== CHAT INPUT DEBUG ==========");
    console.log("INPUT STATE:", JSON.stringify(text));
    console.log("INPUT LENGTH:", text.length);
    console.log("SUBMITTED QUERY:", JSON.stringify(q));
    console.log("SUBMITTED LENGTH:", q.length);
    console.log("======================================");

    if (!q || loading) return;

    setText("");
    onSend(q);
  };

  return (
    <div className={`vx-chatpanel ${mode}`}>
      <div className="vx-chat-tabs">
        <button type="button" className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>
          <MessageSquare size={18} /> Chat with your data
        </button>
        <button type="button" className={tab === "history" ? "active" : ""} onClick={() => { setTab("history"); onRefreshHistory?.(); }}>
          <History size={18} /> Previous Chats
        </button>
        {mode === "panel" && (
          <button type="button" className="vx-chat-expand" onClick={onToggleExpand} title={expanded ? "Collapse chat" : "Expand chat"} aria-label="Expand chat">
            {expanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
          </button>
        )}
      </div>

      {tab === "chat" ? (
        <>
          <div className="vx-chat-dataset" title={datasetName}>
            <span className="vx-live-dot" />
            <span>{datasetName ? `Chatting with: ${datasetName}` : "Upload a dataset to start"}</span>
            <button type="button" className="vx-link" onClick={onNew}><Plus size={13} /> New chat</button>
          </div>

          <div className="vx-chat-scroll" ref={scrollRef}>
            {messages.length === 0 && (
              <div className="vx-chat-empty">
                <div className="vx-chat-empty-icon"><Bot size={30} /></div>
                <h3>Ask anything about your business data</h3>
                <p>Spelling mistakes, Hinglish or short follow-ups are fine - I use the uploaded file and this conversation.</p>
                <div className="vx-suggest">
                  {SUGGESTIONS.map((s) => <button type="button" key={s} onClick={() => onSend(s)} disabled={loading}>{s}</button>)}
                </div>
              </div>
            )}
            {messages.map((m) => <Message key={m.id} m={m} />)}
            {loading && (
              <div className="vx-msg ai">
                <div className="vx-msg-row">
                  <div className="vx-avatar ai"><Bot size={20} /></div>
                  <div className="vx-bubble vx-typing" aria-label="Assistant is thinking"><i /><i /><i /></div>
                </div>
              </div>
            )}
          </div>

          <form className="vx-chat-input" onSubmit={submit}>
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Ask anything about your business data..."
              aria-label="Ask a question"
            />
            <input ref={fileRef} type="file" hidden accept=".csv,.xlsx,.xls,.json,.pdf" onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); e.target.value = ""; }} />
            <button type="button" className="vx-attach" onClick={() => fileRef.current?.click()} title="Upload a file" aria-label="Upload a file"><Paperclip size={19} /></button>
            <button type="submit" className="vx-send" disabled={loading || !text.trim()} aria-label="Send"><Send size={19} /></button>
          </form>
        </>
      ) : (
        <div className="vx-chat-history">
          <button type="button" className="vx-newchat" onClick={() => { onNew(); setTab("chat"); }}><Plus size={16} /> Start a new chat</button>
          {loadingConversations && !conversations.length ? <div className="vx-empty">Loading conversations...</div>
            : !conversations.length ? <div className="vx-empty">No saved chats yet. Ask your first question to create one.</div>
            : conversations.map((c) => {
              const id = c.conversation_id;
              return (
                <div key={id} className={`vx-hist-item ${String(id) === String(activeId) ? "active" : ""}`}>
                  <button type="button" className="vx-hist-open" onClick={() => { onOpen(id); setTab("chat"); }}>
                    <MessageSquare size={16} />
                    <span>
                      <strong>{c.title || "New Chat"}</strong>
                      <small>{fmtStamp(c.updated_at)}</small>
                    </span>
                  </button>
                  <button type="button" className="vx-hist-del" onClick={() => onDelete(id)} title="Delete chat" aria-label="Delete chat"><Trash2 size={15} /></button>
                </div>
              );
            })}
        </div>
      )}
    </div>
  );
}
