import { useMemo, useState } from "react";

import {
  Database,
  Columns3,
  BarChart3,
  Download,
  FileText,
  Plus,
  Sparkles,
  Upload,
  Search,
  RefreshCw,
  Trash2,
  FileSpreadsheet,
  FileJson,
  File,
  X,
} from "lucide-react";

import { EmptyState, PageHeading } from "../components/common.jsx";

import {
  API,
  formatNumber,
  formatReportValue,
  isNumericColumn,
  numericValue,
} from "../lib/helpers.js";

import "./UploadData.css";
/* -------------------------------------------------------------- Reports */
export function ReportsPage({ datasets, selectedDataset, datasetRows, onOpenChat }) {
  const rows = Array.isArray(datasetRows) ? datasetRows : [];
  const recordCount = Number(selectedDataset?.rows ?? rows.length ?? 0) || 0;
  const columnNames = selectedDataset?.columnNames?.length ? selectedDataset.columnNames : rows.length ? Object.keys(rows[0]) : [];
  const columnCount = Number(selectedDataset?.columns ?? columnNames.length) || 0;
  const numericColumns = columnNames.filter((c) => isNumericColumn(rows, c));
  const total = (c) => rows.reduce((t, r) => t + numericValue(r?.[c]), 0);
  const name = selectedDataset?.name || "No dataset selected";
  const sourceUrl = selectedDataset?.stored_filename ? `${API}/download/${encodeURIComponent(selectedDataset.stored_filename)}` : null;
  const cards = [
    { icon: Database, label: "Records", value: recordCount, note: "Available in current dataset" },
    { icon: Columns3, label: "Fields", value: columnCount, note: "Detected dataset columns" },
    { icon: BarChart3, label: "Numeric fields", value: numericColumns.length, note: "Available when preview data is loaded" },
    { icon: FileText, label: "Datasets", value: datasets.length, note: "Stored in database" },
  ];
  return (
    <div className="page">
      <PageHeading kicker="REPORTING" title="Business Reports" description="Review, analyse and export reports from your uploaded business data." />
      <div className="report-hero">
        <div>
          <span className="section-kicker">ACTIVE DATASET</span>
          <h2>{name}</h2>
          <p>{formatNumber(recordCount)} records{columnCount ? ` \u2022 ${formatNumber(columnCount)} columns` : ""}</p>
        </div>
        <div className="report-status"><span className="status-dot" />{recordCount > 0 ? "Data ready" : "Metadata available"}</div>
      </div>
      <div className="report-summary-grid">
        {cards.map(({ icon: Icon, label, value, note }) => (
          <div className="report-summary-card" key={label}>
            <div className="report-summary-icon"><Icon size={19} /></div>
            <span>{label}</span>
            <strong>{formatNumber(value)}</strong>
            <small>{note}</small>
          </div>
        ))}
      </div>
      <div className="report-action-panel">
        <div>
          <span className="section-kicker">REPORT EXPORT</span>
          <h3>Generate business report</h3>
          <p>Export the current dataset using the existing backend reporting system.</p>
        </div>
        <div className="report-action-buttons">
          {sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer" className="secondary-button"><Download size={16} />Download Source</a>}
          {selectedDataset && <button type="button" className="primary-button" onClick={onOpenChat}><Sparkles size={16} />Generate with AI</button>}
        </div>
      </div>
      {numericColumns.length > 0 && rows.length > 0 && (
        <div className="report-section">
          <div className="report-section-heading">
            <div><span className="section-kicker">NUMERIC OVERVIEW</span><h3>Key field totals</h3></div>
            <span className="result-count">{numericColumns.length} fields</span>
          </div>
          <div className="report-metric-grid">
            {numericColumns.slice(0, 8).map((c) => (
              <div className="report-metric-card" key={c}>
                <span>{c}</span>
                <strong>{formatReportValue(total(c), c)}</strong>
                <small>Total across current records</small>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="report-section">
        <div className="report-section-heading">
          <div><span className="section-kicker">REPORT PREVIEW</span><h3>Dataset records</h3></div>
          <span className="result-count">{rows.length > 0 ? `Showing ${Math.min(rows.length, 100)}` : `${formatNumber(recordCount)} records`}</span>
        </div>
        <div className="report-preview-card">
          {rows.length > 0 ? (
            <div className="report-preview-scroll">
              <table className="report-preview-table">
                <thead><tr>{columnNames.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>
                  {rows.slice(0, 100).map((r, i) => (
                    <tr key={i}>{columnNames.map((c) => <td key={c}>{formatReportValue(r?.[c], c)}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="report-empty">
              <Database size={32} />
              <h4>Dataset metadata is ready</h4>
              <p>This dataset contains <strong>{formatNumber(recordCount)}</strong> records across <strong>{formatNumber(columnCount)}</strong> fields.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- Upload */


// Replace only the existing UploadPage function with this.
export function UploadPage({
  datasets = [],
  onUpload,
  onRefresh,
  onDelete,
}) {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const items = Array.isArray(datasets) ? datasets : [];

  const getName = (item) =>
    item?.original_filename ||
    item?.name ||
    item?.filename ||
    item?.stored_filename ||
    "Untitled dataset";

  const getType = (item) => {
    const filename = String(
      item?.original_filename ||
      item?.name ||
      item?.filename ||
      item?.stored_filename ||
      item?.file_name ||
      ""
    ).toLowerCase();

    const type = String(
      item?.file_type ||
      item?.fileType ||
      item?.type ||
      item?.data_type ||
      ""
    ).toLowerCase();

    if (
      /\.(xlsx|xls)(?:$|[?#])/.test(filename) ||
      type.includes("excel") ||
      type.includes("spreadsheet") ||
      type.includes("xlsx") ||
      type === "xls"
    ) return "Excel";

    if (/\.csv(?:$|[?#])/.test(filename) || type.includes("csv")) {
      return "CSV";
    }

    if (/\.json(?:$|[?#])/.test(filename) || type.includes("json")) {
      return "JSON";
    }

    if (/\.pdf(?:$|[?#])/.test(filename) || type.includes("pdf")) {
      return "PDF";
    }

    return "Other";
  };

  const getDatasetId = (item) =>
    item?.id ?? item?.dataset_id ?? item?._id ?? getName(item);

  const getDate = (item) => {
    const raw = item?.uploaded_at || item?.created_at ||
      item?.upload_date || item?.createdAt;

    if (!raw) return "Date unavailable";

    const date = new Date(raw);
    return Number.isNaN(date.getTime())
      ? String(raw)
      : date.toLocaleString("en-IN", {
          day: "2-digit",
          month: "short",
          year: "numeric",
        });
  };

  const filteredItems = useMemo(() => {
    const term = search.trim().toLowerCase();

    return items.filter((item) => {
      const matchesSearch =
        !term ||
        getName(item).toLowerCase().includes(term) ||
        getType(item).toLowerCase().includes(term);

      const matchesType =
        typeFilter === "all" ||
        getType(item).toLowerCase() === typeFilter.toLowerCase();

      return matchesSearch && matchesType;
    });
  }, [items, search, typeFilter]);

  const countByType = (type) =>
    items.filter((item) => getType(item) === type).length;

  const iconForType = (type) => {
    if (type === "Excel" || type === "CSV") {
      return <FileSpreadsheet size={20} />;
    }
    if (type === "JSON") return <FileJson size={20} />;
    if (type === "PDF") return <FileText size={20} />;
    return <File size={20} />;
  };

  const handleDelete = async (item) => {
    if (!onDelete) return;

    const id = getDatasetId(item);
    const confirmed = window.confirm(
      `Delete "${getName(item)}"? This action cannot be undone.`
    );

    if (!confirmed) return;

    try {
      setDeletingId(id);
      await onDelete(item.id ?? item.dataset_id ?? item._id);
      setSelectedDataset(null);
    } catch (error) {
      console.error("Dataset delete failed:", error);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="page upload-data-page">
      <PageHeading
        kicker="DATA MANAGEMENT"
        title="Upload Data"
        description="Import business files and manage your uploaded datasets."
        actions={
          <button
            type="button"
            className="primary-button"
            onClick={onUpload}
          >
            <Plus size={17} />
            Upload file
          </button>
        }
      />

      <section className="upload-hero">
        <div className="upload-hero-content">
          <div className="upload-hero-icon">
            <Upload size={23} />
          </div>

          <div>
            <h3>Import your business data</h3>
            <p>
              Upload CSV, Excel, JSON or PDF files using the existing upload
              workflow. Your imported data can be used by your dashboard and AI
              agent.
            </p>
            <div className="upload-format-list">
              <span>CSV</span>
              <span>XLSX / XLS</span>
              <span>JSON</span>
              <span>PDF</span>
            </div>
          </div>
        </div>

        <button
          type="button"
          className="primary-button upload-hero-button"
          onClick={onUpload}
        >
          <Upload size={17} />
          Choose file
        </button>
      </section>

      <section className="upload-stat-grid">
        <div className="upload-stat-card">
          <span className="upload-stat-icon">
            <Database size={18} />
          </span>
          <div>
            <small>Total datasets</small>
            <strong>{formatNumber(items.length)}</strong>
          </div>
        </div>

        <div className="upload-stat-card">
          <span className="upload-stat-icon">
            <FileSpreadsheet size={18} />
          </span>
          <div>
            <small>Excel files</small>
            <strong>{formatNumber(countByType("Excel"))}</strong>
          </div>
        </div>

        <div className="upload-stat-card">
          <span className="upload-stat-icon">
            <FileText size={18} />
          </span>
          <div>
            <small>CSV files</small>
            <strong>{formatNumber(countByType("CSV"))}</strong>
          </div>
        </div>
      </section>

      <section className="upload-files-panel">
        <div className="upload-files-heading">
          <div>
            <h3>Uploaded files</h3>
            <p>Search and manage datasets already available in your app.</p>
          </div>

          <button
            type="button"
            className="upload-refresh-button"
            onClick={onRefresh}
            disabled={!onRefresh}
            title="Refresh dataset list"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>

        <div className="upload-toolbar">
          <label className="upload-search">
            <Search size={17} />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search file name or type..."
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                aria-label="Clear search"
              >
                <X size={15} />
              </button>
            )}
          </label>

          <select
            className="upload-type-filter"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
            aria-label="Filter files by type"
          >
            <option value="all">All file types</option>
            <option value="Excel">Excel</option>
            <option value="CSV">CSV</option>
            <option value="JSON">JSON</option>
            <option value="PDF">PDF</option>
            <option value="Other">Other</option>
          </select>
        </div>

        <div className="upload-table-wrap">
          <table className="upload-files-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Type</th>
                <th>Records</th>
                <th>Columns</th>
                <th>Uploaded</th>
                <th className="upload-action-heading">Actions</th>
              </tr>
            </thead>

            <tbody>
              {filteredItems.map((item, index) => {
                const id = getDatasetId(item);
                const type = getType(item);
                const rows = item?.rows ?? item?.row_count ?? item?.record_count;
                const columns =
                  item?.columns ?? item?.column_count ??
                  item?.columnNames?.length ?? item?.column_names?.length;

                return (
                  <tr key={`${id}-${index}`}>
                    <td>
                      <div className="upload-file-cell">
                        <span className={`upload-file-icon upload-file-${type.toLowerCase()}`}>
                          {iconForType(type)}
                        </span>
                        <span className="upload-file-name" title={getName(item)}>
                          {getName(item)}
                        </span>
                      </div>
                    </td>

                    <td>
                      <span className="upload-type-badge">{type}</span>
                    </td>

                    <td>{rows == null ? "—" : formatNumber(rows)}</td>
                    <td>{columns == null ? "—" : formatNumber(columns)}</td>
                    <td>{getDate(item)}</td>

                    <td>
                      <div className="upload-row-actions">
                        <button
                          type="button"
                          className="upload-view-button"
                          onClick={() => setSelectedDataset(item)}
                        >
                          View
                        </button>

                        {onDelete && (
                          <button
                            type="button"
                            className="upload-delete-button"
                            onClick={() => handleDelete(item)}
                            disabled={deletingId === id}
                            title="Delete dataset"
                            aria-label={`Delete ${getName(item)}`}
                          >
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {filteredItems.length === 0 && (
            <div className="upload-empty-state">
              <span><Database size={24} /></span>
              <strong>
                {items.length === 0 ? "No datasets uploaded yet" : "No matching files"}
              </strong>
              <p>
                {items.length === 0
                  ? "Choose a file above to import your first dataset."
                  : "Try a different search term or file type."}
              </p>
              {items.length === 0 && (
                <button
                  type="button"
                  className="primary-button"
                  onClick={onUpload}
                >
                  <Upload size={16} />
                  Upload your first file
                </button>
              )}
            </div>
          )}
        </div>

        <div className="upload-table-footer">
          Showing {formatNumber(filteredItems.length)} of{" "}
          {formatNumber(items.length)} datasets
        </div>
      </section>

      {selectedDataset && (
        <div
          className="upload-modal-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) setSelectedDataset(null);
          }}
        >
          <section
            className="upload-detail-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="upload-detail-title"
          >
            <div className="upload-detail-heading">
              <div>
                <small>DATASET DETAILS</small>
                <h3 id="upload-detail-title">{getName(selectedDataset)}</h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDataset(null)}
                aria-label="Close details"
              >
                <X size={19} />
              </button>
            </div>

            <div className="upload-detail-grid">
              <div>
                <span>File type</span>
                <strong>{getType(selectedDataset)}</strong>
              </div>
              <div>
                <span>Records</span>
                <strong>
                  {formatNumber(
                    selectedDataset?.rows ??
                    selectedDataset?.row_count ??
                    selectedDataset?.record_count ??
                    0
                  )}
                </strong>
              </div>
              <div>
                <span>Columns</span>
                <strong>
                  {formatNumber(
                    selectedDataset?.columns ??
                    selectedDataset?.column_count ??
                    selectedDataset?.columnNames?.length ??
                    selectedDataset?.column_names?.length ??
                    0
                  )}
                </strong>
              </div>
              <div>
                <span>Uploaded</span>
                <strong>{getDate(selectedDataset)}</strong>
              </div>
            </div>

            <p className="upload-detail-note">
              This view shows dataset metadata. To inspect the actual records,
              open the dataset from the Business Data page.
            </p>

            <div className="upload-detail-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setSelectedDataset(null)}
              >
                Close
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- Settings */
export function SettingsPage({ theme, setTheme, userName, setUserName }) {
  return (
    <div className="page">
      <PageHeading kicker="PREFERENCES" title="Settings" description="Appearance and profile." />
      <div className="vx-card vx-settings">
        <label className="vx-field">
          <span>Your name (shown in the dashboard greeting)</span>
          <input value={userName} onChange={(e) => setUserName(e.target.value)} maxLength={30} />
        </label>
        <div>
          <strong>Theme</strong>
          <p className="vx-muted">Currently using the {theme} theme.</p>
          <button type="button" className="primary-button" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
            {theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
          </button>
        </div>
      </div>
    </div>
  );
}
