import { useState } from "react";
import { SearchX, PencilLine, Upload, ArrowLeft, RefreshCw, CloudOff } from "lucide-react";

const PREVIEW_COUNT = 10;

export default function NoDataCard({
  question,
  columns = [],
  variant = "nodata", // "nodata" | "engine"
  onEdit,
  onUpload,
  onRetry,
  onBack,
}) {
  const [expanded, setExpanded] = useState(false);

  const names = columns
    .map((c) => (typeof c === "string" ? c : c?.name || c?.key || c?.label))
    .filter(Boolean);
  const shown = expanded ? names : names.slice(0, PREVIEW_COUNT);
  const extra = names.length - PREVIEW_COUNT;
  const isEngine = variant === "engine";

  return (
    <div className="vx-nd-wrap">
      {onBack && (
        <button type="button" className="vx-link" onClick={onBack}>
          <ArrowLeft size={14} /> Back to dashboard
        </button>
      )}

      <div className="vx-nd-card">
        <div className={`vx-nd-icon ${isEngine ? "warn" : ""}`}>
          {isEngine ? <CloudOff size={26} /> : <SearchX size={26} />}
        </div>

        <h2 className="vx-nd-title">
          {isEngine ? "AI engine is busy right now" : "Information not available"}
        </h2>
        <p className="vx-nd-sub">
          {isEngine ? (
            "Please try again in a moment."
          ) : (
            <>No matching data was found in the uploaded file for <b>"{question}"</b>.</>
          )}
        </p>

        {!isEngine && names.length > 0 && (
          <div className="vx-nd-cols">
            <span className="vx-nd-label">
              Available columns in your file ({names.length})
            </span>
            <div className="vx-nd-chips">
              {shown.map((c) => <span key={c} className="vx-nd-chip">{c}</span>)}
              {extra > 0 && (
                <button
                  type="button"
                  className="vx-nd-chip vx-nd-more"
                  onClick={() => setExpanded((v) => !v)}
                  aria-expanded={expanded}
                >
                  {expanded ? "Show less" : `+${extra} more`}
                </button>
              )}
            </div>
          </div>
        )}

        <div className="vx-nd-actions">
          {isEngine ? (
            <button type="button" className="vx-nd-btn primary" onClick={onRetry}>
              <RefreshCw size={16} /> Try again
            </button>
          ) : (
            <>
              <button type="button" className="vx-nd-btn primary" onClick={onEdit}>
                <PencilLine size={16} /> Edit question
              </button>
              <button type="button" className="vx-nd-btn" onClick={onUpload}>
                <Upload size={16} /> Upload another file
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}