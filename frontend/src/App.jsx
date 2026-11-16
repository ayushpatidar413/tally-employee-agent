import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot, ChevronLeft, ChevronRight, Database, FileText, History, LayoutDashboard,
  Moon, RefreshCw, Settings as SettingsIcon, Sun, Upload, X,
} from "lucide-react";

import "./dashboard-v2.css";
import "./pages-v3.css";
import Dashboard from "./components/dashboard/Dashboard.jsx";
import { QueryView, classifyResponse } from "./components/dashboard/QueryView.jsx";
import NoDataCard from "./components/dashboard/NoDataCard.jsx";
import ChatPanel from "./components/chat/ChatPanel.jsx";
import { ReportsPage, UploadPage, SettingsPage } from "./pages/OtherPages.jsx";
import { DataPage, HistoryPage } from "./pages/DataHistoryPages.jsx";
import { loadQueryHistory, makeQueryEntry, saveQueryHistory } from "./lib/queryHistory.js";
import { API, getColumns, normalizeDataset } from "./lib/helpers.js";

const MENU = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "data", label: "Business Data", icon: Database },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "upload", label: "Upload Data", icon: Upload },
  { id: "history", label: "History", icon: History },
  { id: "agent", label: "AI Business Agent", icon: Bot },
  { id: "settings", label: "Settings", icon: SettingsIcon },
];

