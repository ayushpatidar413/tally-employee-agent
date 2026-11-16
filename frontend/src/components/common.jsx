import { Plus, RefreshCw, Maximize2 } from "lucide-react";

export function PageHeading({ kicker, title, description, actions, action }) {
  const buttons = actions || action;
  return (
    <div className="page-heading">
      <div>
        {kicker && <div className="page-heading-kicker">{kicker}</div>}
        <h1 className="page-heading-title">{title}</h1>
        {description && <p className="page-heading-description">{description}</p>}
      </div>
      {buttons && <div className="page-heading-actions">{buttons}</div>}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, text, buttonText, onClick }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon size={30} /></div>
      <h3>{title}</h3>
      <p>{text}</p>
      {buttonText && onClick && (
        <button type="button" className="primary-button" onClick={onClick}>
          <Plus size={17} />
          {buttonText}
        </button>
      )}
    </div>
  );
}

export function LoadingState({ text = "Loading business data..." }) {
  return (
    <div className="loading-state">
      <RefreshCw size={24} className="spin" />
      <span>{text}</span>
    </div>
  );
}

export function DataTable({ rows, columns }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => <td key={c}>{String(row?.[c] ?? "-")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function toggleFullscreen(event) {
  const panel = event.currentTarget.closest(".chart-card, .vx-card");
  if (!panel) return;
  if (document.fullscreenElement === panel) document.exitFullscreen?.();
  else if (panel.requestFullscreen) panel.requestFullscreen().catch(() => panel.classList.toggle("chart-expanded-fallback"));
  else panel.classList.toggle("chart-expanded-fallback");
}

export function FullscreenButton() {
  return (
    <button type="button" className="vx-icon-btn" onClick={toggleFullscreen} title="Full screen" aria-label="Full screen">
      <Maximize2 size={16} />
    </button>
  );
}
