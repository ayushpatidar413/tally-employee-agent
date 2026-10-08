import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  Bot,
  ChevronLeft,
  ChevronRight,
  Columns3,
  Database,
  Download,
  FileText,
  History,
  LayoutDashboard,
  Lightbulb,
  Moon,
  PieChart,
  Plus,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  Sun,
  Trash2,
  Upload,
  X,
} from "lucide-react";



import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API = "http://127.0.0.1:8000";

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "-";

  const number = Number(value);

  if (!Number.isFinite(number)) return String(value);

  return number.toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  });
}

function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "â‚¹0";

  const number = Number(value);

  if (!Number.isFinite(number)) return String(value);

  return `â‚¹${number.toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}`;
}


function normalizeDataset(item) {
  const dataset = item?.dataset || item || {};

  const rawColumns = Array.isArray(dataset.columns)
    ? dataset.columns
    : [];

  return {
    id: dataset.id ?? null,

    name:
      dataset.original_filename ||
      dataset.filename ||
      dataset.file_name ||
      dataset.name ||
      `Dataset ${dataset.id ?? ""}`,

    type:
      dataset.data_type ||
      dataset.dataset_type ||
      dataset.type ||
      "custom",

    fileType:
      dataset.file_type ||
      "",

    stored_filename:
      dataset.stored_filename ||
      null,

    original_filename:
      dataset.original_filename ||
      null,

    rows:
      Number(
        dataset.row_count ??
        dataset.rows ??
        dataset.total_rows ??
        0
      ) || 0,

    columns:
      Number(
        dataset.column_count ??
        dataset.columns_count ??
        rawColumns.length ??
        0
      ) || 0,

    schema: dataset.schema || {},

    columnNames: rawColumns.map((column) => {
      if (typeof column === "string") {
        return column;
      }

      return column?.name || "";
    }).filter(Boolean),

    status:
      dataset.status ||
      "SUCCESS",

    uploaded_at:
      dataset.uploaded_at ||
      null,

    file_size:
      Number(dataset.file_size || 0),

    error_message:
      dataset.error_message ||
      null,

    raw: item,
  };
}



function getRows(payload) {
  if (!payload) return [];

  const candidates = [
    payload.rows,
    payload.data,
    payload.records,
    payload.dataset?.rows,
    payload.dataset?.data,
    payload.result?.rows,
    payload.result?.data,
  ];

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate.filter(
        (row) => row && typeof row === "object" && !Array.isArray(row)
      );
    }
  }

  return [];
}

function getColumns(rows, dataset) {
  if (rows.length) {
    return Object.keys(rows[0]);
  }

  const schema = dataset?.schema;

  if (Array.isArray(schema)) {
    return schema
      .map((item) => {
        if (typeof item === "string") return item;
        return item?.name || item?.column || item?.field;
      })
      .filter(Boolean);
  }

  if (schema && typeof schema === "object") {
    return Object.keys(schema);
  }

  return [];
}

function isNumericColumn(rows, column) {
  const values = rows
    .map((row) => row?.[column])
    .filter((value) => value !== null && value !== undefined && value !== "");

  if (!values.length) return false;

  const numeric = values.filter((value) => {
    const cleaned = String(value).replace(/[?,%\s,]/g, "");
    return cleaned !== "" && Number.isFinite(Number(cleaned));
  });

  return numeric.length / values.length >= 0.6;
}

function numericValue(value) {
  if (value === null || value === undefined) return 0;

  const cleaned = String(value)
    .replace(/[?,%\s,]/g, "")
    .trim();

  const number = Number(cleaned);

  return Number.isFinite(number) ? number : 0;
}

function App() {
  const [page, setPage] = useState("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [theme, setTheme] = useState(
    () => localStorage.getItem("vyapar-theme") || "light"
  );

  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [datasetRows, setDatasetRows] = useState([]);

  const [loadingDatasets, setLoadingDatasets] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);

  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const [chartType, setChartType] = useState("bar");
  const [chartColumn, setChartColumn] = useState("");
  const [groupColumn, setGroupColumn] = useState("");

  const [search, setSearch] = useState("");

  const [agentQuestion, setAgentQuestion] = useState("");
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentResult, setAgentResult] = useState(null);

  const [message, setMessage] = useState(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("vyapar-theme", theme);
  }, [theme]);

  useEffect(() => {
    loadDatasets();
  }, []);

  useEffect(() => {
    if (
        selectedDatasetId !== null &&
        selectedDatasetId !== undefined
    ) {
        loadDataset(selectedDatasetId);
    } else {
        setSelectedDataset(null);
        setDatasetRows([]);
    }
  }, [selectedDatasetId]);
   useEffect(() => {
    const handleNavigateToAgent = () => {
      setPage("agent");
    };

    window.addEventListener(
      "navigate-to-agent",
      handleNavigateToAgent
    );

    return () => {
      window.removeEventListener(
        "navigate-to-agent",
        handleNavigateToAgent
      );
    };
  }, []);

  useEffect(() => {
    const handleNavigateToAgent = () => {
      setPage("agent");
    };

    window.addEventListener(
      "navigate-to-agent",
      handleNavigateToAgent
    );

    return () => {
      window.removeEventListener(
        "navigate-to-agent",
        handleNavigateToAgent
      );
    };
  }, []);

async function loadDatasets() {
  setLoadingDatasets(true);

  try {
    const response = await fetch(`${API}/datasets`);

    if (!response.ok) {
      throw new Error(`Failed to load datasets: ${response.status}`);
    }

    const data = await response.json();

    console.log("FULL DATASETS RESPONSE:", data);

    let rawList = [];

    if (Array.isArray(data)) {
      rawList = data;
    } else if (Array.isArray(data?.datasets)) {
      rawList = data.datasets;
    } else if (
      data?.datasets &&
      typeof data.datasets === "object"
    ) {
      const nested = data.datasets;

      if (Array.isArray(nested.data)) {
        rawList = nested.data;
      } else if (Array.isArray(nested.items)) {
        rawList = nested.items;
      } else if (Array.isArray(nested.datasets)) {
        rawList = nested.datasets;
      } else {
        rawList = Object.values(nested).filter(
          (item) =>
            item &&
            typeof item === "object" &&
            (
              item.id !== undefined ||
              item.original_filename !== undefined ||
              item.row_count !== undefined
            )
        );
      }
    } else if (Array.isArray(data?.data)) {
      rawList = data.data;
    } else if (Array.isArray(data?.items)) {
      rawList = data.items;
    }

    console.log("RAW DATASET LIST:", rawList);
    console.log("RAW DATASET COUNT:", rawList.length);

    const list = rawList
      .map(normalizeDataset)
      .filter(
        (item) =>
          item.id !== null &&
          item.id !== undefined
      );

    console.log("NORMALIZED DATASETS:", list);
    console.log("NORMALIZED COUNT:", list.length);

    setDatasets(list);

    if (list.length > 0) {
      setSelectedDatasetId((currentId) => {
        const exists = list.some(
          (item) => Number(item.id) === Number(currentId)
        );

        return exists ? currentId : list[0].id;
      });
    } else {
      setSelectedDatasetId(null);
      setSelectedDataset(null);
      setDatasetRows([]);
    }
  } catch (error) {
    console.error("DATASET LOAD ERROR:", error);

    setDatasets([]);
    setSelectedDatasetId(null);
    setSelectedDataset(null);
    setDatasetRows([]);
  } finally {
    setLoadingDatasets(false);
  }
}