function buildRich(data) {
  const result = data?.result || {};
  const rawRows = Array.isArray(result.rows) && result.rows.length ? result.rows : Array.isArray(result.table) ? result.table : [];
  const rows = rawRows.filter((r) => r && typeof r === "object" && !Array.isArray(r));
  const detailRows = Array.isArray(result.detail_table)
    ? result.detail_table.filter((r) => r && typeof r === "object" && !Array.isArray(r))
    : [];
  const details = result.details || {};
  const spec = result.chart_spec?.data?.length ? result.chart_spec : data?.chart?.data?.length ? data.chart : null;

  const rich = {
    rows,
    detailRows,
    details,
    uniquePartytypes: Array.isArray(details.unique_partytypes) ? details.unique_partytypes : [],
    partytypeSalesRanking: Array.isArray(details.partytype_sales_ranking) ? details.partytype_sales_ranking : [],
    partytypeProductSales: Array.isArray(details.partytype_product_sales) ? details.partytype_product_sales : [],
    chart: spec,
    downloadUrl: data?.download_url || null,
    source: data?.dataset?.original_filename || null,
    period: result.period_label || null,
    engine: data?.engine || null,
    engineDiagnostic: data?.engine_diagnostic || null,
  };

  return rows.length || detailRows.length || spec || rich.downloadUrl || rich.source || rich.engine
    || rich.uniquePartytypes.length || rich.partytypeProductSales.length
    ? rich
    : null;
}

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(() => (typeof window === "undefined" ? true : window.innerWidth >= 1000));
  const [theme, setTheme] = useState(() => localStorage.getItem("vyapar-theme") || "light");
  const [userName, setUserName] = useState(() => localStorage.getItem("vyapar-user") || "Ayush");
  const [online, setOnline] = useState(null);

  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [datasetRows, setDatasetRows] = useState([]);
  const [loadingDatasets, setLoadingDatasets] = useState(false);
  const [loadingRows, setLoadingRows] = useState(false);

  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const activeConversationIdRef = useRef(null);
  const chatRequestLockRef = useRef(false);
  const [messages, setMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [loadingConversations, setLoadingConversations] = useState(false);
  const [chatExpanded, setChatExpanded] = useState(false);
  const [dashboardQuery, setDashboardQuery] = useState(null);
  const [queryHistory, setQueryHistory] = useState(() => loadQueryHistory());
  const queryHistoryRef = useRef(queryHistory);

  const [toast, setToast] = useState(null);

  const showMessage = useCallback((type, text) => {
    setToast({ type, text });
    window.setTimeout(() => setToast(null), 3800);
  }, []);

  /* ---------------------------------------------------- appearance */
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("vyapar-theme", theme);
  }, [theme]);
  useEffect(() => { localStorage.setItem("vyapar-user", userName); }, [userName]);
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") setChatExpanded(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  /* ------------------------------------------------------ backend */
  useEffect(() => {
    let alive = true;
    const ping = async () => {
      try {
        const r = await fetch(`${API}/health`);
        if (alive) setOnline(r.ok);
      } catch (e) {
        if (alive) setOnline(false);
      }
    };
    ping();
    const id = window.setInterval(ping, 30000);
    return () => { alive = false; window.clearInterval(id); };
  }, []);

  const loadDatasets = useCallback(async () => {
    setLoadingDatasets(true);
    try {
      const response = await fetch(`${API}/datasets`);
      if (!response.ok) throw new Error(`Failed to load datasets: ${response.status}`);
      const data = await response.json();
      let raw = [];
      if (Array.isArray(data)) raw = data;
      else if (Array.isArray(data?.datasets)) raw = data.datasets;
      else if (data?.datasets && typeof data.datasets === "object") {
        const n = data.datasets;
        raw = Array.isArray(n.data) ? n.data : Array.isArray(n.items) ? n.items : Array.isArray(n.datasets) ? n.datasets
          : Object.values(n).filter((i) => i && typeof i === "object" && (i.id !== undefined || i.original_filename !== undefined));
      } else if (Array.isArray(data?.data)) raw = data.data;
      else if (Array.isArray(data?.items)) raw = data.items;
      const list = raw.map(normalizeDataset).filter((i) => i.id !== null && i.id !== undefined);
      setDatasets(list);
      setSelectedDatasetId((cur) => (list.some((i) => Number(i.id) === Number(cur)) ? cur : list[0]?.id ?? null));
    } catch (error) {
      console.error("DATASET LOAD ERROR:", error);
      setDatasets([]);
      setSelectedDatasetId(null);
    } finally {
      setLoadingDatasets(false);
    }
  }, []);

  const loadDataset = useCallback(async (id) => {
    if (id === null || id === undefined) {
      setSelectedDataset(null);
      setDatasetRows([]);
      return;
    }
    setLoadingRows(true);
    try {
      const meta = await fetch(`${API}/datasets/${id}`);
      if (!meta.ok) throw new Error(`Failed to load dataset metadata: ${meta.status}`);
      const data = await meta.json();
      setSelectedDataset(normalizeDataset(data?.dataset?.dataset || data?.dataset || data));
      const rr = await fetch(`${API}/datasets/${id}/rows`);
      if (!rr.ok) throw new Error(`Failed to load dataset rows (${rr.status})`);
      const payload = await rr.json();
      const raw = Array.isArray(payload?.rows) ? payload.rows : Array.isArray(payload?.data) ? payload.data : [];
      setDatasetRows(
        raw.map((i) => (i && typeof i === "object" && i.data && typeof i.data === "object" ? i.data : i))
          .filter((i) => i && typeof i === "object" && !Array.isArray(i))
      );
    } catch (error) {
      console.error("DATASET DETAIL/ROWS ERROR:", error);
      setDatasetRows([]);
      showMessage("error", error.message || "Could not load dataset rows.");
    } finally {
      setLoadingRows(false);
    }
  }, [showMessage]);

  useEffect(() => { loadDatasets(); loadConversations(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { loadDataset(selectedDatasetId); }, [selectedDatasetId, loadDataset]);

  async function deleteDataset(id) {
    if (!id || !window.confirm("Are you sure you want to delete this dataset?")) return;
    try {
      const r = await fetch(`${API}/datasets/${id}`, { method: "DELETE" });
      if (!r.ok) throw new Error(`Failed to delete dataset: ${r.status}`);
      await loadDatasets();
      showMessage("success", "Dataset deleted.");
    } catch (error) {
      showMessage("error", error.message || "Unable to delete the dataset.");
    }
  }

  async function uploadFileToServer(file) {
    if (!file) { showMessage("error", "Please select a file first."); return false; }
    const form = new FormData();
    form.append("file", file);
    setUploading(true);
    try {
      const r = await fetch(`${API}/upload-data`, { method: "POST", body: form });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || data?.result?.success === false) throw new Error(data?.detail || data?.result?.message || "Upload failed");
      showMessage("success", `${file.name} uploaded successfully.`);
      await loadDatasets();
      return true;
    } catch (error) {
      showMessage("error", error.message || "File upload failed.");
      return false;
    } finally {
      setUploading(false);
    }
  }

  async function submitUpload(event) {
    event.preventDefault();
    if (await uploadFileToServer(uploadFile)) { setUploadOpen(false); setUploadFile(null); }
  }

  /* ------------------------------------------------ conversations */
  async function loadConversations() {
    setLoadingConversations(true);
    try {
      const r = await fetch(`${API}/conversations`);
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || "Could not load chat history.");
      setConversations(Array.isArray(data?.conversations) ? data.conversations : []);
    } catch (error) {
      console.error("Load conversations failed:", error);
    } finally {
      setLoadingConversations(false);
    }
  }

  async function createConversation(title) {
    const r = await fetch(`${API}/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: String(title || "New Chat").slice(0, 80) }),
    });
    const data = await r.json();
  
    if (!r.ok || !data?.conversation_id) throw new Error(data?.detail || "Could not create a new conversation.");
    activeConversationIdRef.current = data.conversation_id;
    setActiveConversationId(data.conversation_id);
    return data.conversation_id;
  }

  async function openConversation(id) {
    try {
      const r = await fetch(`${API}/conversations/${encodeURIComponent(id)}`);
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || "Could not open this conversation.");
      activeConversationIdRef.current = id;
      setActiveConversationId(id);
      setDashboardQuery(null);
      setMessages((Array.isArray(data?.messages) ? data.messages : []).map((m, index, allMessages) => {
        let saved = m.metadata ?? m.meta ?? null;
        if (typeof saved === "string") {
          try { saved = JSON.parse(saved); } catch { saved = null; }
        }
        const role = String(m.role).toLowerCase() === "user" ? "user" : "assistant";
        if ((!saved || typeof saved !== "object") && role === "assistant") {
          let precedingQuestion = "";
          for (let j = index - 1; j >= 0; j -= 1) {
            if (String(allMessages[j]?.role).toLowerCase() === "user") {
              precedingQuestion = String(allMessages[j]?.message ?? allMessages[j]?.content ?? "");
              break;
            }
          }
          const cached = queryHistoryRef.current.find((entry) =>
            String(entry.conversationId) === String(id) &&
            String(entry.question || "").trim() === precedingQuestion.trim()
          );
          if (cached?.data) saved = cached.data;
        }
        return {
          id: `db-${m.id}`,
          role,
          text: m.message ?? m.content ?? "",
          time: m.created_at,
          rich: role === "assistant" && saved && typeof saved === "object" ? buildRich(saved) : null,
          engine: saved?.engine || null,
          engineDiagnostic: saved?.engine_diagnostic || null,
        };
      }));
    } catch (error) {
      showMessage("error", error.message || "Could not open conversation.");
    }
  }

  function startNewChat() {
    activeConversationIdRef.current = null;
    setActiveConversationId(null);
    setMessages([]);
    setDashboardQuery(null);
  }

  async function removeConversation(id) {
    if (!window.confirm("Delete this conversation and its messages?")) return;
    try {
      const r = await fetch(`${API}/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || "Could not delete conversation.");
      if (String(activeConversationId) === String(id)) startNewChat();
      await loadConversations();
      showMessage("success", "Conversation deleted.");
    } catch (error) {
      showMessage("error", error.message || "Could not delete conversation.");
    }
  }

  async function sendMessage(question) {
    const q = String(question || "").trim();
    console.log("========== APP QUERY DEBUG ==========");
    console.log("QUESTION RECEIVED:", JSON.stringify(question));
    console.log("QUESTION LENGTH:", String(question || "").length);
    console.log("FINAL API QUERY:", JSON.stringify(q));
    console.log("FINAL API QUERY LENGTH:", q.length);
    console.log("=====================================");
    if (!q || chatRequestLockRef.current) return;
    chatRequestLockRef.current = true;
    const stamp = () => new Date().toISOString();
    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: "user", text: q, time: stamp() }]);
    setChatLoading(true);
    try {
      const cid = activeConversationIdRef.current || (await createConversation(q));
      const r = await fetch(`${API}/ask-business`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, dataset_id: selectedDatasetId, conversation_id: cid }),
      });
      const data = await r.json();
      console.log("========== API RESPONSE DEBUG ==========");
      console.log("REQUEST QUESTION:", q);
      console.log("HTTP STATUS:", r.status);
      console.log("RESPONSE ANSWER:", data?.answer);
      console.log("RESPONSE ENGINE:", data?.engine);
      console.log("RESPONSE DATASET:", data?.dataset_id);
      console.log("RESPONSE RESULT:", data?.result);
      console.log("========================================");
      if (!r.ok) throw new Error(data?.detail || data?.message || "Agent request failed");
      setDashboardQuery({ question: q, data, datasetName: selectedDataset?.original_filename || selectedDataset?.name || "" });
      try {
        const entry = makeQueryEntry({
          question: q, data, conversationId: cid,
          datasetId: data?.dataset_id ?? selectedDatasetId,
          datasetName: selectedDataset?.original_filename || selectedDataset?.name || "",
        });
        const next = saveQueryHistory([entry, ...queryHistoryRef.current]);
        queryHistoryRef.current = next;
        setQueryHistory(next);
      } catch (e) { console.error("Could not save query history:", e); }
      console.log("===== TOP PRODUCTS API DEBUG =====");
      console.log("QUESTION:", question);
      console.log("ANSWER:", data?.answer);
      console.log("RESULT OPERATION:", data?.result?.operation);
      console.log("RESULT ROWS COUNT:", data?.result?.rows?.length);
      console.table(data?.result?.rows || []);
      console.log("RESULT TABLE COUNT:", data?.result?.table?.length);
      console.log("FULL RESULT:", data?.result);
      setMessages((m) => [...m, {
        id: `a-${Date.now()}`, role: "assistant", time: stamp(),
        text: String(data?.answer || "Information is not available in the uploaded file"),
        rich: buildRich(data),
        engine: data?.engine || null,
        engineDiagnostic: data?.engine_diagnostic || null,
      }]);
      if (data?.dataset_id && Number(data.dataset_id) !== Number(selectedDatasetId)) {
        setSelectedDatasetId(data.dataset_id);
        showMessage("success", "Switched to the dataset that matches your question.");
      }
      loadConversations();
    } catch (error) {
      setMessages((m) => [...m, { id: `e-${Date.now()}`, role: "assistant", error: true, time: stamp(), text: error.message || "Agent request failed." }]);
    } finally {
      chatRequestLockRef.current = false;
      setChatLoading(false);
    }
  }

  /* ---------------------------------------------------------- render */
  const columns = getColumns(datasetRows, selectedDataset);
  const chatProps = {
    messages, loading: chatLoading, onSend: sendMessage, onUpload: uploadFileToServer,
    datasetName: selectedDataset?.name, conversations, activeId: activeConversationId, loadingConversations,
    onOpen: openConversation, onDelete: removeConversation, onNew: startNewChat, onRefreshHistory: loadConversations,
  };
  const useDataset = (id) => { setSelectedDatasetId(id); setPage("dashboard"); };
  const removeQuery = (id) => {
    const next = saveQueryHistory(queryHistoryRef.current.filter((e) => e.id !== id));
    queryHistoryRef.current = next;
    setQueryHistory(next);
  };
  const clearQueries = () => {
    const next = saveQueryHistory([]);
    queryHistoryRef.current = next;
    setQueryHistory(next);
  };
  const rerunQuery = (q) => { setPage("dashboard"); sendMessage(q); };
  const openChatPage = async (id) => { await openConversation(id); setPage("agent"); };

  return (
    <div className={`vx-app ${page === "dashboard" ? "has-chat" : ""}`}>
      <aside className={`vx-sidebar ${sidebarOpen ? "open" : "closed"}`}>
        <div className="vx-brand">
          <div className="vx-brand-mark">V</div>
          {sidebarOpen && (
            <div className="vx-brand-copy">
              <strong>Vyapar AI</strong>
              <span>Business Intelligence</span>
            </div>
          )}
        </div>
        <nav className="vx-nav">
          {MENU.map(({ id, label, icon: Icon }) => (
            <button key={id} type="button" className={page === id ? "active" : ""} onClick={() => setPage(id)} title={!sidebarOpen ? label : ""}>
              <Icon size={20} />
              {sidebarOpen && <span>{label}</span>}
            </button>
          ))}
        </nav>
        <div className="vx-side-bottom">
          <div className={`vx-status ${online === false ? "off" : online ? "on" : ""}`} title={online ? "Backend connected" : "Backend not reachable"}>
            <span className="vx-status-dot" />
            {sidebarOpen && (
              <div>
                <strong>{online === false ? "Backend Offline" : online ? "Backend Connected" : "Connecting..."}</strong>
                <small>Dynamic database</small>
              </div>
            )}
          </div>
          <div className="vx-side-tools">
            <button type="button" onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))} title="Toggle theme">{theme === "light" ? <Moon size={17} /> : <Sun size={17} />}</button>
            <button type="button" onClick={loadDatasets} title="Refresh datasets"><RefreshCw size={17} className={loadingDatasets ? "spin" : ""} /></button>
            <button type="button" onClick={() => setSidebarOpen((v) => !v)} title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}>{sidebarOpen ? <ChevronLeft size={17} /> : <ChevronRight size={17} />}</button>
          </div>
        </div>
      </aside>

      <main className="vx-main">
        {page === "dashboard" ? (
          <div className="vx-workspace">
            <section className="vx-content">
              <Dashboard
                datasets={datasets}
                selectedDataset={selectedDataset}
                selectedDatasetId={selectedDatasetId}
                onSelectDataset={setSelectedDatasetId}
                rows={datasetRows}
                columns={columns}
                loading={loadingDatasets || loadingRows}
                userName={userName}
                onUpload={() => setUploadOpen(true)}
              />
              {dashboardQuery && (
                <div className="vx-dashboard-query">
                <div className="vx-query-shortcut">
                  <button
                    type="button"
                    className="vx-select-btn small"
                    onClick={() => setPage("agent")}
                  >
                    Open chat answer
                  </button>
                  <button
                    type="button"
                    className="vx-select-btn small"
                    onClick={() => setDashboardQuery(null)}
                  >
                    Close query
                  </button>
                </div>
                <div className="vx-query-result">
                  <QueryView
                    question={dashboardQuery.question}
                    data={dashboardQuery.data}
                    datasetName={dashboardQuery.datasetName}
                  />
                </div>
              
                </div>
              )}
            </section>
            {chatExpanded && <div className="vx-chat-backdrop" onClick={() => setChatExpanded(false)} />}
            <aside className={`vx-chat ${chatExpanded ? "expanded" : ""}`}>
              <ChatPanel {...chatProps} mode="panel" expanded={chatExpanded} onToggleExpand={() => setChatExpanded((v) => !v)} />
            </aside>
          </div>
        ) : page === "agent" ? (
          <section className="vx-content vx-agent-page">
            <ChatPanel {...chatProps} mode="page" />
          </section>
        ) : (
          <section className="vx-content vx-page-content">
            {page === "data" && (
              <DataPage datasets={datasets} selectedDatasetId={selectedDatasetId} setSelectedDatasetId={useDataset} onDelete={deleteDataset} onUpload={() => setUploadOpen(true)} loading={loadingDatasets} />
            )}
            {page === "reports" && <ReportsPage datasets={datasets} selectedDataset={selectedDataset} datasetRows={datasetRows} onOpenChat={() => setPage("agent")} />}
            {page === "upload" && (
              <UploadPage
                datasets={datasets}
                onUpload={() => setUploadOpen(true)}
                onRefresh={loadDatasets}
                onDelete={deleteDataset}
              />
            )}
            {page === "history" && (
              <HistoryPage
                datasets={datasets} selectedDatasetId={selectedDatasetId} onDelete={deleteDataset}
                onRefresh={() => { loadDatasets(); loadConversations(); }} onUse={useDataset}
                queryHistory={queryHistory} onRemoveQuery={removeQuery} onClearQueries={clearQueries}
                conversations={conversations} loadingConversations={loadingConversations}
                onOpenConversation={openChatPage} onDeleteConversation={removeConversation} onRerun={rerunQuery}
              />
            )}
            {page === "settings" && <SettingsPage theme={theme} setTheme={setTheme} userName={userName} setUserName={setUserName} />}
          </section>
        )}
      </main>

      {toast && (
        <div className={`vx-toast ${toast.type}`} role="status">
          <span>{toast.text}</span>
          <button type="button" onClick={() => setToast(null)} aria-label="Dismiss"><X size={16} /></button>
        </div>
      )}

      {uploadOpen && (
        <div className="modal-backdrop" onClick={() => { setUploadOpen(false); setUploadFile(null); }}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="section-kicker">DATA IMPORT</span>
                <h2>Upload Business Data</h2>
              </div>
              <button type="button" className="close-button" onClick={() => { setUploadOpen(false); setUploadFile(null); }}><X size={18} /></button>
            </div>
            <form onSubmit={submitUpload}>
              <label className="drop-zone">
                <Upload size={30} />
                <strong>{uploadFile ? uploadFile.name : "Choose a business file"}</strong>
                <span>CSV, XLSX, XLS, JSON or PDF</span>
                <input type="file" accept=".csv,.xlsx,.xls,.json,.pdf" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} />
              </label>
              <div className="modal-actions">
                <button type="button" className="secondary-button" onClick={() => { setUploadOpen(false); setUploadFile(null); }}>Cancel</button>
                <button type="submit" className="primary-button" disabled={uploading || !uploadFile}>
                  {uploading ? <><RefreshCw size={17} className="spin" />Uploading...</> : <><Upload size={17} />Upload File</>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

