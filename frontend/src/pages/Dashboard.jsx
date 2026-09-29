import {
  useCallback,
  useEffect,
  useState,
} from "react";

const API_BASE =
  "http://127.0.0.1:8000";

function Dashboard({
  setActivePage,
  theme,
  onChangeTheme,
}) {
  const [employeeCount, setEmployeeCount] =
    useState(0);

  const [uploadCount, setUploadCount] =
    useState(0);

  const [latestUpload, setLatestUpload] =
    useState(null);

  const [recentUploads, setRecentUploads] =
    useState([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  /*
   * Load dashboard data.
   */
  const loadDashboardData =
    useCallback(async () => {
      try {
        setLoading(true);
        setError("");

        const [
          employeeResponse,
          historyResponse,
        ] = await Promise.all([
          fetch(
            `${API_BASE}/uploaded-employees`
          ),

          fetch(
            `${API_BASE}/upload-history`
          ),
        ]);

        if (!employeeResponse.ok) {
          throw new Error(
            "Unable to load employee information."
          );
        }

        if (!historyResponse.ok) {
          throw new Error(
            "Unable to load upload history."
          );
        }

        const employeeData =
          await employeeResponse.json();

        const historyData =
          await historyResponse.json();

        const employees =
          employeeData?.employees || [];

        const uploads =
          historyData?.uploads ||
          historyData?.data?.uploads ||
          [];

        setEmployeeCount(
          employeeData?.count ??
            employees.length ??
            0
        );

        setUploadCount(
          uploads.length
        );

        setLatestUpload(
          uploads.length > 0
            ? uploads[0]
            : null
        );

        setRecentUploads(
          uploads.slice(0, 5)
        );
      } catch (err) {
        console.error(
          "Dashboard error:",
          err
        );

        setError(
          err.message ||
            "Unable to load dashboard data."
        );
      } finally {
        setLoading(false);
      }
    }, []);

  /*
   * Load dashboard when page opens.
   */
  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  /*
   * Format dates.
   */
  const formatDate = (value) => {
    if (!value) {
      return "—";
    }

    try {
      const date = new Date(value);

      if (
        Number.isNaN(
          date.getTime()
        )
      ) {
        return value;
      }

      return date.toLocaleString();
    } catch {
      return value;
    }
  };

  /*
   * Get filename from different
   * possible backend field names.
   */
  const getFileName = (upload) => {
    return (
      upload?.original_filename ||
      upload?.filename ||
      upload?.file_name ||
      upload?.name ||
      "Unknown file"
    );
  };

  /*
   * Get uploaded record count.
   */
  const getRecordCount = (upload) => {
    return (
      upload?.records_uploaded ??
      upload?.record_count ??
      upload?.records ??
      0
    );
  };

  /*
   * Get file type.
   */
  const getFileType = (upload) => {
    return (
      upload?.file_type ||
      upload?.extension ||
      "FILE"
    );
  };

  /*
   * Get upload status.
   */
  const getStatus = (upload) => {
    return (
      upload?.status ||
      "success"
    ).toLowerCase();
  };

  /*
   * Get upload date.
   */
  const getUploadedAt = (upload) => {
    return (
      upload?.uploaded_at ||
      upload?.created_at ||
      upload?.date
    );
  };

  /*
   * Refresh dashboard.
   */
  const handleRefresh = () => {
    loadDashboardData();
  };

  return (
    <div className="page">

      {/* =====================================================
          PAGE HEADER
          ===================================================== */}

      <div className="page-header dashboard-header">

        <div>
          <div className="page-eyebrow">
            HR MANAGEMENT
          </div>

          <h1>
            Dashboard
          </h1>

          <p className="page-description">
            Manage employee data, uploads
            and HR operations from one
            place.
          </p>
        </div>

        {/* =================================================
            RIGHT SIDE CONTROLS

            Refresh + Theme
            ================================================= */}

        <div className="dashboard-header-actions">

          <button
            type="button"
            className="secondary-button"
            onClick={
              handleRefresh
            }
            disabled={loading}
          >
            {loading
              ? "Refreshing..."
              : "Refresh"}
          </button>

          <button
            type="button"
            className="theme-circle-button"
            onClick={
              onChangeTheme
            }
            title={`Current theme: ${theme}`}
            aria-label="Change theme"
          >
            {theme === "white" && "☀"}
            {theme === "dark" && "◐"}
            {theme === "black" && "●"}
          </button>

        </div>

      </div>

      {/* =====================================================
          ERROR
          ===================================================== */}

      {error && (
        <div className="message-box error-message">
          {error}
        </div>
      )}

      {/* =====================================================
          STATISTICS
          ===================================================== */}

      <div className="dashboard-grid">

        <div className="stat-card">

          <div className="stat-label">
            Uploaded Employees
          </div>

          <div className="stat-value">
            {loading
              ? "—"
              : employeeCount}
          </div>

          <div className="stat-description">
            Employees currently
            available to the HR Agent.
          </div>

        </div>

        <div className="stat-card">

          <div className="stat-label">
            Uploaded Files
          </div>

          <div className="stat-value">
            {loading
              ? "—"
              : uploadCount}
          </div>

          <div className="stat-description">
            Employee data files
            uploaded to the system.
          </div>

        </div>

        <div className="stat-card">

          <div className="stat-label">
            HR Agent
          </div>

          <div className="stat-value status-online">
            Online
          </div>

          <div className="stat-description">
            Ready to answer
            employee-related questions.
          </div>

        </div>

      </div>

      {/* =====================================================
          WORKFLOW + LATEST UPLOAD
          ===================================================== */}

      <div className="dashboard-columns">

        <section className="dashboard-card">

          <div className="card-header">

            <div>
              <div className="section-label">
                WORKFLOW
              </div>

              <h2>
                Employee Data
              </h2>
            </div>

          </div>

          <div className="workflow">

            <div className="workflow-step">

              <div className="workflow-number">
                01
              </div>

              <div>
                <h3>
                  Upload employee files
                </h3>

                <p>
                  Upload CSV or Excel
                  employee data files.
                </p>
              </div>

            </div>

            <div className="workflow-step">

              <div className="workflow-number">
                02
              </div>

              <div>
                <h3>
                  Process employee data
                </h3>

                <p>
                  The system stores and
                  processes employee records.
                </p>
              </div>

            </div>

            <div className="workflow-step">

              <div className="workflow-number">
                03
              </div>

              <div>
                <h3>
                  Ask the HR Agent
                </h3>

                <p>
                  Ask questions about
                  salary, PF, experience
                  and employees.
                </p>
              </div>

            </div>

          </div>

        </section>

        {/* =================================================
            LATEST UPLOAD
            ================================================= */}

        <section className="dashboard-card">

          <div className="card-header">

            <div>
              <div className="section-label">
                LATEST UPLOAD
              </div>

              <h2>
                Recent File
              </h2>
            </div>

          </div>

          {latestUpload ? (
            <div className="latest-upload">

              <div className="latest-file-top">

                <div className="file-type-badge">
                  {getFileType(
                    latestUpload
                  ).toUpperCase()}
                </div>

                <div
                  className={
                    getStatus(
                      latestUpload
                    ) === "success"
                      ? "status-success"
                      : "status-error"
                  }
                >
                  {getStatus(
                    latestUpload
                  )}
                </div>

              </div>

              <div className="latest-file-name">
                {getFileName(
                  latestUpload
                )}
              </div>

              <div className="latest-file-details">

                <span>
                  {getRecordCount(
                    latestUpload
                  )}{" "}
                  records
                </span>

                <span>
                  {formatDate(
                    getUploadedAt(
                      latestUpload
                    )
                  )}
                </span>

              </div>

            </div>
          ) : (
            <div className="empty-state">
              No employee file has
              been uploaded yet.
            </div>
          )}

        </section>

      </div>

      {/* =====================================================
          RECENT UPLOADS
          ===================================================== */}

      <section className="dashboard-card recent-card">

        <div className="card-header">

          <div>
            <div className="section-label">
              UPLOAD HISTORY
            </div>

            <h2>
              Recent Uploads
            </h2>
          </div>

          <div className="history-count">
            {recentUploads.length}
            {" "}
            recent
          </div>

        </div>

        {recentUploads.length > 0 ? (

          <div className="recent-upload-list">

            {recentUploads.map(
              (upload, index) => (

                <div
                  className="recent-upload-item"
                  key={
                    upload?.id ||
                    upload?.upload_id ||
                    `${getFileName(
                      upload
                    )}-${index}`
                  }
                >

                  <div className="recent-upload-info">

                    <div className="file-type-badge">
                      {getFileType(
                        upload
                      ).toUpperCase()}
                    </div>

                    <div>

                      <div className="history-file-name">
                        {getFileName(
                          upload
                        )}
                      </div>

                      <div className="upload-date">
                        {formatDate(
                          getUploadedAt(
                            upload
                          )
                        )}
                      </div>

                    </div>

                  </div>

                  <div className="recent-upload-meta">

                    <span>
                      {getRecordCount(
                        upload
                      )}{" "}
                      records
                    </span>

                    <span
                      className={
                        getStatus(
                          upload
                        ) === "success"
                          ? "status-success"
                          : "status-error"
                      }
                    >
                      {getStatus(
                        upload
                      )}
                    </span>

                  </div>

                </div>

              )
            )}

          </div>

        ) : (

          <div className="empty-state">
            No upload history available.
          </div>

        )}

      </section>

      {/* =====================================================
          QUICK HR AGENT
          ===================================================== */}

      <section className="dashboard-card quick-agent">

        <div>

          <div className="section-label">
            HR AGENT
          </div>

          <h2>
            Ask about your employees
          </h2>

          <p>
            Search employee information
            using natural language. You can
            ask about salary, PF, experience,
            employee ID and more.
          </p>

        </div>

        <button
          type="button"
          className="dark-button"
          onClick={() =>
            setActivePage("agent")
          }
        >
          Open HR Agent
        </button>

      </section>

    </div>
  );
}

export default Dashboard;