async function loadDataset(id) {
  if (id === null || id === undefined) {
    setSelectedDataset(null);
    setDatasetRows([]);
    return;
  }

  try {
    console.log("LOADING DATASET:", id);

    const response = await fetch(`${API}/datasets/${id}`);

    if (!response.ok) {
      throw new Error(`Failed to load dataset: ${response.status}`);
    }

    const data = await response.json();

    console.log("DATASET DETAIL RESPONSE:", data);

    // Backend response is:
    // { success: true, dataset: { success: true, dataset: {...} } }
    const source =
      data?.dataset?.dataset ||
      data?.dataset ||
      data;

    console.log("ACTUAL DATASET OBJECT:", source);

    const normalized = normalizeDataset(source);

    console.log("SELECTED DATASET:", normalized);

    setSelectedDataset(normalized);

    // This endpoint returns metadata, not the actual records.
    // Keep rows empty until we have a real preview/data endpoint.
    setDatasetRows([]);
  } catch (error) {
    console.error("DATASET DETAIL ERROR:", error);

    setSelectedDataset(null);
    setDatasetRows([]);
  }
}

  async function deleteDataset(id) {
    if (!id) return;

    const confirmed = window.confirm(
        "Are you sure you want to delete this dataset?"
    );

    if (!confirmed) return;

    try {
        const response = await fetch(`${API}/datasets/${id}`, {
        method: "DELETE",
        });

        if (!response.ok) {
        throw new Error(`Failed to delete dataset: ${response.status}`);
        }

        console.log("Dataset deleted:", id);

        // Refresh dataset list
        await loadDatasets();

        // Clear selection if deleted dataset was active
        if (Number(selectedDatasetId) === Number(id)) {
        setSelectedDatasetId(null);
        setSelectedDataset(null);
        setDatasetRows([]);
        }
    } catch (error) {
        console.error("DELETE DATASET ERROR:", error);
        window.alert("Unable to delete the dataset.");
    }
  }
  async function uploadData(event) {
    event.preventDefault();

    if (!uploadFile) {
      showMessage("error", "Please select a file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", uploadFile);

    setUploading(true);

    try {
      const response = await fetch(`${API}/upload-data`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data?.detail || "Upload failed");
      }

      showMessage("success", "File uploaded successfully.");

      setUploadOpen(false);
      setUploadFile(null);

      await loadDatasets();
    } catch (error) {
      showMessage(
        "error",
        error.message || "File upload failed."
      );
    } finally {
      setUploading(false);
    }
  }

  async function askAgent(questionOverride = null) {
    const question = String(
      questionOverride ?? agentQuestion
    ).trim();

    if (!question) {
      showMessage("error", "Enter a business question first.");
      return;
    }

    setAgentLoading(true);

    try {
      const response = await fetch(`${API}/ask-business`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: question,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail || data?.message || "Agent request failed"
        );
      }

      setAgentResult(data);
      setAgentQuestion(question);
    } catch (error) {
      setAgentResult({
        answer: error.message || "Agent request failed.",
        error: true,
      });
    } finally {
      setAgentLoading(false);
    }
  }

  function showMessage(type, text) {
    setMessage({ type, text });

    window.setTimeout(() => {
      setMessage(null);
    }, 3500);
  }

  const columns = useMemo(
    () => getColumns(datasetRows, selectedDataset),
    [datasetRows, selectedDataset]
  );

  const numericColumns = useMemo(
    () => columns.filter((column) => isNumericColumn(datasetRows, column)),
    [columns, datasetRows]
  );

  const categoricalColumns = useMemo(
    () =>
      columns.filter(
        (column) =>
          !isNumericColumn(datasetRows, column)
      ),
    [columns, datasetRows]
  );

  const chartData = useMemo(() => {
    if (!datasetRows.length || !chartColumn) return [];

    const category = groupColumn;

    if (!category) {
      return datasetRows.slice(0, 25).map((row, index) => ({
        label: `Row ${index + 1}`,
        value: numericValue(row[chartColumn]),
      }));
    }

    const map = new Map();

    for (const row of datasetRows) {
      const key = String(
        row?.[category] ?? "Unknown"
      );

      const value = numericValue(row?.[chartColumn]);

      map.set(key, (map.get(key) || 0) + value);
    }

    return Array.from(map.entries())
      .map(([label, value]) => ({
        label,
        value,
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 20);
  }, [datasetRows, chartColumn, groupColumn]);

  const metrics = useMemo(() => {
    if (!datasetRows.length) {
      return {
        rows: selectedDataset?.rows || 0,
        columns: columns.length,
        numericTotal: 0,
        uniqueGroups: 0,
      };
    }

    const total = chartColumn
      ? datasetRows.reduce(
          (sum, row) => sum + numericValue(row?.[chartColumn]),
          0
        )
      : 0;

    const uniqueGroups = groupColumn
      ? new Set(
          datasetRows.map((row) => String(row?.[groupColumn] ?? ""))
        ).size
      : 0;

    return {
      rows: datasetRows.length,
      columns: columns.length,
      numericTotal: total,
      uniqueGroups,
    };
  }, [
    datasetRows,
    selectedDataset,
    columns,
    chartColumn,
    groupColumn,
  ]);

  const filteredDatasets = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) return datasets;

    return datasets.filter((dataset) =>
      `${dataset.name} ${dataset.type}`
        .toLowerCase()
        .includes(query)
    );
  }, [datasets, search]);

  function navigate(nextPage) {
    setPage(nextPage);
  }

  const menu = [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: LayoutDashboard,
    },
    {
      id: "data",
      label: "Business Data",
      icon: Database,
    },
    {
      id: "analytics",
      label: "Analytics",
      icon: BarChart3,
    },
    {
      id: "reports",
      label: "Reports",
      icon: FileText,
    },
    {
      id: "upload",
      label: "Upload Data",
      icon: Upload,
    },
    {
      id: "history",
      label: "History",
      icon: History,
    },
    {
      id: "agent",
      label: "AI Business Agent",
      icon: Bot,
    },
  ];

  const pageTitle =
    menu.find((item) => item.id === page)?.label ||
    "Dashboard";

  return (
    <div className="app">
      <PieTest />
      <aside
        className={`sidebar ${
          sidebarOpen ? "sidebar-open" : "sidebar-closed"
        }`}
      >
        <div className="brand">
          <div className="brand-mark">V</div>

          {sidebarOpen && (
            <div className="brand-copy">
              <strong>Vyapar</strong>
              <span>Business Intelligence</span>
            </div>
          )}
        </div>

        <nav className="navigation">
          {menu.map((item) => {
            const Icon = item.icon;

            return (
              <button
                key={item.id}
                type="button"
                className={`nav-button ${
                  page === item.id ? "active" : ""
                }`}
                onClick={() => navigate(item.id)}
                title={!sidebarOpen ? item.label : ""}
              >
                <Icon size={19} />
                {sidebarOpen && <span>{item.label}</span>}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          {sidebarOpen && (
            <div className="connection-card">
              <span className="connection-dot" />
              <div>
                <strong>Backend Connected</strong>
                <small>Dynamic database</small>
              </div>
            </div>
          )}

          <button
            type="button"
            className="collapse-button"
            onClick={() => setSidebarOpen((value) => !value)}
            title={
              sidebarOpen
                ? "Collapse sidebar"
                : "Expand sidebar"
            }
          >
            {sidebarOpen ? (
              <ChevronLeft size={17} />
            ) : (
              <ChevronRight size={17} />
            )}
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <span className="topbar-kicker">
              BUSINESS INTELLIGENCE
            </span>
            <h1>{pageTitle}</h1>
          </div>

          <div className="topbar-actions">
            <div className="search-box">
              <Search size={17} />
              <input
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Search datasets..."
              />
            </div>

            <button
              type="button"
              className="top-icon-button"
              onClick={() =>
                setTheme((value) =>
                  value === "light" ? "dark" : "light"
                )
              }
              title="Toggle theme"
            >
              {theme === "light" ? (
                <Moon size={18} />
              ) : (
                <Sun size={18} />
              )}
            </button>

            <button
              type="button"
              className="top-icon-button"
              onClick={loadDatasets}
              title="Refresh datasets"
            >
              <RefreshCw
                size={18}
                className={
                  loadingDatasets ? "spin" : ""
                }
              />
            </button>
          </div>
        </header>

        {message && (
          <div className={`toast ${message.type}`}>
            <span>{message.text}</span>
            <button
              type="button"
              onClick={() => setMessage(null)}
            >
              <X size={16} />
            </button>
          </div>
        )}

        <section className="content">
          {page === "dashboard" && (
            <DashboardPage
              datasets={datasets}
              selectedDataset={selectedDataset}
              selectedDatasetId={selectedDatasetId}
              setSelectedDatasetId={setSelectedDatasetId}
              loading={loadingDetails || loadingDatasets}
              metrics={metrics}
              chartData={chartData}
              chartType={chartType}
              setChartType={setChartType}
              chartColumn={chartColumn}
              setChartColumn={setChartColumn}
              groupColumn={groupColumn}
              setGroupColumn={setGroupColumn}
              numericColumns={numericColumns}
              categoricalColumns={categoricalColumns}
              columns={columns}
              datasetRows={datasetRows}
              onUpload={() => setUploadOpen(true)}
              onDelete={deleteDataset}
              onNavigate={navigate}
            />
          )}

          {page === "data" && (
            <DataPage
              datasets={filteredDatasets}
              selectedDatasetId={selectedDatasetId}
              setSelectedDatasetId={setSelectedDatasetId}
              onDelete={deleteDataset}
              onUpload={() => setUploadOpen(true)}
              loading={loadingDatasets}
            />
          )}

          {page === "analytics" && (
            <AnalyticsPage
              datasets={datasets}
              selectedDataset={selectedDataset}
              datasetRows={datasetRows}
              columns={columns}
              chartData={chartData}
              chartType={chartType}
              setChartType={setChartType}
              chartColumn={chartColumn}
              setChartColumn={setChartColumn}
              groupColumn={groupColumn}
              setGroupColumn={setGroupColumn}
              numericColumns={numericColumns}
              categoricalColumns={categoricalColumns}
            />
          )}

          {page === "reports" && (
            <ReportsPage
              datasets={datasets}
              selectedDataset={selectedDataset}
              datasetRows={datasetRows}
            />
          )}

          {page === "upload" && (
            <UploadPage
              onUpload={() => setUploadOpen(true)}
              datasets={datasets}
            />
          )}

          {page === "history" && (
            <HistoryPage
              datasets={datasets}
              onDelete={deleteDataset}
              onRefresh={loadDatasets}
            />
          )}

          {page === "agent" && (
            <AgentPage
              question={agentQuestion}
              setQuestion={setAgentQuestion}
              loading={agentLoading}
              result={agentResult}
              askAgent={askAgent}
            />
          )}
        </section>
      </main>

      {uploadOpen && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="modal-header">
              <div>
                <span className="section-kicker">
                  DATA IMPORT
                </span>
                <h2>Upload Business Data</h2>
              </div>

              <button
                type="button"
                className="close-button"
                onClick={() => {
                  setUploadOpen(false);
                  setUploadFile(null);
                }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={uploadData}>
              <label className="drop-zone">
                <Upload size={30} />
                <strong>
                  {uploadFile
                    ? uploadFile.name
                    : "Choose a business file"}
                </strong>

                <span>
                  CSV, XLSX, XLS, JSON or PDF
                </span>

                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.json,.pdf"
                  onChange={(event) =>
                    setUploadFile(
                      event.target.files?.[0] || null
                    )
                  }
                />
              </label>

              <div className="modal-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => {
                    setUploadOpen(false);
                    setUploadFile(null);
                  }}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="primary-button"
                  disabled={uploading}
                >
                  {uploading ? (
                    <>
                      <RefreshCw
                        size={17}
                        className="spin"
                      />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload size={17} />
                      Upload File
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, subtitle, icon: Icon, trend }) {
  return (
    <div className="metric-card">
      <div className="metric-card-top">
        <div className="metric-card-icon">
          {Icon && <Icon size={20} />}
        </div>

        {trend && (
          <span className="metric-card-trend">
            {trend}
          </span>
        )}
      </div>

      <div className="metric-card-label">
        {label}
      </div>

      <div className="metric-card-value">
        {value}
      </div>

      {subtitle && (
        <div className="metric-card-subtitle">
          {subtitle}
        </div>
      )}
    </div>
  );
}

function PageHeading({ kicker, title, description, actions }) {
  return (
    <div className="page-heading">
      <div>
        {kicker && (
          <div className="page-heading-kicker">
            {kicker}
          </div>
        )}

        <h1 className="page-heading-title">
          {title}
        </h1>

        {description && (
          <p className="page-heading-description">
            {description}
          </p>
        )}
      </div>

      {actions && (
        <div className="page-heading-actions">
          {actions}
        </div>
      )}
    </div>
  );
}



function DashboardPage({
  datasets,
  selectedDataset,
  selectedDatasetId,
  setSelectedDatasetId,
  loading,
  metrics,
  chartData,
  chartType,
  setChartType,
  chartColumn,
  setChartColumn,
  groupColumn,
  setGroupColumn,
  numericColumns,
  categoricalColumns,
  columns,
  datasetRows,
  onUpload,
  onDelete,
  onNavigate,
}) {
  return (
    <div className="page">
      <div className="hero">
        <div>
          <span className="section-kicker">
            BUSINESS OVERVIEW
          </span>
          <h2>Business dashboard</h2>
          <p>
            Your dashboard is generated from the datasets
            stored in your business database.
          </p>
        </div>

        <button
          type="button"
          className="primary-button"
          onClick={onUpload}
        >
          <Plus size={18} />
          Upload Data
        </button>
      </div>

      {!datasets.length && !loading ? (
        <EmptyState
          icon={Database}
          title="No business data yet"
          text="Upload your first CSV, Excel, JSON or PDF file to start building the dashboard."
          buttonText="Upload your first file"
          onClick={onUpload}
        />
      ) : (
        <>
          <div className="dataset-strip">
            <div>
              <span className="section-kicker">
                ACTIVE DATASET
              </span>

              <select
                value={selectedDatasetId || ""}
                onChange={(event) =>
                  setSelectedDatasetId(
                    Number(event.target.value)
                  )
                }
              >
                {datasets.map((dataset) => (
                  <option
                    key={dataset.id}
                    value={dataset.id}
                  >
                    {dataset.name}
                  </option>
                ))}
              </select>
            </div>

            {selectedDataset && (
              <div className="dataset-meta">
                <span>
                  {selectedDataset.type}
                </span>
                <span>
                  {formatNumber(metrics.rows)} rows
                </span>
                <span>
                  {formatNumber(metrics.columns)} columns
                </span>

                <button
                  type="button"
                  className="danger-icon"
                  onClick={() =>
                    onDelete(selectedDataset.id)
                  }
                  title="Delete dataset"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            )}
          </div>

          <div className="metric-grid">
            <MetricCard
              icon={Database}
              label="Rows"
              value={formatNumber(metrics.rows)}
            />

            <MetricCard
              icon={FileText}
              label="Columns"
              value={formatNumber(metrics.columns)}
            />

            <MetricCard
              icon={Activity}
              label="Numeric Total"
              value={
                chartColumn
                  ? formatMoney(metrics.numericTotal)
                  : "-"
              }
            />

            <MetricCard
              icon={BarChart3}
              label="Unique Groups"
              value={formatNumber(
                metrics.uniqueGroups
              )}
            />
          </div>

          {selectedDataset && (
            <div className="chart-card">
              <div className="chart-header">
                <div>
                  <span className="section-kicker">
                    VISUAL ANALYSIS
                  </span>
                  <h3>
                    {chartColumn
                      ? `${chartColumn} analysis`
                      : "Dataset analysis"}
                  </h3>
                </div>

                <div className="chart-controls">
                  <select
                    value={groupColumn}
                    onChange={(event) =>
                      setGroupColumn(event.target.value)
                    }
                  >
                    <option value="">
                      No grouping
                    </option>

                    {categoricalColumns.map(
                      (column) => (
                        <option
                          key={column}
                          value={column}
                        >
                          Group: {column}
                        </option>
                      )
                    )}
                  </select>

                  <select
                    value={chartColumn}
                    onChange={(event) =>
                      setChartColumn(event.target.value)
                    }
                  >
                    <option value="">
                      Numeric field
                    </option>

                    {numericColumns.map(
                      (column) => (
                        <option
                          key={column}
                          value={column}
                        >
                          {column}
                        </option>
                      )
                    )}
                  </select>

                  <ChartSelector
                    value={chartType}
                    onChange={setChartType}
                  />
                </div>
              </div>

              {chartData.length ? (
                <Chart
                  type={chartType}
                  data={chartData}
                />
              ) : (
                <div className="chart-empty">
                  <BarChart3 size={30} />
                  <p>
                    Select a numeric field to generate
                    a chart.
                  </p>
                </div>
              )}
            </div>
          )}

          {datasetRows.length > 0 && (
            <div className="table-card">
              <div className="table-header">
                <div>
                  <span className="section-kicker">
                    DATA PREVIEW
                  </span>
                  <h3>Latest records</h3>
                </div>

                <span className="record-count">
                  Showing {Math.min(
                    datasetRows.length,
                    20
                  )} of{" "}
                  {formatNumber(datasetRows.length)}
                </span>
              </div>

              <DataTable
                rows={datasetRows.slice(0, 20)}
                columns={columns}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function DataPage({
  datasets,
  selectedDatasetId,
  setSelectedDatasetId,
  onDelete,
  onUpload,
  loading,
}) {
  return (
    <div className="page">
      <PageHeading
        kicker="DATA MANAGEMENT"
        title="Business Data"
        description="Manage the datasets stored in your dynamic business database."
        action={
          <button
            type="button"
            className="primary-button"
            onClick={onUpload}
          >
            <Upload size={17} />
            Upload Data
          </button>
        }
      />

      {loading ? (
        <LoadingState />
      ) : !datasets.length ? (
        <EmptyState
          icon={Database}
          title="No datasets found"
          text="Upload data to create your first dataset."
          buttonText="Upload Data"
          onClick={onUpload}
        />
      ) : (
        <div className="dataset-grid">
          {datasets.map((dataset) => (
            <div
              className={`dataset-card ${
                selectedDatasetId === dataset.id
                  ? "selected"
                  : ""
              }`}
              key={dataset.id}
            >
              <div className="dataset-card-icon">
                <Database size={21} />
              </div>

              <div className="dataset-card-content">
                <span className="dataset-type">
                  {dataset.type}
                </span>

                <h3>{dataset.name}</h3>

                <div className="dataset-stats">
                  <span>
                    {formatNumber(dataset.rows)} rows
                  </span>
                  <span>
                    {formatNumber(dataset.columns)} cols
                  </span>
                </div>
              </div>

              <div className="dataset-card-actions">
                <button
                  type="button"
                  className="secondary-button small"
                  onClick={() =>
                    setSelectedDatasetId(dataset.id)
                  }
                >
                  View
                </button>

                <button
                  type="button"
                  className="danger-icon"
                  onClick={() =>
                    onDelete(dataset.id)
                  }
                  title="Delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AnalyticsPage({
  datasets,
  selectedDataset,
  datasetRows,
  columns,
  chartData,
  chartType,
  setChartType,
  chartColumn,
  setChartColumn,
  groupColumn,
  setGroupColumn,
  numericColumns,
  categoricalColumns,
}) {
  return (
    <div className="page">
      <PageHeading
        kicker="ANALYTICS"
        title="Business Analytics"
        description="Explore uploaded data using interactive visualizations."
      />

      {!datasets.length ? (
        <EmptyState
          icon={BarChart3}
          title="Analytics needs data"
          text="Upload a dataset before creating visualizations."
        />
      ) : !selectedDataset ? (
        <LoadingState />
      ) : (
        <div className="chart-card">
          <div className="chart-header">
            <div>
              <span className="section-kicker">
                DATASET
              </span>
              <h3>{selectedDataset.name}</h3>
            </div>

            <div className="chart-controls">
              <select
                value={groupColumn}
                onChange={(event) =>
                  setGroupColumn(event.target.value)
                }
              >
                <option value="">
                  No grouping
                </option>

                {categoricalColumns.map(
                  (column) => (
                    <option
                      key={column}
                      value={column}
                    >
                      Group: {column}
                    </option>
                  )
                )}
              </select>

              <select
                value={chartColumn}
                onChange={(event) =>
                  setChartColumn(event.target.value)
                }
              >
                <option value="">
                  Numeric field
                </option>

                {numericColumns.map(
                  (column) => (
                    <option
                      key={column}
                      value={column}
                    >
                      {column}
                    </option>
                  )
                )}
              </select>

              <ChartSelector
                value={chartType}
                onChange={setChartType}
              />
            </div>
          </div>

          {chartData.length ? (
            <Chart
              type={chartType}
              data={chartData}
            />
          ) : (
            <div className="chart-empty">
              <BarChart3 size={30} />
              <p>
                Select a numeric field to visualize
                {datasetRows.length
                  ? ` the ${datasetRows.length} records.`
                  : "."}
              </p>
            </div>
          )}

          <div className="analytics-info">
            <span>
              Dataset: <strong>{selectedDataset.name}</strong>
            </span>

            <span>
              Records:{" "}
              <strong>
                {formatNumber(datasetRows.length)}
              </strong>
            </span>

            <span>
              Fields:{" "}
              <strong>
                {formatNumber(columns.length)}
              </strong>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function ReportsPage({
  datasets,
  selectedDataset,
  datasetRows,
}) {
  const rows = Array.isArray(datasetRows)
    ? datasetRows
    : [];

  const recordCount = Number(
    selectedDataset?.rows ?? rows.length ?? 0
  ) || 0;

  const columnCount = Number(
    selectedDataset?.columns ??
    selectedDataset?.columnNames?.length ??
    (rows.length ? Object.keys(rows[0]).length : 0)
  ) || 0;

  const columnNames =
    Array.isArray(selectedDataset?.columnNames) &&
    selectedDataset.columnNames.length
      ? selectedDataset.columnNames
      : rows.length
        ? Object.keys(rows[0])
        : [];

  const numericColumns = columnNames.filter((column) => {
    return rows.some((row) => {
      const value = row?.[column];

      if (typeof value === "number") {
        return Number.isFinite(value);
      }

      if (typeof value === "string") {
        const cleaned = value
          .replace(/[?,%\s,]/g, "")
          .trim();

        return (
          cleaned !== "" &&
          Number.isFinite(Number(cleaned))
        );
      }

      return false;
    });
  });

  const totalForColumn = (column) => {
    return rows.reduce((total, row) => {
      const value = row?.[column];

      if (typeof value === "number") {
        return total + value;
      }

      if (typeof value === "string") {
        const cleaned = value
          .replace(/[?,%\s,]/g, "")
          .trim();

        const numeric = Number(cleaned);

        return Number.isFinite(numeric)
          ? total + numeric
          : total;
      }

      return total;
    }, 0);
  };

  const formatReportValue = (value, column = "") => {
    if (
      value === null ||
      value === undefined ||
      value === ""
    ) {
      return "ï¿½";
    }

    if (typeof value === "number") {
      const name = column.toLowerCase();

      const moneyField =
        name.includes("amount") ||
        name.includes("price") ||
        name.includes("sales") ||
        name.includes("profit") ||
        name.includes("cost") ||
        name.includes("discount") ||
        name.includes("gst") ||
        name.includes("total") ||
        name.includes("value");

      if (moneyField) {
        return `\u20B9${value.toLocaleString("en-IN", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}`;
      }

      return value.toLocaleString("en-IN");
    }

    return String(value);
  };

  const getDatasetName = () =>
    selectedDataset?.name ||
    selectedDataset?.original_filename ||
    "No dataset selected";

  const previewRows = rows.slice(0, 100);

  const sourceUrl = selectedDataset?.stored_filename
    ? `http://127.0.0.1:8000/download/${encodeURIComponent(
        selectedDataset.stored_filename
      )}`
    : null;

  return (
    <div className="page">

      <PageHeading
        kicker="REPORTING"
        title="Business Reports"
        description="Review, analyse and export reports from your uploaded business data."
      />

      {/* Active Dataset */}
      <div className="report-hero">
        <div>
          <span className="section-kicker">
            ACTIVE DATASET
          </span>

          <h2>{getDatasetName()}</h2>

          <p>
            {formatNumber(recordCount)} records
            {columnCount
              ? ` â€¢ ${formatNumber(columnCount)} columns`
              : ""}
          </p>
        </div>

        <div className="report-status">
          <span className="status-dot" />
          {recordCount > 0 ? "Data ready" : "Metadata available"}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="report-summary-grid">

        <div className="report-summary-card">
          <div className="report-summary-icon">
            <Database size={19} />
          </div>

          <span>Records</span>

          <strong>
            {formatNumber(recordCount)}
          </strong>

          <small>
            Available in current dataset
          </small>
        </div>

        <div className="report-summary-card">
          <div className="report-summary-icon">
            <Columns3 size={19} />
          </div>

          <span>Fields</span>

          <strong>
            {formatNumber(columnCount)}
          </strong>

          <small>
            Detected dataset columns
          </small>
        </div>

        <div className="report-summary-card">
          <div className="report-summary-icon">
            <BarChart3 size={19} />
          </div>

          <span>Numeric fields</span>

          <strong>
            {formatNumber(numericColumns.length)}
          </strong>

          <small>
            Available when preview data is loaded
          </small>
        </div>

        <div className="report-summary-card">
          <div className="report-summary-icon">
            <FileText size={19} />
          </div>

          <span>Datasets</span>

          <strong>
            {formatNumber(datasets.length)}
          </strong>

          <small>
            Stored in database
          </small>
        </div>

      </div>

      {/* Report Actions */}
      <div className="report-action-panel">

        <div>
          <span className="section-kicker">
            REPORT EXPORT
          </span>

          <h3>Generate business report</h3>

          <p>
            Export the current dataset using the
            existing backend reporting system.
          </p>
        </div>

        <div className="report-action-buttons">

          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noreferrer"
              className="secondary-button"
            >
              <Download size={16} />
              Download Source
            </a>
          )}

          {selectedDataset && (
            <button
              type="button"
              className="primary-button"
              onClick={() => {
                window.dispatchEvent(
                  new CustomEvent("navigate-to-agent")
                );
              }}
            >
              <Sparkles size={16} />
              Generate with AI
            </button>
          )}

        </div>
      </div>

      {/* Numeric Overview */}
      {numericColumns.length > 0 && rows.length > 0 && (
        <div className="report-section">

          <div className="report-section-heading">
            <div>
              <span className="section-kicker">
                NUMERIC OVERVIEW
              </span>

              <h3>Key field totals</h3>
            </div>

            <span className="result-count">
              {numericColumns.length} fields
            </span>
          </div>

          <div className="report-metric-grid">

            {numericColumns
              .slice(0, 8)
              .map((column) => (
                <div
                  className="report-metric-card"
                  key={column}
                >
                  <span>{column}</span>

                  <strong>
                    {formatReportValue(
                      totalForColumn(column),
                      column
                    )}
                  </strong>

                  <small>
                    Total across current records
                  </small>
                </div>
              ))}

          </div>
        </div>
      )}

      {/* Dataset Preview */}
      <div className="report-section">

        <div className="report-section-heading">
          <div>
            <span className="section-kicker">
              REPORT PREVIEW
            </span>

            <h3>Dataset records</h3>
          </div>

          <span className="result-count">
            {rows.length > 0
              ? `Showing ${Math.min(rows.length, 100)}`
              : `${formatNumber(recordCount)} records`}
          </span>
        </div>

        <div className="report-preview-card">

          {previewRows.length > 0 ? (
            <div className="report-preview-table">

              <table>
                <thead>
                  <tr>
                    {columnNames.map((column) => (
                      <th key={column}>
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {previewRows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {columnNames.map((column) => (
                        <td key={column}>
                          {formatReportValue(
                            row?.[column],
                            column
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>

            </div>
          ) : (
            <div className="report-empty">

              <Database size={32} />

              <h4>
                Dataset metadata is ready
              </h4>

              <p>
                This dataset contains{" "}
                <strong>
                  {formatNumber(recordCount)}
                </strong>{" "}
                records across{" "}
                <strong>
                  {formatNumber(columnCount)}
                </strong>{" "}
                fields.
              </p>

              <small>
                The current dataset detail endpoint provides
                metadata. The full record preview will appear
                once the data-preview endpoint is connected.
              </small>

            </div>
          )}

        </div>
      </div>

      {/* Dataset Information */}
      <div className="report-info-strip">

        <div>
          <span>Source</span>
          <strong>
            {selectedDataset?.original_filename ||
              getDatasetName()}
          </strong>
        </div>

        <div>
          <span>Records</span>
          <strong>
            {formatNumber(recordCount)}
          </strong>
        </div>

        <div>
          <span>Fields</span>
          <strong>
            {formatNumber(columnCount)}
          </strong>
        </div>

        <div>
          <span>File type</span>
          <strong>
            {selectedDataset?.fileType
              ? selectedDataset.fileType.toUpperCase()
              : "ï¿½"}
          </strong>
        </div>

      </div>

    </div>
  );
}
function UploadPage({
  datasets,
  onUpload,
}) {
  return (
    <div className="page">
      <PageHeading
        kicker="DATA IMPORT"
        title="Upload Data"
        description="Add CSV, Excel, JSON or PDF business data to the dynamic database."
        action={
          <button
            type="button"
            className="primary-button"
            onClick={onUpload}
          >
            <Upload size={17} />
            Choose File
          </button>
        }
      />

      <div className="upload-panel">
        <div className="upload-icon">
          <Upload size={28} />
        </div>

        <h3>Import business data</h3>

        <p>
          Files are sent to the existing backend
          <strong> /upload-data </strong>
          endpoint and become available to the dashboard,
          analytics and AI agent.
        </p>

        <button
          type="button"
          className="primary-button"
          onClick={onUpload}
        >
          <Plus size={17} />
          Upload File
        </button>
      </div>

      <div className="simple-info">
        <span>
          Current datasets
        </span>
        <strong>
          {formatNumber(datasets.length)}
        </strong>
      </div>
    </div>
  );
}

function HistoryPage({
  datasets,
  onDelete,
  onRefresh,
}) {
  const [historySearch, setHistorySearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");

  const historyItems = Array.isArray(datasets)
    ? datasets
    : [];

  const fileType = (dataset) => {
    const value = String(
      dataset?.type ||
      dataset?.data_type ||
      dataset?.file_type ||
      ""
    ).toLowerCase();

    const filename = String(
      dataset?.name ||
      dataset?.original_filename ||
      ""
    ).toLowerCase();

    if (value.includes("excel") || value.includes("xlsx")) {
      return "Excel";
    }

    if (value.includes("csv") || filename.endsWith(".csv")) {
      return "CSV";
    }

    if (value.includes("json") || filename.endsWith(".json")) {
      return "JSON";
    }

    if (value.includes("pdf") || filename.endsWith(".pdf")) {
      return "PDF";
    }

    if (value.includes("word") || filename.endsWith(".docx")) {
      return "DOCX";
    }

    return dataset?.type || "Dataset";
  };

  const formatDate = (dataset) => {
    const rawDate =
      dataset?.uploaded_at ||
      dataset?.created_at ||
      dataset?.upload_date ||
      dataset?.createdAt ||
      dataset?.created_at;

    if (!rawDate) {
      return "Upload date unavailable";
    }

    const date = new Date(rawDate);

    if (Number.isNaN(date.getTime())) {
      return String(rawDate);
    }

    return date.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const filteredHistory = historyItems.filter((dataset) => {
    const name = String(
      dataset?.name ||
      dataset?.original_filename ||
      ""
    ).toLowerCase();

    const type = fileType(dataset).toLowerCase();
    const query = historySearch.trim().toLowerCase();

    const matchesSearch =
      !query ||
      name.includes(query) ||
      type.includes(query);

    const matchesType =
      typeFilter === "all" ||
      type === typeFilter.toLowerCase();

    return matchesSearch && matchesType;
  });

  const totalRows = historyItems.reduce(
    (sum, dataset) =>
      sum + (Number(dataset?.rows ?? dataset?.row_count ?? 0) || 0),
    0
  );

  const totalColumns = historyItems.reduce(
    (sum, dataset) =>
      sum +
      (Number(dataset?.columns ?? dataset?.column_count ?? 0) || 0),
    0
  );

  return (
    <div className="page history-page">
      <PageHeading
        kicker="DATA HISTORY"
        title="Upload History"
        description="Manage every dataset currently stored in your business database."
        action={
          <button
            type="button"
            className="secondary-button"
            onClick={onRefresh}
            title="Refresh upload history"
          >
            <RefreshCw size={17} />
            Refresh
          </button>
        }
      />

      {historyItems.length > 0 && (
        <>
          <div className="history-overview">
            <div className="history-stat">
              <div className="history-stat-icon">
                <Database size={18} />
              </div>
              <div>
                <span>Total datasets</span>
                <strong>{formatNumber(historyItems.length)}</strong>
              </div>
            </div>

            <div className="history-stat">
              <div className="history-stat-icon">
                <FileText size={18} />
              </div>
              <div>
                <span>Total records</span>
                <strong>{formatNumber(totalRows)}</strong>
              </div>
            </div>

            <div className="history-stat">
              <div className="history-stat-icon">
                <Columns3 size={18} />
              </div>
              <div>
                <span>Total columns</span>
                <strong>{formatNumber(totalColumns)}</strong>
              </div>
            </div>
          </div>

          <div className="history-toolbar">
            <div className="history-search">
              <Search size={17} />
              <input
                type="text"
                value={historySearch}
                onChange={(event) =>
                  setHistorySearch(event.target.value)
                }
                placeholder="Search uploaded files..."
              />
            </div>

            <div className="history-filter">
              <select
                value={typeFilter}
                onChange={(event) =>
                  setTypeFilter(event.target.value)
                }
                aria-label="Filter datasets by file type"
              >
                <option value="all">All file types</option>
                <option value="excel">Excel</option>
                <option value="csv">CSV</option>
                <option value="json">JSON</option>
                <option value="pdf">PDF</option>
                <option value="docx">DOCX</option>
              </select>
            </div>
          </div>
        </>
      )}

      {!historyItems.length ? (
        <EmptyState
          icon={History}
          title="No upload history"
          text="Uploaded datasets will appear here once you add business data."
        />
      ) : !filteredHistory.length ? (
        <EmptyState
          icon={Search}
          title="No matching datasets"
          text="Try a different file name or change the file type filter."
        />
      ) : (
        <div className="history-list">
          <div className="history-list-header">
            <span>Dataset</span>
            <span>Records</span>
            <span>Structure</span>
            <span>Uploaded</span>
            <span>Action</span>
          </div>

          {filteredHistory.map((dataset, index) => {
            const name =
              dataset?.name ||
              dataset?.original_filename ||
              `Dataset ${dataset?.id ?? index + 1}`;

            const rows =
              Number(
                dataset?.rows ??
                dataset?.row_count ??
                0
              ) || 0;

            const columns =
              Number(
                dataset?.columns ??
                dataset?.column_count ??
                0
              ) || 0;

            const type = fileType(dataset);

            return (
              <div
                className="history-row"
                key={dataset?.id ?? `${name}-${index}`}
              >
                <div className="history-dataset-cell">
                  <div className="history-file-icon">
                    <FileText size={19} />
                  </div>

                  <div className="history-main">
                    <strong title={name}>
                      {name}
                    </strong>

                    <div className="history-file-sub">
                      <span className="history-type-badge">
                        {type}
                      </span>

                      <span>
                        Dataset ID #{dataset?.id ?? "—"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="history-value">
                  <strong>{formatNumber(rows)}</strong>
                  <span>rows</span>
                </div>

                <div className="history-value">
                  <strong>{formatNumber(columns)}</strong>
                  <span>columns</span>
                </div>

                <div className="history-date">
                  <span>{formatDate(dataset)}</span>
                </div>

                <div className="history-actions">
                  <button
                    type="button"
                    className="history-action-button"
                    onClick={() => {
                      window.dispatchEvent(
                        new CustomEvent(
                          "vyapar-select-dataset",
                          {
                            detail: {
                              datasetId: dataset?.id,
                            },
                          }
                        )
                      );
                    }}
                    title="Use this dataset"
                  >
                    <Database size={16} />
                    Use
                  </button>

                  <button
                    type="button"
                    className="danger-icon"
                    onClick={() =>
                      onDelete(dataset.id)
                    }
                    title="Delete dataset"
                  >
                    <Trash2 size={17} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AgentPage({
  question,
  setQuestion,
  loading,
  result,
  askAgent,
}) {

  const [chartType, setChartType] = useState(
    result?.chart?.type || "bar"
  );

  useEffect(() => {
    if (result?.chart?.type) {
      setChartType(result.chart.type);
    }
  }, [result]);
  const suggestions = [
    "Show total sales month wise",
    "Show sales and profit quarter wise",
    "Which customer has the highest sales?",
    "Show quantity and sales product wise",
    "Show invoice count and discount year wise",
  ];

  const rows =
    result?.result?.rows ||
    result?.rows ||
    result?.data ||
    [];

  const columns = rows.length
    ? Object.keys(rows[0])
    : [];

  const chartSeries = result?.chart?.series || [];

  const formatReportValue = (value, column = "") => {
    if (value === null || value === undefined || value === "") {
      return "â€”";
    }

    if (typeof value === "number") {
      const lower = column.toLowerCase();

      const isMoney =
        lower.includes("amount") ||
        lower.includes("sales") ||
        lower.includes("discount") ||
        lower.includes("profit") ||
        lower.includes("cost") ||
        lower.includes("gst") ||
        lower.includes("price") ||
        lower.includes("total");

      if (isMoney) {
        return `â‚¹${value.toLocaleString("en-IN", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}`;
      }

      return value.toLocaleString("en-IN");
    }

    return String(value);
  };

   const getMetricValue = (seriesItem) => {
    const key = seriesItem?.key;

    if (!key || !result?.chart?.data?.length) {
      return null;
    }

    return result.chart.data.reduce(
      (total, item) =>
        total + numericValue(item?.[key]),
      0
    );
  };

  const formatINR = (value) => {
    const number = numericValue(value);

    return `\u20B9${number.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  const formatMetricValue = (value, metric) => {
    const number = numericValue(value);

    if (metric?.format === "integer") {
      return number.toLocaleString("en-IN", {
        maximumFractionDigits: 0,
      });
    }

    if (metric?.prefix === "â‚¹") {
      return formatINR(number);
    }

    return number.toLocaleString("en-IN", {
      maximumFractionDigits: 2,
    });
  };

  const primaryMetric = chartSeries[0];

const analysisData =
  primaryMetric && result?.chart?.data
    ? result.chart.data
        .map((item) => ({
          label:
            item?.label ??
            item?.[result.chart?.group_key] ??
            item?.Date ??
            item?.Month ??
            item?.Year ??
            "",
          value: numericValue(
            item?.[primaryMetric.key]
          ),
        }))
        .filter((item) =>
          Number.isFinite(item.value)
        )
    : [];

const analysisGroupKey =
  String(
    result?.chart?.group_by ||
    result?.chart?.group_key ||
    ""
  ).toLowerCase();

const temporalAnalysis =
  ["month", "year", "quarter", "date", "week"].some(
    (key) => analysisGroupKey.includes(key)
  );

  const firstAnalysisValue =
    temporalAnalysis && analysisData.length >= 2
      ? analysisData[0].value
      : null;

  const lastAnalysisValue =
    temporalAnalysis && analysisData.length >= 2
      ? analysisData[analysisData.length - 1].value
      : null;

  const analysisDifference =
    firstAnalysisValue !== null &&
    lastAnalysisValue !== null
      ? lastAnalysisValue - firstAnalysisValue
      : null;

  const analysisPercentage =
    firstAnalysisValue !== null &&
    firstAnalysisValue !== 0 &&
    analysisDifference !== null
      ? (analysisDifference / firstAnalysisValue) * 100
      : null;

  const analysisDirection =
    analysisDifference === null
      ? "neutral"
      : analysisDifference > 0
      ? "up"
      : analysisDifference < 0
      ? "down"
      : "neutral";
  return (
    <div className="page">
      <PageHeading
        kicker="AI BUSINESS AGENT"
        title="Ask your business"
        description="Ask questions about the datasets stored in your business database."
      />

      <div className="agent-layout">
        <div className="agent-main-card">

          {/* Agent Header */}
          <div className="agent-intro">
            <div className="agent-icon">
              <Bot size={25} />
            </div>

            <div>
              <h3>Business Intelligence Agent</h3>
              <p>
                Ask questions about sales, customers,
                products, GST, attendance and more.
              </p>
            </div>
          </div>

          {/* Suggestions */}
          <div className="suggestion-list">
            {suggestions.map((suggestion) => (
              <button
                type="button"
                key={suggestion}
                onClick={() => askAgent(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>

          {/* Question Input */}
          <form
            className="agent-input"
            onSubmit={(event) => {
              event.preventDefault();
              askAgent();
            }}
          >
            <input
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              placeholder="Ask something like: Show total sales month wise"
            />

            <button
              type="submit"
              className="primary-button"
              disabled={loading || !question.trim()}
            >
              {loading ? (
                <RefreshCw
                  size={17}
                  className="spin"
                />
              ) : (
                <Send size={17} />
              )}

              {loading ? "Running..." : "Ask"}
            </button>
          </form>

          {/* Loading */}
          {loading && (
            <div className="agent-loading">
              <RefreshCw
                size={20}
                className="spin"
              />

              <div>
                <strong>Analysing your data...</strong>
                <span>
                  Selecting the dataset, calculating
                  the result and preparing the report.
                </span>
              </div>
            </div>
          )}

          {/* Result */}
          {result && !loading && (
            <div className="agent-result">

              {/* Result Header */}
              <div className="result-header">
                <div>
                  <span className="section-kicker">
                    BUSINESS ANALYSIS
                  </span>

                  <h3>
                    {result.chart?.title ||
                      "Analysis Result"}
                  </h3>

                  {result.chart?.description && (
                    <p>
                      {result.chart.description}
                    </p>
                  )}
                </div>

                <div className="result-status">
                  <span className="status-dot" />
                  Completed
                </div>
              </div>

              {/* KPI Cards */}
              {chartSeries.length > 0 && (
                <div className="agent-kpi-grid">
                  {chartSeries.map((metric) => {
                    const total = getMetricValue(metric);

                    return (
                      <div
                        className="agent-kpi-card"
                        key={metric.key}
                      >
                        <div className="agent-kpi-top">
                          <span>
                            {metric.label ||
                              metric.key}
                          </span>

                          <Activity size={17} />
                        </div>

                        <strong>
                          {formatMetricValue(total, metric)}
                        </strong>

                        <small>
                          Across{" "}
                          {result.chart.row_count ||
                            rows.length ||
                            0}{" "}
                          periods
                        </small>
                      </div>
                    );
                  })}
                </div>
              )}

              

              {/* Charts */}
              {result.chart?.enabled &&
                result.chart?.data?.length > 0 && (
                  <div className="agent-visual-section">
                    <div className="agent-section-heading">
                      <div>
                        <span className="section-kicker">
                          VISUAL ANALYSIS
                        </span>

                        <h3>
                          Trends & comparison
                        </h3>
                      </div>

                      <span className="result-count">
                        {result.chart.data.length}{" "}
                        periods
                      </span>
                    </div>
                    <div className="agent-chart-controls">
                      <span>Chart type</span>

                      <ChartSelector
                        value={chartType}
                        onChange={setChartType}
                      />
                    </div>
                    <div className="agent-charts-grid">
                      {chartSeries.length > 0 ? (
                        chartSeries.map((metric) => (
                          <div
                            className="agent-single-chart"
                            key={metric.key}
                          >
                            <div className="single-chart-header">
                              <div>
                                <span>
                                  {metric.label ||
                                    metric.key}
                                </span>

                                <strong>
                                  {metric.format ===
                                  "integer"
                                    ? "Count"
                                    : metric.prefix ||
                                      ""}
                                </strong>
                              </div>
                            </div>

                            <Chart
                              type={chartType}
                              data={result.chart.data}
                              series={[metric]}
                            />
                          </div>
                        ))
                      ) : (
                        <div className="agent-single-chart">
                          <Chart
                            type={
                              result.chart.type ||
                              "bar"
                            }
                            data={result.chart.data}
                            series={result.chart.series}
                            title={result.chart.title}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                )}



              {/* Data Report */}
              {rows.length > 0 && (
                <div className="agent-report-section">

                  <div className="agent-section-heading">
                    <div>
                      <span className="section-kicker">
                        DATA REPORT
                      </span>

                      <h3>Detailed results</h3>
                    </div>

                    <span className="result-count">
                      {rows.length}{" "}
                      {rows.length === 1
                        ? "record"
                        : "records"}
                    </span>
                  </div>

                  <div className="agent-table-card">
                    <div className="agent-table-scroll">
                      <table className="agent-report-table">
                        <thead>
                          <tr>
                            {columns.map((column) => (
                              <th key={column}>
                                {column}
                              </th>
                            ))}
                          </tr>
                        </thead>

                        <tbody>
                          {rows.map((row, rowIndex) => (
                            <tr key={rowIndex}>
                              {columns.map(
                                (column) => (
                                  <td
                                    key={`${rowIndex}-${column}`}
                                  >
                                    {formatReportValue(
                                      row[column],
                                      column
                                    )}
                                  </td>
                                )
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* Performance Analysis */}
              {analysisPercentage !== null &&
                primaryMetric && (
                  <div className="agent-analysis-card">
                    <div className="agent-analysis-main">
                      <span className="section-kicker">
                        PERFORMANCE
                      </span>

                      <div
                        className={`agent-analysis-value ${analysisDirection}`}
                      >
                        {analysisDirection === "up"
                          ? "â†‘"
                          : analysisDirection === "down"
                          ? "â†“"
                          : "â†’"}{" "}
                        {Math.abs(
                          analysisPercentage
                        ).toFixed(2)}
                        %
                      </div>

                      <strong>
                        {primaryMetric.label ||
                          primaryMetric.key}{" "}
                        {analysisDirection === "up"
                          ? "increased"
                          : analysisDirection ===
                            "down"
                          ? "decreased"
                          : "remained unchanged"}{" "}
                        over the selected periods.
                      </strong>
                    </div>

                    <div className="agent-analysis-details">
                      <div>
                        <span>
                          {analysisData[0]?.label ||
                            "First period"}
                        </span>

                        <strong>
                          {formatMetricValue(
                            firstAnalysisValue,
                            primaryMetric
                          )}
                        </strong>
                      </div>

                      <div>
                        <span>
                          {analysisData[
                            analysisData.length - 1
                          ]?.label ||
                            "Latest period"}
                        </span>

                        <strong>
                          {formatMetricValue(
                            lastAnalysisValue,
                            primaryMetric
                          )}
                        </strong>
                      </div>

                      <div>
                        <span>Difference</span>

                        <strong>
                          {analysisDifference > 0
                            ? "+"
                            : analysisDifference < 0
                            ? "-"
                            : ""}
                          {primaryMetric.prefix ===
                          "â‚¹"
                            ? formatINR(
                                Math.abs(
                                  analysisDifference
                                )
                              )
                            : Math.abs(
                                analysisDifference
                              ).toLocaleString(
                                "en-IN",
                                {
                                  maximumFractionDigits:
                                    2,
                                }
                              )}
                        </strong>
                      </div>
                    </div>
                  </div>
                )}

              {/* Report Footer */}
              <div className="agent-report-footer">

                <div className="report-source">
                  <Database size={17} />

                  <div>
                    <span>DATA SOURCE</span>

                    <strong>
                      {result.dataset
                        ?.original_filename ||
                        result.dataset_name ||
                        "Business dataset"}
                    </strong>
                  </div>
                </div>

                <div className="report-source">
                  <FileText size={17} />

                  <div>
                    <span>RECORDS ANALYSED</span>

                    <strong>
                      {formatNumber(
                        result.result
                          ?.filtered_rows ??
                          result.result
                            ?.source_rows ??
                          rows.length
                      )}
                    </strong>
                  </div>
                </div>

                {result.download_url && (
                  <div className="report-download-area">
                    <div className="report-download-info">
                      <div className="report-download-icon">
                        <Download size={17} />
                      </div>

                      <div>
                        <span>REPORT READY</span>
                        <strong>Download your analysed report</strong>
                      </div>
                    </div>

                    <a
                      href={`http://127.0.0.1:8000${
                        result.download_url
                      }`}
                      download
                      className="report-download-button"
                    >
                      <Download size={16} />
                      Download Report
                    </a>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Side Information */}
        <div className="agent-side-card">
          <Bot size={22} />

          <h3>What you can ask</h3>

          <p>
            Sales, purchases, customers, products,
            attendance, GST, payments, inventory and
            other uploaded business datasets.
          </p>

          <div className="agent-tags">
            <span>Sales</span>
            <span>Customers</span>
            <span>Products</span>
            <span>GST</span>
            <span>Attendance</span>
            <span>Analytics</span>
          </div>

          <div className="agent-side-divider" />

          <div className="agent-tip">
            <Lightbulb size={17} />

            <div>
              <strong>Try a natural question</strong>
              <p>
                For example, ask:
                <br />
                "Show sales and profit month wise"
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

function ChartSelector({ value, onChange }) {
  return (
    <div className="chart-type-selector">
      <button
        type="button"
        className={value === "bar" ? "selected" : ""}
        onClick={() => onChange("bar")}
        title="Bar chart"
      >
        <BarChart3 size={16} />
        <span>Bar</span>
      </button>

      <button
        type="button"
        className={value === "line" ? "selected" : ""}
        onClick={() => onChange("line")}
        title="Line chart"
      >
        <Activity size={16} />
        <span>Line</span>
      </button>

      <button
        type="button"
        className={value === "pie" ? "selected" : ""}
        onClick={() => onChange("pie")}
        title="Pie chart"
      >
        <PieChart size={16} />
        <span>Pie</span>
      </button>

      <button
        type="button"
        className={
          value === "scatter" ? "selected" : ""
        }
        onClick={() => onChange("scatter")}
        title="Scatter chart"
      >
        <Activity size={16} />
        <span>Scatter</span>
      </button>
    </div>
  );
}

function Chart({ type, data, series = null, title = "" }) {

  const [selectedPieSlice, setSelectedPieSlice] =
    useState(null);
  if (!data?.length) return null;

  const chartSeries =
    series?.length
      ? series
      : [
          {
            key: "value",
            field: "value",
            label: "Value",
            format: "number",
          },
        ];

  const normalizedData = data.map((item, index) => {
    const row = {
      ...item,
      label:
        item?.label ??
        item?.name ??
        item?.period ??
        item?.date ??
        `Item ${index + 1}`,
    };

    chartSeries.forEach((metric) => {
      const rawValue =
        item?.[metric.key] ??
        item?.[metric.field] ??
        0;

      row[metric.key] = numericValue(rawValue);
    });

    return row;
  });

  const formatMetricValue = (value, metric) => {
    const numeric = numericValue(value);

    if (metric?.format === "integer") {
      return Math.round(numeric).toLocaleString("en-IN");
    }

    if (metric?.format === "compact") {
        if (numeric >= 10000000) {
            return `\u20B9${(numeric / 10000000).toFixed(2)}Cr`;
        }

        if (numeric >= 100000) {
            return `\u20B9${(numeric / 100000).toFixed(2)}L`;
        }

        if (numeric >= 1000) {
            return `\u20B9${(numeric / 1000).toFixed(2)}K`;
        }

        return `\u20B9${numeric.toLocaleString("en-IN")}`;
    }

    if (metric?.prefix) {
      return `${metric.prefix}${numeric.toLocaleString("en-IN")}`;
    }

    return numeric.toLocaleString("en-IN");
  };
  if (type === "pie") {
    const pieMetric = chartSeries[0];

    const rawPieData = normalizedData
        .map((item, index) => ({
        name:
            item?.label ||
            item?.name ||
            `Item ${index + 1}`,
        value: Number(item?.[pieMetric?.key] ?? 0),
        }))
        .filter(
        (item) =>
            Number.isFinite(item.value) &&
            item.value > 0
        )
        .sort((a, b) => b.value - a.value);

    if (!rawPieData.length) {
        return (
        <div className="chart-wrapper">
            {title && (
            <h4 className="chart-title">{title}</h4>
            )}

            <div className="chart-empty-state">
            No positive numeric data available.
            </div>
        </div>
        );
    }

    /*
    * For pie charts, too many slices become unreadable.
    * Show top 10 and combine remaining records as Others.
    */
    const topItems = rawPieData.slice(0, 10);

    const remainingValue = rawPieData
        .slice(10)
        .reduce(
        (sum, item) => sum + item.value,
        0
        );

    if (remainingValue > 0) {
        topItems.push({
        name: "Others",
        value: remainingValue,
        });
    }

    const total = topItems.reduce(
        (sum, item) => sum + item.value,
        0
    );

    const pieColors = topItems.map(
        (_, index) =>
        `hsl(${(index * 43) % 360}, 70%, 55%)`
    );

    let accumulated = 0;

    const slices = topItems.map(
        (item, index) => {
        const startValue = accumulated;

        accumulated += item.value;

        const startAngle =
            (startValue / total) * 360 - 90;

        const endAngle =
            (accumulated / total) * 360 - 90;

        const percentage =
            (item.value / total) * 100;

        const polarToCartesian = (
            cx,
            cy,
            radius,
            angle
        ) => {
            const angleInRadians =
            (angle * Math.PI) / 180;

            return {
            x:
                cx +
                radius *
                Math.cos(angleInRadians),
            y:
                cy +
                radius *
                Math.sin(angleInRadians),
            };
        };

        const start = polarToCartesian(
            200,
            200,
            150,
            startAngle
        );

        const end = polarToCartesian(
            200,
            200,
            150,
            endAngle
        );

        const largeArcFlag =
            endAngle - startAngle > 180
            ? 1
            : 0;

        const pathData = `
            M 200 200
            L ${start.x} ${start.y}
            A 150 150 0 ${largeArcFlag} 1 ${end.x} ${end.y}
            Z
        `;

        return {
            ...item,
            index,
            percentage,
            color: pieColors[index],
            pathData,
        };
        }
    );

    return (
        <div className="chart-wrapper">
        {title && (
            <h4 className="chart-title">
            {title}
            </h4>
        )}

        <div className="pie-chart-header">
            <div>
            <span className="pie-chart-label">
                {pieMetric?.label || "Value"}
            </span>

            <strong>
                {formatMetricValue(
                total,
                pieMetric
                )}
            </strong>
            </div>

            <span className="pie-chart-count">
            {rawPieData.length} categories
            </span>
        </div>

        <div className="interactive-pie-layout">
            <div className="interactive-pie-visual">
            <svg
                viewBox="0 0 400 400"
                className="interactive-pie-svg"
            >
                <circle
                    cx="200"
                    cy="200"
                    r="78"
                    className="interactive-pie-hole"
                    pointerEvents="none"
                />

                { slices.map((slice) => (
                  <path
                    key={slice.name}
                    d={slice.pathData}
                    fill={slice.color}
                    className={`interactive-pie-slice ${
                      selectedPieSlice?.name === slice.name
                        ? "selected"
                        : ""
                    }`}
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      setSelectedPieSlice(slice);
                    }}
                  >
                    <title>
                      {slice.name} â€”{" "}
                      {formatMetricValue(slice.value, pieMetric)} â€”{" "}
                      {slice.percentage.toFixed(1)}%
                    </title>
                  </path>
                ))}
            </svg>

            <div className="interactive-pie-center">
                <span>
                {selectedPieSlice?.name ||
                    "Total"}
                </span>

                <strong>
                {selectedPieSlice
                    ? formatMetricValue(
                        selectedPieSlice.value,
                        pieMetric
                    )
                    : formatMetricValue(
                        total,
                        pieMetric
                    )}
                </strong>

                {selectedPieSlice && (
                <small>
                    {selectedPieSlice.percentage.toFixed(
                    1
                    )}
                    %
                </small>
                )}
            </div>
            </div>

            <div className="interactive-pie-legend">
            {slices.map((slice) => (
                <button
                type="button"
                key={slice.name}
                className={`interactive-pie-item ${
                    selectedPieSlice?.name ===
                    slice.name
                    ? "active"
                    : ""
                }`}
                onClick={() => setSelectedPieSlice(slice)}
                >
                <span
                    className="interactive-pie-color"
                    style={{
                    backgroundColor:
                        slice.color,
                    }}
                />

                <span className="interactive-pie-info">
                    <strong>
                    {slice.name}
                    </strong>

                    <small>
                    {formatMetricValue(
                        slice.value,
                        pieMetric
                    )}
                    </small>
                </span>

                <span className="interactive-pie-percent">
                    {slice.percentage.toFixed(1)}%
                </span>
                </button>
            ))}
            </div>
        </div>

        {selectedPieSlice && (
            <div className="pie-selection-detail">
            <span
                className="pie-selection-dot"
                style={{
                backgroundColor:
                    selectedPieSlice.color,
                }}
            />

            <div>
                <span>Selected</span>

                <strong>
                {selectedPieSlice.name}
                </strong>
            </div>

            <div>
                <span>
                {pieMetric?.label || "Value"}
                </span>

                <strong>
                {formatMetricValue(
                    selectedPieSlice.value,
                    pieMetric
                )}
                </strong>
            </div>

            <div>
                <span>Share</span>

                <strong>
                {selectedPieSlice.percentage.toFixed(
                    1
                )}
                %
                </strong>
            </div>
            </div>
        )}
        </div>
    );
  }
  if (type === "scatter") {
    const scatterMetric = chartSeries[0];

    return (
      <div className="chart-wrapper">
        {title && <h4 className="chart-title">{title}</h4>}

        <ResponsiveContainer width="100%" height={390}>
          <ScatterChart>
            <CartesianGrid />

            <XAxis
              dataKey="label"
              name="Period"
              tick={{ fontSize: 12 }}
            />

            <YAxis
              dataKey={scatterMetric.key}
              name={scatterMetric.label}
            />

            <Tooltip
              formatter={(value) =>
                formatMetricValue(value, scatterMetric)
              }
            />

            <Legend />

            <Scatter
              name={scatterMetric.label}
              data={normalizedData}
              fill="var(--accent)"
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (type === "line") {
    return (
      <div className="chart-wrapper">
        {title && <h4 className="chart-title">{title}</h4>}

        <ResponsiveContainer width="100%" height={390}>
          <LineChart data={normalizedData}>
            <CartesianGrid strokeDasharray="3 3" />

            <XAxis
              dataKey="label"
              tick={{ fontSize: 12 }}
            />

            <YAxis />

            <Tooltip
              formatter={(value, name) => {
                const metric = chartSeries.find(
                  (item) => item.key === name
                );

                return [
                  formatMetricValue(value, metric),
                  metric?.label ?? name,
                ];
              }}
            />

            <Legend />

            {chartSeries.map((metric, index) => (
              <Line
                key={metric.key}
                type="monotone"
                dataKey={metric.key}
                name={metric.label}
                stroke={`hsl(${index * 65 + 20}, 65%, 45%)`}
                strokeWidth={3}
                dot={{ r: 4 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <div className="chart-wrapper">
      {title && <h4 className="chart-title">{title}</h4>}

      <ResponsiveContainer width="100%" height={390}>
        <BarChart data={normalizedData}>
          <CartesianGrid strokeDasharray="3 3" />

          <XAxis
            dataKey="label"
            tick={{ fontSize: 12 }}
          />

          <YAxis />

          <Tooltip
            formatter={(value, name) => {
              const metric = chartSeries.find(
                (item) => item.key === name
              );

              return [
                formatMetricValue(value, metric),
                metric?.label ?? name,
              ];
            }}
          />

          <Legend />

          {chartSeries.map((metric, index) => (
            <Bar
              key={metric.key}
              dataKey={metric.key}
              name={metric.label}
              fill={`hsl(${index * 65 + 20}, 65%, 45%)`}
              radius={[6, 6, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function DataTable({ rows, columns }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>

        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>
                  {String(
                    row?.[column] ?? "-"
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({
  icon: Icon,
  title,
  text,
  buttonText,
  onClick,
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon size={30} />
      </div>

      <h3>{title}</h3>
      <p>{text}</p>

      {buttonText && onClick && (
        <button
          type="button"
          className="primary-button"
          onClick={onClick}
        >
          <Plus size={17} />
          {buttonText}
        </button>
      )}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="loading-state">
      <RefreshCw size={24} className="spin" />
      <span>Loading business data...</span>
    </div>
  );
}

function PieTest() {
  const data = [
    { name: "2025", value: 10219166.19 },
    { name: "2026", value: 9035227.01 },
  ];

  
}

export default App;





