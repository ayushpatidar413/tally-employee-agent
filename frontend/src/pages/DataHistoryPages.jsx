import { useMemo, useState } from "react";
import {
  ArrowLeft, BarChart3, Clock, Columns3, Database, Download, FileSpreadsheet, FileText, History,
  MessageSquare, Play, RefreshCw, Search, Sparkles, Table2, Trash2, Upload,
} from "lucide-react";
import { EmptyState, LoadingState, PageHeading } from "../components/common.jsx";
import { QueryView, ChartDeck, ReportTable, deriveChart, pickRows } from "../components/dashboard/QueryView.jsx";
import { API, downloadCsv, fmtStamp, formatNumber } from "../lib/helpers.js";
import "./HistoryInteractive.css";

const SPLIT = /\s[\u2014\u2013-]\s/; // "file.xlsx — Sheet name"

function fileKind(d) {
  const v = String(d?.type || d?.fileType || "").toLowerCase();
  const f = String(d?.name || "").toLowerCase();
  if (v.includes("xls") || /\.xlsx?\b/.test(f)) return "Excel";
  if (v.includes("csv") || f.includes(".csv")) return "CSV";
  if (v.includes("json") || f.includes(".json")) return "JSON";
  if (v.includes("pdf") || f.includes(".pdf")) return "PDF";
  return "Dataset";
}

