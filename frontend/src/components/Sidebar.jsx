
import { useEffect, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

function Sidebar({
  activePage,
  setActivePage,
  mobileMenuOpen,
  setMobileMenuOpen,
  conversationId,
  onNewConversation,
  onSelectConversation,
  theme,
  onChangeTheme,
}) {
  const [conversations, setConversations] =
    useState([]);

  const [loading, setLoading] =
    useState(false);

  const loadConversations = async () => {
    try {
      setLoading(true);

      const response = await fetch(
        `${API_BASE}/conversations`
      );

      if (!response.ok) {
        throw new Error(
          "Failed to load conversations"
        );
      }

      const data = await response.json();

      setConversations(
        Array.isArray(data)
          ? data
          : data.conversations || []
      );
    } catch (error) {
      console.error(
        "Conversation loading error:",
        error
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConversations();
  }, [conversationId]);

  const openPage = (page) => {
    setActivePage(page);
    setMobileMenuOpen(false);
  };

  const newConversation = () => {
    onNewConversation();
    setMobileMenuOpen(false);
  };

  const openConversation = (id) => {
    onSelectConversation(id);
    setMobileMenuOpen(false);
  };

  const deleteConversation = async (
    event,
    id
  ) => {
    event.stopPropagation();

    try {
      const response = await fetch(
        `${API_BASE}/conversations/${id}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error(
          "Failed to delete conversation"
        );
      }

      if (
        String(conversationId) ===
        String(id)
      ) {
        onNewConversation();
      }

      await loadConversations();
    } catch (error) {
      console.error(
        "Delete conversation error:",
        error
      );
    }
  };

  const formatDate = (value) => {
    if (!value) {
      return "";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    const now = new Date();

    if (
      date.toDateString() ===
      now.toDateString()
    ) {
      return date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
    }

    return date.toLocaleDateString([], {
      day: "2-digit",
      month: "short",
    });
  };

  const themeSymbol =
    theme === "white"
      ? "☼"
      : theme === "dark"
      ? "◐"
      : "●";

  const nextTheme =
    theme === "white"
      ? "Dark"
      : theme === "dark"
      ? "Black"
      : "Light";

  return (
    <>
      <aside
        className={`sidebar ${
          mobileMenuOpen
            ? "sidebar-mobile-open"
            : ""
        }`}
      >
        {/* BRAND */}
        <div className="sidebar-brand">
          <div className="brand-row">
            <div className="brand-mark">
              HR
            </div>

            <div className="brand-content">
              <div className="brand-title">
                Tally HR Agent
              </div>

              <div className="brand-subtitle">
                Employee intelligence
                workspace
              </div>
            </div>
          </div>
        </div>

        {/* WORKSPACE */}
        <div className="workspace-section">
          <div className="section-heading">
            Workspace
          </div>

          <div className="workspace-list">
            <button
              type="button"
              className={`workspace-button ${
                activePage ===
                "dashboard"
                  ? "workspace-button-active"
                  : ""
              }`}
              onClick={() =>
                openPage("dashboard")
              }
            >
              <div className="workspace-text">
                <div className="workspace-title">
                  Dashboard
                </div>

                <div className="workspace-description">
                  Employee overview
                </div>
              </div>

              {activePage ===
                "dashboard" && (
                <span className="active-indicator" />
              )}
            </button>

            <button
              type="button"
              className={`workspace-button ${
                activePage === "upload"
                  ? "workspace-button-active"
                  : ""
              }`}
              onClick={() =>
                openPage("upload")
              }
            >
              <div className="workspace-text">
                <div className="workspace-title">
                  Upload Data
                </div>

                <div className="workspace-description">
                  Add employee files
                </div>
              </div>

              {activePage ===
                "upload" && (
                <span className="active-indicator" />
              )}
            </button>

            <button
              type="button"
              className={`workspace-button ${
                activePage === "agent"
                  ? "workspace-button-active"
                  : ""
              }`}
              onClick={() =>
                openPage("agent")
              }
            >
              <div className="workspace-text">
                <div className="workspace-title">
                  HR Agent
                </div>

                <div className="workspace-description">
                  Ask employee questions
                </div>
              </div>

              {activePage === "agent" && (
                <span className="active-indicator" />
              )}
            </button>

            <button
              type="button"
              className={`workspace-button ${
                activePage ===
                "history"
                  ? "workspace-button-active"
                  : ""
              }`}
              onClick={() =>
                openPage("history")
              }
            >
              <div className="workspace-text">
                <div className="workspace-title">
                  Upload History
                </div>

                <div className="workspace-description">
                  Uploaded files
                </div>
              </div>

              {activePage ===
                "history" && (
                <span className="active-indicator" />
              )}
            </button>
          </div>
        </div>

        {/* NEW CONVERSATION */}
        <div className="new-conversation-area">
          <button
            type="button"
            className="new-conversation-button"
            onClick={
              newConversation
            }
          >
            <span className="new-conversation-plus">
              +
            </span>

            <span>
              New Conversation
            </span>
          </button>
        </div>

        {/* RECENTS */}
        <div className="recents-section">
          <div className="recents-header">
            <span className="section-heading">
              Recents
            </span>

            <div className="recents-actions">
              {/* REFRESH CIRCLE */}
              <button
                type="button"
                className="circle-action-button"
                onClick={
                  loadConversations
                }
                title="Refresh conversations"
                aria-label="Refresh conversations"
              >
                ↻
              </button>

              {/* THEME CIRCLE */}
              <button
                type="button"
                className="circle-action-button theme-button"
                onClick={
                  onChangeTheme
                }
                title={`Change to ${nextTheme} theme`}
                aria-label={`Change to ${nextTheme} theme`}
              >
                {themeSymbol}
              </button>
            </div>
          </div>

          <div className="recents-list">
            {loading ? (
              <div className="recents-empty">
                Loading conversations...
              </div>
            ) : conversations.length ===
              0 ? (
              <div className="recents-empty">
                No conversations yet.
                <br />
                Start a new HR
                conversation.
              </div>
            ) : (
              conversations.map(
                (conversation) => {
                  const id =
                    conversation.conversation_id ||
                    conversation.id;

                  return (
                    <button
                      type="button"
                      key={id}
                      className={`recent-item ${
                        String(
                          conversationId
                        ) ===
                        String(id)
                          ? "recent-item-active"
                          : ""
                      }`}
                      onClick={() =>
                        openConversation(
                          id
                        )
                      }
                    >
                      <div className="recent-item-content">
                        <div className="recent-item-title">
                          {conversation.title ||
                            "New Conversation"}
                        </div>

                        <div className="recent-item-date">
                          {formatDate(
                            conversation.updated_at ||
                              conversation.created_at
                          )}
                        </div>
                      </div>

                      <span
                        className="delete-conversation"
                        onClick={(
                          event
                        ) =>
                          deleteConversation(
                            event,
                            id
                          )
                        }
                        title="Delete conversation"
                      >
                        ×
                      </span>
                    </button>
                  );
                }
              )
            )}
          </div>
        </div>
      </aside>

      {/* MOBILE OVERLAY */}
      {mobileMenuOpen && (
        <div
          className="sidebar-overlay"
          onClick={() =>
            setMobileMenuOpen(false)
          }
        />
      )}
    </>
  );
}

export default Sidebar;
