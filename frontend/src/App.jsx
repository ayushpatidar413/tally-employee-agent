
import { useEffect, useState } from "react";

import "./App.css";

import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import UploadData from "./components/UploadData";
import HRAgent from "./components/HRAgent";
import History from "./components/History";

function App() {
  const [activePage, setActivePage] =
    useState("dashboard");

  const [mobileMenuOpen, setMobileMenuOpen] =
    useState(false);

  const [conversationId, setConversationId] =
    useState(null);

  const [theme, setTheme] = useState(() => {
    return (
      localStorage.getItem(
        "hr-agent-theme"
      ) || "white"
    );
  });

  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      theme
    );

    localStorage.setItem(
      "hr-agent-theme",
      theme
    );
  }, [theme]);

  const handleNewConversation = () => {
    setConversationId(null);
    setActivePage("agent");
    setMobileMenuOpen(false);
  };

  const handleSelectConversation = (id) => {
    setConversationId(id);
    setActivePage("agent");
    setMobileMenuOpen(false);
  };

  const handleConversationCreated = (
    id
  ) => {
    setConversationId(id);
  };

  const changeTheme = () => {
    setTheme((current) => {
      if (current === "white") {
        return "dark";
      }

      if (current === "dark") {
        return "black";
      }

      return "white";
    });
  };

  const renderPage = () => {
    if (activePage === "dashboard") {
      return (
        <Dashboard
          setActivePage={setActivePage}
        />
      );
    }

    if (activePage === "upload") {
      return <UploadData />;
    }

    if (activePage === "agent") {
      return (
        <HRAgent
          conversationId={conversationId}
          onConversationCreated={
            handleConversationCreated
          }
        />
      );
    }

    if (activePage === "history") {
      return <History />;
    }

    return (
      <Dashboard
        setActivePage={setActivePage}
      />
    );
  };

  return (
    <div className="app-shell">
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
        mobileMenuOpen={mobileMenuOpen}
        setMobileMenuOpen={
          setMobileMenuOpen
        }
        conversationId={conversationId}
        onNewConversation={
          handleNewConversation
        }
        onSelectConversation={
          handleSelectConversation
        }
        theme={theme}
        onChangeTheme={changeTheme}
      />

      <main className="main-content">
        <button
          type="button"
          className="mobile-menu-button"
          onClick={() =>
            setMobileMenuOpen(
              (value) => !value
            )
          }
          aria-label="Open menu"
        >
          <span />
          <span />
          <span />
        </button>

        <div className="main-page-wrapper">
          {renderPage()}
        </div>
      </main>
    </div>
  );
}

export default App;
