import { useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8000";

function History() {
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadDatasets = async () => {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(
        `${API_URL}/datasets`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Unable to load dataset history."
        );
      }

      if (
        data.success &&
        Array.isArray(data.datasets)
      ) {
        setDatasets(data.datasets);
      } else {
        setDatasets([]);
      }
    } catch (err) {
      setError(
        err.message ||
          "Unable to load dataset history."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDatasets();
  }, []);

  const deleteDataset = async (dataset) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${dataset.original_filename}"?\n\nThis will delete the dataset record and the stored uploaded file.`
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeleting(dataset.id);
      setError("");
      setSuccess("");

      const response = await fetch(
        `${API_URL}/datasets/${dataset.id}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Unable to delete dataset."
        );
      }

      if (!data.success) {
        throw new Error(
          data.message ||
            "Unable to delete dataset."
        );
      }

      setSuccess(
        `"${dataset.original_filename}" was deleted successfully.`
      );

      await loadDatasets();
    } catch (err) {
      setError(
        err.message ||
          "Unable to delete dataset."
      );
    } finally {
      setDeleting(null);
    }
  };

  const totalRows = datasets.reduce(
    (total, item) =>
      total +
      Number(item.row_count || 0),
    0
  );

  const successfulDatasets = datasets.filter(
    (item) => item.status === "SUCCESS"
  ).length;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <p className="page-eyebrow">
            DATA MANAGEMENT
          </p>

          <h1>Dataset History</h1>

          <p className="page-description">
            View all structured files uploaded to the
            Dynamic Data Agent.
          </p>
        </div>

        <button
          className="secondary-button"
          onClick={loadDatasets}
          disabled={loading}
        >
          {loading
            ? "Loading..."
            : "Refresh"}
        </button>
      </div>

      {error && (
        <div className="message-box error-message">
          <strong>
            Request information
          </strong>

          <p>{error}</p>
        </div>
      )}

      {success && (
        <div className="message-box success-message">
          <strong>
            Dataset deleted
          </strong>

          <p>{success}</p>
        </div>
      )}

      <div className="dashboard-grid">
        <div className="stat-card">
          <span className="stat-label">
            TOTAL DATASETS
          </span>

          <strong className="stat-value">
            {datasets.length}
          </strong>

          <span className="stat-description">
            Uploaded files
          </span>
        </div>

        <div className="stat-card">
          <span className="stat-label">
            TOTAL ROWS
          </span>

          <strong className="stat-value">
            {totalRows}
          </strong>

          <span className="stat-description">
            Records across datasets
          </span>
        </div>

        <div className="stat-card">
          <span className="stat-label">
            SUCCESSFUL
          </span>

          <strong className="stat-value">
            {successfulDatasets}
          </strong>

          <span className="stat-description">
            Successfully processed
          </span>
        </div>
      </div>

      <section className="history-card">
        <div className="history-card-header">
          <div>
            <p className="page-eyebrow">
              DATASETS
            </p>

            <h2>
              Uploaded Datasets
            </h2>
          </div>

          <span className="history-count">
            {datasets.length}{" "}
            {datasets.length === 1
              ? "dataset"
              : "datasets"}
          </span>
        </div>

        {loading && (
          <div className="history-empty">
            <h3>
              Loading dataset history...
            </h3>

            <p>
              Please wait.
            </p>
          </div>
        )}

        {!loading &&
          datasets.length === 0 && (
            <div className="history-empty">
              <h3>
                No datasets uploaded
              </h3>

              <p>
                Upload a CSV or Excel file
                to see it here.
              </p>
            </div>
          )}

        {!loading &&
          datasets.length > 0 && (
            <div className="history-table-wrapper">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>
                      Dataset
                    </th>

                    <th>
                      Type
                    </th>

                    <th>
                      Rows
                    </th>

                    <th>
                      Columns
                    </th>

                    <th>
                      Size
                    </th>

                    <th>
                      Status
                    </th>

                    <th>
                      Uploaded
                    </th>

                    <th>
                      Action
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {datasets.map(
                    (item) => (
                      <tr
                        key={item.id}
                      >
                        <td>
                          <div className="history-file-name">
                            <strong>
                              {
                                item.original_filename
                              }
                            </strong>

                            <small>
                              Dataset ID:{" "}
                              {item.id}
                            </small>

                            {item.stored_filename && (
                              <small>
                                Stored as:{" "}
                                {
                                  item.stored_filename
                                }
                              </small>
                            )}
                          </div>
                        </td>

                        <td>
                          <span className="file-type-badge">
                            {(
                              item.file_type ||
                              "FILE"
                            ).toUpperCase()}
                          </span>
                        </td>

                        <td>
                          <strong>
                            {
                              item.row_count ?? 0
                            }
                          </strong>
                        </td>

                        <td>
                          <strong>
                            {
                              item.column_count ?? 0
                            }
                          </strong>
                        </td>

                        <td>
                          {formatFileSize(
                            item.file_size
                          )}
                        </td>

                        <td>
                          <span
                            className={
                              item.status ===
                              "SUCCESS"
                                ? "status-success"
                                : "status-error"
                            }
                          >
                            {item.status ||
                              "UNKNOWN"}
                          </span>
                        </td>

                        <td>
                          <span className="upload-date">
                            {formatDate(
                              item.uploaded_at
                            )}
                          </span>
                        </td>

                        <td>
                          <button
                            className="delete-button"
                            onClick={() =>
                              deleteDataset(
                                item
                              )
                            }
                            disabled={
                              deleting ===
                              item.id
                            }
                          >
                            {deleting ===
                            item.id
                              ? "Deleting..."
                              : "Delete"}
                          </button>
                        </td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>
          )}
      </section>
    </div>
  );
}

function formatFileSize(bytes) {
  const size = Number(
    bytes || 0
  );

  if (size === 0) {
    return "0 KB";
  }

  if (size < 1024) {
    return `${size} B`;
  }

  if (
    size <
    1024 * 1024
  ) {
    return `${(
      size / 1024
    ).toFixed(1)} KB`;
  }

  return `${(
    size /
    (1024 * 1024)
  ).toFixed(1)} MB`;
}

function formatDate(
  dateString
) {
  if (!dateString) {
    return "Unknown";
  }

  const date = new Date(
    String(
      dateString
    ).replace(
      " ",
      "T"
    )
  );

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return dateString;
  }

  return date.toLocaleString(
    "en-IN",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }
  );
}

export default History;