function fmtDate(raw) {
  if (!raw) return "";
  const date = new Date(raw);
  return Number.isNaN(date.getTime())
    ? String(raw)
    : date.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/* ============================================================= Business Data */
export function DataPage({ datasets, selectedDatasetId, setSelectedDatasetId, onDelete, onUpload, loading }) {
  const [q, setQ] = useState("");

  const groups = useMemo(() => {
    const t = q.trim().toLowerCase();
    const list = t ? datasets.filter((d) => `${d.name} ${d.type}`.toLowerCase().includes(t)) : datasets;
    const map = new Map();
    list.forEach((d) => {
      const parts = String(d.name).split(SPLIT);
      const file = parts.length > 1 ? parts[0].trim() : String(d.name);
      const sheet = parts.length > 1 ? parts.slice(1).join(" - ").trim() : "";
      if (!map.has(file)) map.set(file, []);
      map.get(file).push({ ...d, sheet });
    });
    return [...map.entries()].map(([file, items]) => ({ file, items }));
  }, [datasets, q]);

  const totalRows = datasets.reduce((s, d) => s + (d.rows || 0), 0);
  const totalFiles = new Set(datasets.map((d) => String(d.name).split(SPLIT)[0].trim())).size;

  return (
    <div className="page">
      <PageHeading
        kicker="DATA MANAGEMENT"
        title="Business Data"
        description="Manage the datasets stored in your dynamic business database."
        actions={<button type="button" className="primary-button" onClick={onUpload}><Upload size={17} />Upload Data</button>}
      />

      {datasets.length > 0 && (
        <div className="vxp-stats">
          {[
            { icon: FileSpreadsheet, label: "Files", value: totalFiles },
            { icon: Database, label: "Datasets / sheets", value: datasets.length },
            { icon: Table2, label: "Total records", value: totalRows },
          ].map(({ icon: Icon, label, value }) => (
            <div className="vxp-stat" key={label}>
              <span className="vxp-stat-icon"><Icon size={18} /></span>
              <div><small>{label}</small><strong>{formatNumber(value)}</strong></div>
            </div>
          ))}
        </div>
      )}

      <div className="vxp-search">
        <Search size={17} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search datasets..." aria-label="Search datasets" />
      </div>

      {loading ? <LoadingState /> : !groups.length ? (
        <EmptyState icon={Database} title="No datasets found" text="Upload data to create your first dataset." buttonText="Upload Data" onClick={onUpload} />
      ) : groups.map(({ file, items }) => (
        <section className="vxp-group" key={file}>
          <header className="vxp-group-head">
            <span className="vxp-group-icon"><FileSpreadsheet size={18} /></span>
            <div>
              <h3 title={file}>{file}</h3>
              <small>{items.length} dataset{items.length > 1 ? "s" : ""}</small>
            </div>
          </header>
          <div className="vxp-grid">
            {items.map((d) => {
              const active = Number(selectedDatasetId) === Number(d.id);
              return (
                <article className={`vxp-card ${active ? "active" : ""}`} key={d.id}>
                  <div className="vxp-card-top">
                    <span className="vxp-card-icon"><Database size={18} /></span>
                    <span className="vxp-badge">{d.type}</span>
                    {active && <span className="vxp-badge on">Active</span>}
                  </div>
                  <h4 title={d.sheet || d.name}>{d.sheet || d.name}</h4>
                  <div className="vxp-pills">
                    <span><Table2 size={13} />{formatNumber(d.rows)} rows</span>
                    <span><Columns3 size={13} />{formatNumber(d.columns)} cols</span>
                  </div>
                  {d.uploaded_at && <div className="vxp-date"><Clock size={12} />{fmtDate(d.uploaded_at)}</div>}
                  <div className="vxp-card-actions">
                    <button type="button" className="primary-button small" onClick={() => setSelectedDatasetId(d.id)}><Play size={14} />Use</button>
                    <button type="button" className="danger-icon" onClick={() => onDelete(d.id)} title="Delete dataset" aria-label="Delete dataset"><Trash2 size={16} /></button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

/* ================================================================== History */
function QueryDetail({ entry, initialMode = "all", onBack, onRerun }) {
  const [mode, setMode] = useState(initialMode);
  const { data, question } = entry;
  const rows = useMemo(() => pickRows(data), [data]);
  const r = data?.result || {};
  const spec = r.chart_spec?.data?.length ? r.chart_spec : data?.chart?.data?.length ? data.chart : null;
  const canChart = useMemo(() => Boolean(deriveChart(rows, spec, question)), [rows, spec, question]);
  const fileName = String(question || "report").slice(0, 40).replace(/[^\w]+/g, "_");

  return (
    <div className="vxp-detail">
      <div className="vxp-detail-bar">
        <button type="button" className="vx-select-btn small" onClick={onBack}><ArrowLeft size={15} /> Back to history</button>
        <div className="vx-seg">
          <button type="button" className={mode === "all" ? "on" : ""} onClick={() => setMode("all")}>Full result</button>
          <button type="button" className={mode === "chart" ? "on" : ""} onClick={() => setMode("chart")}>Chart</button>
          <button type="button" className={mode === "report" ? "on" : ""} onClick={() => setMode("report")}>Report</button>
        </div>
        <div className="vxp-detail-actions">
          {rows.length > 0 && <button type="button" className="secondary-button small" onClick={() => downloadCsv(`${fileName}.csv`, rows)}><Download size={14} />CSV</button>}
          {data?.download_url && <a className="secondary-button small" href={`${API}${data.download_url}`} download><Download size={14} />Report file</a>}
          <button type="button" className="secondary-button small" onClick={() => onRerun(question)}><RefreshCw size={14} />Run again</button>
        </div>
      </div>

      {r.__truncated && <p className="vxp-note">Saved copy shows the first 300 rows. Use &quot;Run again&quot; for the complete result.</p>}

      {mode === "all" && <QueryView question={question} data={data} datasetName={entry.datasetName} />}
      {mode !== "all" && <h2 className="vxp-detail-title">{question}</h2>}
      {mode === "chart" && (canChart
        ? <ChartDeck rows={rows} spec={spec} title={question} />
        : <div className="vxp-empty-block"><BarChart3 size={28} /><p>This query has no chartable data. Try &quot;Run again&quot; or open the Report view.</p></div>)}
      {mode === "report" && (rows.length
        ? <ReportTable rows={rows} fileName={fileName} downloadUrl={data?.download_url} />
        : <div className="vxp-empty-block"><FileText size={28} /><p>This query returned a text answer only, so there is no table report.</p></div>)}
    </div>
  );
}

export function HistoryPage({
  datasets, selectedDatasetId, onDelete, onRefresh, onUse,
  queryHistory = [], onRemoveQuery, onClearQueries,
  conversations = [], loadingConversations, onOpenConversation, onDeleteConversation, onRerun,
}) {
  const [tab, setTab] = useState("queries");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [open, setOpen] = useState(null);
  const [openMode, setOpenMode] = useState("all");

  const items = Array.isArray(datasets) ? datasets : [];
  const term = search.trim().toLowerCase();

  /* datasets */
  const filteredDatasets = items.filter((d) => {
    const t = fileKind(d).toLowerCase();
    return (!term || String(d.name).toLowerCase().includes(term) || t.includes(term)) && (typeFilter === "all" || t === typeFilter);
  });
  const totalRows = items.reduce((s, d) => s + (d.rows || 0), 0);
  const totalCols = items.reduce((s, d) => s + (d.columns || 0), 0);

  /* Conversation-first history: individual cards are only for queries without a session. */
  const conversationIds = new Set(conversations.map((c) => String(c.conversation_id)));
  const standaloneQueries = queryHistory.filter((entry) =>
    !entry.conversationId || !conversationIds.has(String(entry.conversationId))
  );
  const filteredQueries = standaloneQueries.filter((entry) =>
    !term || String(entry.question || "").toLowerCase().includes(term)
  );
  const olderChats = conversations.filter((conversation) => {
    if (!term) return true;
    const titleMatches = String(conversation.title || "").toLowerCase().includes(term);
    const questionMatches = queryHistory.some((entry) =>
      String(entry.conversationId) === String(conversation.conversation_id) &&
      String(entry.question || "").toLowerCase().includes(term)
    );
    return titleMatches || questionMatches;
  });

  if (open) {
    return (
      <div className="page history-page">
        <PageHeading kicker="QUERY HISTORY" title="Saved Query" description="Chart, report and answer for this query." />
        <QueryDetail key={`${open.id}-${openMode}`} entry={open} initialMode={openMode} onBack={() => setOpen(null)} onRerun={onRerun} />
      </div>
    );
  }

  const openEntry = (entry, mode) => { setOpenMode(mode); setOpen(entry); };

  return (
    <div className="page history-page">
      <PageHeading
        kicker="HISTORY"
        title="History"
        description="Browse the datasets you have uploaded and the queries you have asked."
        actions={<button type="button" className="secondary-button" onClick={onRefresh}><RefreshCw size={17} />Refresh</button>}
      />

      <div className="vxp-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "queries"} className={tab === "queries" ? "active" : ""} onClick={() => { setTab("queries"); setSearch(""); }}>
          <MessageSquare size={17} />Query History <span className="vxp-count">{standaloneQueries.length + conversations.length}</span>
        </button>
        <button type="button" role="tab" aria-selected={tab === "datasets"} className={tab === "datasets" ? "active" : ""} onClick={() => { setTab("datasets"); setSearch(""); }}>
          <Database size={17} />Datasets <span className="vxp-count">{items.length}</span>
        </button>
      </div>

      {tab === "datasets" ? (
        <>
          {items.length > 0 && (
            <>
              <div className="history-overview">
                {[{ icon: Database, label: "Total datasets", value: items.length }, { icon: FileText, label: "Total records", value: totalRows }, { icon: Columns3, label: "Total columns", value: totalCols }].map(({ icon: Icon, label, value }) => (
                  <div className="history-stat" key={label}>
                    <div className="history-stat-icon"><Icon size={18} /></div>
                    <div><span>{label}</span><strong>{formatNumber(value)}</strong></div>
                  </div>
                ))}
              </div>
              <div className="history-toolbar">
                <div className="history-search"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search uploaded files..." /></div>
                <div className="history-filter">
                  <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} aria-label="Filter by type">
                    <option value="all">All file types</option>
                    <option value="excel">Excel</option>
                    <option value="csv">CSV</option>
                    <option value="json">JSON</option>
                    <option value="pdf">PDF</option>
                  </select>
                </div>
              </div>
            </>
          )}
          {!items.length ? <EmptyState icon={History} title="No upload history" text="Uploaded datasets will appear here once you add business data." />
            : !filteredDatasets.length ? <EmptyState icon={Search} title="No matching datasets" text="Try a different file name or change the file type filter." />
            : (
              <div className="history-list">
                <div className="history-list-header"><span>Dataset</span><span>Records</span><span>Structure</span><span>Uploaded</span><span>Action</span></div>
                {filteredDatasets.map((d, i) => (
                  <div className="history-row" key={d.id ?? i}>
                    <div className="history-dataset-cell">
                      <div className="history-file-icon"><FileText size={19} /></div>
                      <div className="history-main">
                        <strong title={d.name}>{d.name}</strong>
                        <div className="history-file-sub"><span className="history-type-badge">{fileKind(d)}</span><span>Dataset ID #{d.id ?? "\u2014"}</span></div>
                      </div>
                    </div>
                    <div className="history-value"><strong>{formatNumber(d.rows)}</strong><span>rows</span></div>
                    <div className="history-value"><strong>{formatNumber(d.columns)}</strong><span>columns</span></div>
                    <div className="history-date"><span>{fmtDate(d.uploaded_at) || "Upload date unavailable"}</span></div>
                    <div className="history-actions">
                      <button type="button" className="history-action-button" onClick={() => onUse(d.id)} title="Use this dataset"><Database size={16} />Use</button>
                      <button type="button" className="danger-icon" onClick={() => onDelete(d.id)} title="Delete dataset"><Trash2 size={17} /></button>
                    </div>
                  </div>
                ))}
              </div>
            )}
        </>
      ) : (
        <>
          <div className="history-toolbar">
            <div className="history-search"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search your queries..." /></div>
            {queryHistory.length > 0 && (
              <button type="button" className="secondary-button" onClick={() => { if (window.confirm("Clear all saved query results from this browser?")) onClearQueries(); }}>
                <Trash2 size={16} />Clear saved results
              </button>
            )}
          </div>

          {!queryHistory.length && !olderChats.length ? (
            <EmptyState icon={MessageSquare} title="No queries yet" text="Ask the AI Business Agent a question. Its answer, chart and report will be saved here." />
          ) : (
            <>
              {filteredQueries.length > 0 && (
                <div className="vxp-qlist">
                  {filteredQueries.map((e) => {
                    const hasRows = e.rowCount > 0;
                    return (
                      <article className="vxp-q" key={e.id}>
                        <div className="vxp-q-main">
                          <span className="vxp-q-icon"><Sparkles size={17} /></span>
                          <div>
                            <h4 title={e.question}>{e.question}</h4>
                            <div className="vxp-q-meta">
                              <span><Clock size={12} />{fmtStamp(e.time)}</span>
                              {e.datasetName && <span><Database size={12} />{e.datasetName}</span>}
                              <span className={`vxp-tag ${e.kind === "na" ? "warn" : ""}`}>
                                {e.kind === "na" ? "No data" : hasRows ? `${formatNumber(e.rowCount)} rows` : "Text answer"}
                              </span>
                              {e.hasChart && e.kind !== "na" && <span className="vxp-tag">Chart</span>}
                            </div>
                          </div>
                        </div>
                        <div className="vxp-q-actions">
                          <button type="button" className="secondary-button small" onClick={() => openEntry(e, "all")}><Sparkles size={14} />View</button>
                          {e.hasChart && e.kind !== "na" && <button type="button" className="secondary-button small" onClick={() => openEntry(e, "chart")}><BarChart3 size={14} />Chart</button>}
                          {hasRows && <button type="button" className="secondary-button small" onClick={() => openEntry(e, "report")}><FileText size={14} />Report</button>}
                          <button type="button" className="danger-icon" onClick={() => onRemoveQuery(e.id)} title="Remove" aria-label="Remove"><Trash2 size={16} /></button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}

              {olderChats.length > 0 && (
                <>
                  <h3 className="vxp-sub">Older conversations</h3>
                  <p className="vxp-note">Open a session to see its questions and answers together. Saved chart and report details appear when available.</p>
                  <div className="vxp-qlist">
                    {olderChats.map((c) => (
                      <article className="vxp-q" key={c.conversation_id}>
                        <div className="vxp-q-main">
                          <span className="vxp-q-icon muted"><MessageSquare size={17} /></span>
                          <div>
                            <h4 title={c.title}>{c.title || "New Chat"}</h4>
                            <div className="vxp-q-meta"><span><Clock size={12} />{fmtStamp(c.updated_at)}</span></div>
                          </div>
                        </div>
                        <div className="vxp-q-actions">
                          <button type="button" className="secondary-button small" onClick={() => onOpenConversation(c.conversation_id)}><MessageSquare size={14} />Open chat</button>
                          {c.title && <button type="button" className="secondary-button small" onClick={() => onRerun(c.title)}><RefreshCw size={14} />Run again</button>}
                          <button type="button" className="danger-icon" onClick={() => onDeleteConversation(c.conversation_id)} title="Delete chat" aria-label="Delete chat"><Trash2 size={16} /></button>
                        </div>
                      </article>
                    ))}
                  </div>
                </>
              )}
              {loadingConversations && <LoadingState text="Loading conversations..." />}
              {!filteredQueries.length && !olderChats.length && <EmptyState icon={Search} title="No matching queries" text="Try a different search term." />}
            </>
          )}
        </>
      )}
    </div>
  );
}
