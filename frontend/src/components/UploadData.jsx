import { useState } from "react";

const API_URL = "http://127.0.0.1:8000";

function UploadData() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");

  const handleFileChange = (event) => {
    const selectedFiles = Array.from(
      event.target.files || []
    );

    setError("");
    setResults([]);

    const validFiles = selectedFiles.filter((file) => {
      const name = file.name.toLowerCase();

      return (
        name.endsWith(".csv") ||
        name.endsWith(".xlsx") ||
        name.endsWith(".xls")
      );
    });

    if (validFiles.length !== selectedFiles.length) {
      setError(
        "Only CSV, XLSX and XLS files are supported."
      );
    }

    setFiles(validFiles);

    event.target.value = "";
  };

  const removeFile = (index) => {
    setFiles((currentFiles) =>
      currentFiles.filter(
        (_, currentIndex) => currentIndex !== index
      )
    );
  };

  const uploadFiles = async () => {
    if (files.length === 0) {
      setError("Please select at least one file.");
      return;
    }

    setUploading(true);
    setError("");
    setResults([]);

    const uploadResults = [];

    try {
      for (const file of files) {
        const formData = new FormData();

        formData.append("file", file);

        const response = await fetch(
          `${API_URL}/upload-data`,
          {
            method: "POST",
            body: formData,
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
              `Upload failed for ${file.name}`
          );
        }

        uploadResults.push({
          filename:
            data.filename || file.name,

          success: true,

          datasetId:
            data.dataset_id ?? null,

          records:
            data.row_count ??
            data.records_uploaded ??
            data.records_inserted ??
            0,

          columns:
            data.column_count ?? 0,

          dataType:
            data.data_type || "structured",

          fileType:
            data.file_type ||
            file.name
              .split(".")
              .pop()
              ?.toUpperCase(),

          status:
            data.status || "SUCCESS",
        });
      }

      setResults(uploadResults);
      setFiles([]);
    } catch (err) {
      setError(
        err.message ||
          "Unable to upload files."
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <p className="page-eyebrow">
            DATA MANAGEMENT
          </p>

          <h1>Upload Data</h1>

          <p className="page-description">
            Upload one or multiple CSV or Excel files.
            The AI Data Agent automatically detects the
            structure and stores each dataset for
            future questions and analysis.
          </p>
        </div>
      </div>

      <section className="upload-card">
        <div className="upload-card-header">
          <div>
            <p className="section-label">
              DATASET UPLOAD
            </p>

            <h2>Select files</h2>

            <p>
              Supported formats: CSV, XLSX and XLS
            </p>
          </div>

          <div className="upload-count">
            {files.length}{" "}
            {files.length === 1
              ? "file"
              : "files"} selected
          </div>
        </div>

        <label
          className="file-drop-zone"
          htmlFor="data-files"
        >
          <div className="upload-symbol">
            +
          </div>

          <strong>
            Select data files
          </strong>

          <span>
            Multiple CSV or Excel files are supported
          </span>

          <input
            id="data-files"
            type="file"
            accept=".csv,.xlsx,.xls"
            multiple
            onChange={handleFileChange}
          />
        </label>

        {files.length > 0 && (
          <div className="selected-files">
            <div className="selected-files-header">
              <h3>Selected files</h3>

              <span>
                {files.length} selected
              </span>
            </div>

            {files.map((file, index) => (
              <div
                className="selected-file"
                key={`${file.name}-${index}`}
              >
                <div className="selected-file-info">
                  <div className="file-icon">
                    {file.name
                      .split(".")
                      .pop()
                      ?.toUpperCase()}
                  </div>

                  <div>
                    <strong>
                      {file.name}
                    </strong>

                    <span>
                      {formatFileSize(file.size)}
                    </span>
                  </div>
                </div>

                <button
                  type="button"
                  className="remove-file-button"
                  onClick={() => removeFile(index)}
                  disabled={uploading}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="upload-error">
            <strong>Upload failed</strong>

            <span>
              {error}
            </span>
          </div>
        )}

        {results.length > 0 && (
          <div className="upload-results">
            <div className="upload-success-header">
              <div>
                <strong>
                  Upload completed
                </strong>

                <span>
                  {results.length}{" "}
                  {results.length === 1
                    ? "dataset"
                    : "datasets"}{" "}
                  processed
                </span>
              </div>

              <span className="success-badge">
                Success
              </span>
            </div>

            {results.map((result, index) => (
              <div
                className="upload-result"
                key={`${result.filename}-${index}`}
              >
                <div>
                  <strong>
                    {result.filename}
                  </strong>

                  <span>
                    {result.records} rows
                    {" • "}
                    {result.columns} columns
                    {" • "}
                    {result.fileType}
                  </span>

                  {result.datasetId && (
                    <span>
                      Dataset ID: {result.datasetId}
                    </span>
                  )}
                </div>

                <span className="result-record-count">
                  {result.records}
                </span>
              </div>
            ))}
          </div>
        )}

        <button
          type="button"
          className="primary-button upload-button"
          onClick={uploadFiles}
          disabled={
            uploading ||
            files.length === 0
          }
        >
          {uploading
            ? "Processing files..."
            : `Upload ${
                files.length || ""
              } ${
                files.length === 1
                  ? "File"
                  : "Files"
              }`}
        </button>
      </section>

      <section className="upload-process">
        <div className="section-heading">
          <p className="page-eyebrow">
            WORKFLOW
          </p>

          <h2>
            From file to AI data intelligence
          </h2>
        </div>

        <div className="process-grid">
          <ProcessCard
            number="01"
            title="Select files"
            description="Choose one or multiple CSV or Excel data files."
          />

          <ProcessCard
            number="02"
            title="Detect structure"
            description="The backend automatically reads rows, columns and data types."
          />

          <ProcessCard
            number="03"
            title="Store dataset"
            description="Each uploaded file receives a unique stored filename and dataset ID."
          />

          <ProcessCard
            number="04"
            title="Ask questions"
            description="The AI Data Agent can query the uploaded dataset using natural language."
          />
        </div>
      </section>
    </div>
  );
}

function ProcessCard({
  number,
  title,
  description,
}) {
  return (
    <div className="process-card">
      <span>{number}</span>

      <h3>{title}</h3>

      <p>
        {description}
      </p>
    </div>
  );
}

function formatFileSize(bytes) {
  const size = Number(bytes || 0);

  if (size < 1024) {
    return `${size} B`;
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }

  return `${(
    size /
    (1024 * 1024)
  ).toFixed(1)} MB`;
}

export default UploadData;