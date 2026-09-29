
import { useEffect, useRef, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

function HRAgent() {
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);

  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);

  const [messages, setMessages] = useState([]);

  const [question, setQuestion] = useState("");

  const [loading, setLoading] = useState(false);
  const [loadingDatasets, setLoadingDatasets] = useState(true);
  const [loadingConversation, setLoadingConversation] = useState(false);

  const [error, setError] = useState("");

  const textareaRef = useRef(null);
  const messagesEndRef = useRef(null);

  // ============================================================
  // LOAD DATASETS
  // ============================================================

  const loadDatasets = async () => {
    try {
      setLoadingDatasets(true);
      setError("");

      const response = await fetch(`${API_BASE}/datasets`);

      if (!response.ok) {
        throw new Error("Unable to load uploaded datasets.");
      }

      const data = await response.json();

      console.log("DATASETS API RESPONSE:", data);

      /*
        Backend may return:

        1. [...]
        2. { datasets: [...] }
        3. { datasets: { datasets: [...] } }
        4. { data: [...] }
        5. { data: { datasets: [...] } }
      */

      let uploadedDatasets = [];

      if (Array.isArray(data)) {
        uploadedDatasets = data;
      } else if (Array.isArray(data.datasets)) {
        uploadedDatasets = data.datasets;
      } else if (
        data.datasets &&
        Array.isArray(data.datasets.datasets)
      ) {
        uploadedDatasets = data.datasets.datasets;
      } else if (data.data && Array.isArray(data.data)) {
        uploadedDatasets = data.data;
      } else if (
        data.data &&
        Array.isArray(data.data.datasets)
      ) {
        uploadedDatasets = data.data.datasets;
      }

      setDatasets(uploadedDatasets);

      // Automatically select newest dataset
      if (
        uploadedDatasets.length > 0 &&
        selectedDatasetId === null
      ) {
        setSelectedDatasetId(uploadedDatasets[0].id);
      }
    } catch (err) {
      console.error("Dataset loading error:", err);

      setDatasets([]);

      setError("Unable to load uploaded datasets.");
    } finally {
      setLoadingDatasets(false);
    }
  };

  // ============================================================
  // LOAD CONVERSATIONS
  // ============================================================

  const loadConversations = async () => {
    try {
      const response = await fetch(`${API_BASE}/conversations`);

      if (!response.ok) {
        return;
      }

      const data = await response.json();

      let items = [];

      if (Array.isArray(data)) {
        items = data;
      } else if (Array.isArray(data.conversations)) {
        items = data.conversations;
      } else if (
        data.data &&
        Array.isArray(data.data)
      ) {
        items = data.data;
      } else if (
        data.data &&
        Array.isArray(data.data.conversations)
      ) {
        items = data.data.conversations;
      }

      setConversations(items);
    } catch (err) {
      console.error("Conversation loading error:", err);
    }
  };

  // ============================================================
  // INITIAL LOAD
  // ============================================================

  useEffect(() => {
    loadDatasets();
    loadConversations();
  }, []);

  // ============================================================
  // SCROLL TO BOTTOM
  // ============================================================

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  // ============================================================
  // LOAD EXISTING CONVERSATION
  // ============================================================

  const loadConversation = async (id) => {
    if (!id) {
      return;
    }

    try {
      setLoadingConversation(true);
      setError("");

      const response = await fetch(
        `${API_BASE}/conversations/${id}`
      );

      if (!response.ok) {
        throw new Error("Unable to load conversation.");
      }

      const data = await response.json();

      const conversation =
        data.conversation || data;

      const conversationMessages =
        data.messages ||
        conversation.messages ||
        [];

      const normalizedMessages =
        Array.isArray(conversationMessages)
          ? conversationMessages.map((message) => ({
              id:
                message.id ||
                `${Date.now()}-${Math.random()}`,
              role:
                message.role ||
                message.sender ||
                "assistant",
              content:
                message.content ||
                message.message ||
                message.answer ||
                "",
              download_url:
                message.download_url ||
                message.downloadUrl ||
                null,
              download_filename:
                message.download_filename ||
                message.downloadFilename ||
                null,
              export_format:
                message.export_format ||
                message.exportFormat ||
                null,
            }))
          : [];

      setConversationId(id);
      setMessages(normalizedMessages);
    } catch (err) {
      console.error("Conversation error:", err);

      setError("Unable to load conversation.");
    } finally {
      setLoadingConversation(false);
    }
  };

  // ============================================================
  // NEW CONVERSATION
  // ============================================================

  const createNewConversation = async () => {
    try {
      setMessages([]);
      setConversationId(null);
      setError("");

      const response = await fetch(
        `${API_BASE}/conversations`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            title: "New Business Conversation",
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          "Unable to create conversation."
        );
      }

      const data = await response.json();

      const id =
        data.conversation_id ||
        data.id ||
        data.conversation?.id;

      if (id) {
        setConversationId(id);
      }

      await loadConversations();
    } catch (err) {
      console.error(
        "Create conversation error:",
        err
      );

      setError("Unable to create conversation.");
    }
  };

  // ============================================================
  // DOWNLOAD FILE
  // ============================================================

  const downloadFile = (downloadUrl) => {
    if (!downloadUrl) {
      return;
    }

    const fullUrl = downloadUrl.startsWith("http")
      ? downloadUrl
      : `${API_BASE}${downloadUrl}`;

    window.open(fullUrl, "_blank");
  };

  // ============================================================
  // SEND QUESTION
  // ============================================================

  const sendQuestion = async () => {
    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) {
      return;
    }

    const userMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmedQuestion,
    };

    setMessages((previous) => [
      ...previous,
      userMessage,
    ]);

    setQuestion("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_BASE}/ask-business`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query: trimmedQuestion,
            conversation_id: conversationId,
            dataset_id: selectedDatasetId,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            data.message ||
            "Unable to process the question."
        );
      }

      console.log(
        "ASK-BUSINESS RESPONSE:",
        data
      );

      /*
        Export information can be returned either directly:

        {
          download_url,
          download_filename,
          export_format
        }

        or through:

        {
          export: {
            filename,
            format,
            ...
          }
        }
      */

      const exportData =
        data.export || {};

      const downloadUrl =
        data.download_url ||
        data.downloadUrl ||
        exportData.download_url ||
        exportData.downloadUrl ||
        null;

      const downloadFilename =
        data.download_filename ||
        data.downloadFilename ||
        exportData.filename ||
        null;

      const exportFormat =
        data.export_format ||
        data.exportFormat ||
        exportData.format ||
        null;

      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content:
          data.answer ||
          data.message ||
          "I could not generate an answer.",
        download_url: downloadUrl,
        download_filename: downloadFilename,
        export_format: exportFormat,
      };

      setMessages((previous) => [
        ...previous,
        assistantMessage,
      ]);

      /*
        Backend may create the conversation
        automatically on the first message.
      */

      if (
        !conversationId &&
        data.conversation_id
      ) {
        setConversationId(
          data.conversation_id
        );
      }

      await loadConversations();
    } catch (err) {
      console.error(
        "Ask business error:",
        err
      );

      setMessages((previous) => [
        ...previous,
        {
          id: `error-${Date.now()}`,
          role: "assistant",
          content:
            err.message ||
            "Something went wrong while processing your question.",
        },
      ]);

      setError(
        err.message ||
          "Something went wrong."
      );
    } finally {
      setLoading(false);

      setTimeout(() => {
        textareaRef.current?.focus();
      }, 50);
    }
  };

  // ============================================================
  // ENTER KEY
  // ============================================================

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendQuestion();
    }
  };

  // ============================================================
  // TEXTAREA AUTO HEIGHT
  // ============================================================

  const handleQuestionChange = (event) => {
    setQuestion(event.target.value);

    const textarea = event.target;

    textarea.style.height = "auto";

    textarea.style.height = `${Math.min(
      textarea.scrollHeight,
      180
    )}px`;
  };

  // ============================================================
  // DATASET HELPERS
  // ============================================================

  const selectedDataset =
    Array.isArray(datasets)
      ? datasets.find(
          (dataset) =>
            Number(dataset.id) ===
            Number(selectedDatasetId)
        )
      : null;

  const getDatasetName = (dataset) => {
    return (
      dataset.name ||
      dataset.original_filename ||
      dataset.filename ||
      dataset.file_name ||
      `Dataset ${dataset.id}`
    );
  };

  const getDatasetRows = (dataset) => {
    return (
      dataset.rows ||
      dataset.row_count ||
      dataset.records ||
      dataset.records_count ||
      0
    );
  };

  // ============================================================
  // ANSWER FORMATTER
  // ============================================================

    // ============================================================
  // ANSWER FORMATTER
  // ============================================================

  const renderInlineMarkdown = (text) => {
    if (text === null || text === undefined) {
      return "";
    }

    const value = String(text);

    const parts = value.split(/(\*\*[^*]+\*\*)/g);

    return parts.map((part, index) => {
      if (
        part.startsWith("**") &&
        part.endsWith("**") &&
        part.length >= 4
      ) {
        return (
          <strong key={`bold-${index}`}>
            {part.slice(2, -2)}
          </strong>
        );
      }

      return (
        <span key={`text-${index}`}>
          {part}
        </span>
      );
    });
  };

  const renderAnswer = (content) => {
    if (!content) {
      return null;
    }

    const rawLines = String(content).split("\n");

    const elements = [];
    let tableRows = [];

    const flushTable = () => {
      if (tableRows.length === 0) {
        return;
      }

      const rows = tableRows;
      tableRows = [];

      if (rows.length < 2) {
        return;
      }

      const headerCells = rows[0]
        .split("|")
        .map((cell) => cell.trim());

      const dataRows = rows.slice(2).map((row) =>
        row
          .split("|")
          .map((cell) => cell.trim())
      );

      elements.push(
        <div
          key={`table-${elements.length}`}
          className="answer-table-wrapper"
        >
          <table className="answer-table">
            <thead>
              <tr>
                {headerCells.map((cell, index) => (
                  <th key={`header-${index}`}>
                    {renderInlineMarkdown(cell)}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {dataRows.map((row, rowIndex) => (
                <tr key={`row-${rowIndex}`}>
                  {headerCells.map((_, columnIndex) => (
                    <td key={`cell-${rowIndex}-${columnIndex}`}>
                      {renderInlineMarkdown(
                        row[columnIndex] ?? ""
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    };

    rawLines.forEach((line, index) => {
      const trimmed = line.trim();

      // --------------------------------------------------------
      // Blank line
      // --------------------------------------------------------

      if (!trimmed) {
        if (tableRows.length > 0) {
          flushTable();
        }

        elements.push(
          <div
            key={`space-${index}`}
            className="answer-spacer"
          />
        );

        return;
      }

      // --------------------------------------------------------
      // Markdown table
      // --------------------------------------------------------

      const looksLikeTableRow =
        trimmed.includes("|");

      const looksLikeSeparator =
        /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(
          trimmed
        );

      if (looksLikeTableRow || looksLikeSeparator) {
        tableRows.push(trimmed);
        return;
      }

      // --------------------------------------------------------
      // Finish any previous table
      // --------------------------------------------------------

      if (tableRows.length > 0) {
        flushTable();
      }

      // --------------------------------------------------------
      // Bullet
      // --------------------------------------------------------

      const isBullet =
        trimmed.startsWith("- ") ||
        trimmed.startsWith("* ") ||
        trimmed.startsWith("• ");

      if (isBullet) {
        const bulletText = trimmed
          .replace(/^[-*•]\s*/, "")
          .trim();

        elements.push(
          <div
            key={`bullet-${index}`}
            className="answer-list-item"
          >
            <span className="answer-list-marker">
              •
            </span>

            <span>
              {renderInlineMarkdown(bulletText)}
            </span>
          </div>
        );

        return;
      }

      // --------------------------------------------------------
      // Normal text
      // --------------------------------------------------------

      elements.push(
        <div
          key={`line-${index}`}
          className="answer-line"
        >
          {renderInlineMarkdown(line)}
        </div>
      );
    });

    // Flush table at end of answer
    if (tableRows.length > 0) {
      flushTable();
    }

    return elements;
  };

  // ============================================================
  // EXAMPLE QUESTIONS
  // ============================================================

  const exampleQuestions = [
    "Show all data",
    "Show Electronics products",
    "What is the average Price?",
    "Show Product and Price",
    "Show products where Price is greater than 5000",
    "Download all data as Excel",
    "Download Electronics products as CSV",
    "Create a PDF report of Laptop data",
  ];

  const useExampleQuestion = (value) => {
    setQuestion(value);

    setTimeout(() => {
      textareaRef.current?.focus();
    }, 50);
  };

  // ============================================================
  // RENDER
  // ============================================================

  return (
    <div className="chat-page">

      {/* ======================================================
          HEADER
      ====================================================== */}

      <div className="chat-header">
        <div>
          <div className="chat-title">
            Business Agent
          </div>

          <div className="chat-subtitle">
            Ask questions about your business data
          </div>
        </div>

        <button
          type="button"
          className="chat-new-button"
          onClick={createNewConversation}
        >
          New Chat
        </button>
      </div>

      {/* ======================================================
          DATASET BAR
      ====================================================== */}

      <div className="chat-dataset-bar">

        <div className="chat-dataset-info">

          <span className="chat-dataset-label">
            Dataset
          </span>

          {loadingDatasets ? (
            <span className="chat-dataset-value">
              Loading...
            </span>
          ) : (
            <select
              value={
                selectedDatasetId ?? ""
              }
              onChange={(event) => {
                const value =
                  event.target.value;

                setSelectedDatasetId(
                  value
                    ? Number(value)
                    : null
                );
              }}
              className="chat-dataset-select"
            >
              <option value="">
                All datasets
              </option>

              {Array.isArray(datasets) &&
                datasets.map((dataset) => (
                  <option
                    key={dataset.id}
                    value={dataset.id}
                  >
                    {getDatasetName(dataset)}
                  </option>
                ))}
            </select>
          )}

        </div>

        {selectedDataset && (
          <div className="chat-dataset-meta">
            {getDatasetRows(selectedDataset)} rows
          </div>
        )}

      </div>

      {/* ======================================================
          MAIN CHAT
      ====================================================== */}

      <div className="chat-scroll-area">

        <div className="chat-messages">

          {/* EMPTY STATE */}

          {messages.length === 0 &&
            !loadingConversation && (
              <div className="chat-welcome">

                <div className="chat-welcome-title">
                  What would you like to know?
                </div>

                <div className="chat-welcome-subtitle">
                  Ask your business data agent
                  about sales, products,
                  customers, invoices,
                  expenses, payments, or any
                  other uploaded data.
                </div>

                <div className="example-question-list">
                  {exampleQuestions.map(
                    (example) => (
                      <button
                        type="button"
                        key={example}
                        className="example-question"
                        onClick={() =>
                          useExampleQuestion(
                            example
                          )
                        }
                      >
                        {example}
                      </button>
                    )
                  )}
                </div>

              </div>
            )}

          {/* CONVERSATION LOADING */}

          {loadingConversation && (
            <div className="chat-empty">
              Loading conversation...
            </div>
          )}

          {/* ==================================================
              MESSAGES
          ================================================== */}

          {messages.map((message) => {

            const isUser =
              message.role === "user";

            const hasDownload =
              !isUser &&
              Boolean(
                message.download_url
              );

            return (
              <div
                key={message.id}
                className={`chat-row ${
                  isUser
                    ? "chat-row-user"
                    : "chat-row-assistant"
                }`}
              >

                <div className="chat-message">

                  <div className="message-label">
                    {isUser
                      ? "You"
                      : "Business Agent"}
                  </div>

                  <div
                    className={`message-bubble ${
                      isUser
                        ? "user-bubble"
                        : "assistant-bubble"
                    }`}
                  >
                    {isUser
                      ? message.content
                      : renderAnswer(
                          message.content
                        )}

                    {/* ========================================
                        DOWNLOAD CARD
                    ======================================== */}

                    {hasDownload && (
                      <div className="download-card">

                        <div className="download-card-main">

                          <div className="download-file-icon">
                            {(
                              message.export_format ||
                              "file"
                            )
                              .toString()
                              .toUpperCase()
                              .slice(
                                0,
                                4
                              )}
                          </div>

                          <div className="download-file-info">

                            <div className="download-file-title">
                              File ready
                            </div>

                            <div className="download-file-name">
                              {message.download_filename ||
                                "Download file"}
                            </div>

                          </div>

                        </div>

                        <button
                          type="button"
                          className="download-file-button"
                          onClick={() =>
                            downloadFile(
                              message.download_url
                            )
                          }
                        >
                          Download
                        </button>

                      </div>
                    )}

                  </div>

                </div>

              </div>
            );
          })}

          {/* ==================================================
              TYPING INDICATOR
          ================================================== */}

          {loading && (
            <div className="chat-row chat-row-assistant">

              <div className="chat-message">

                <div className="message-label">
                  Business Agent
                </div>

                <div className="message-bubble assistant-bubble typing-bubble">
                  <span>Thinking</span>
                  <span className="typing-dots">
                    ...
                  </span>
                </div>

              </div>

            </div>
          )}

          {/* ==================================================
              ERROR
          ================================================== */}

          {error && (
            <div className="chat-error">
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />

        </div>

      </div>

      {/* ======================================================
          INPUT
      ====================================================== */}

      <div className="chat-input-area">

        <div className="chat-input-container">

          <div className="chat-input-wrapper">

            <textarea
              ref={textareaRef}
              value={question}
              onChange={handleQuestionChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about your business data..."
              rows={1}
              disabled={loading}
            />

            <button
              type="button"
              className="chat-send-button"
              onClick={sendQuestion}
              disabled={
                loading ||
                !question.trim()
              }
              aria-label="Send question"
            >
              ↑
            </button>

          </div>

          <div className="chat-input-hint">
            Press Enter to send · Shift + Enter
            for a new line
          </div>

        </div>

      </div>

    </div>
  );
}

export default HRAgent;
