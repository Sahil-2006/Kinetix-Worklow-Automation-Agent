import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat } from "./api";
import ChatMessage from "./components/ChatMessage";
import ChatInput from "./components/ChatInput";
import TracePanel from "./components/TracePanel";
import AuthPage from "./components/AuthPage";

const SUGGESTIONS = [
  { icon: "📊", text: "Analyze sales.csv and tell me the top trends" },
  { icon: "📅", text: "Schedule a team meeting tomorrow at 2pm" },
  { icon: "📧", text: "Summarize daily-report.txt and email to ops@example.com" },
  { icon: "🔍", text: "Search for workflow automation best practices" },
];

function App() {
  // ── Auth state ─────────────────────────────────────────────
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("kinetix_user");
    if (stored) {
      try { return JSON.parse(stored); } catch { return null; }
    }
    return null;
  });
  const [token, setToken] = useState(() =>
    localStorage.getItem("kinetix_access_token") || ""
  );

  const isLoggedIn = Boolean(user && token);

  // Listen for forced logout events (e.g. token expired)
  useEffect(() => {
    const handleLogout = () => {
      setUser(null);
      setToken("");
    };
    window.addEventListener("kinetix-logout", handleLogout);
    return () => window.removeEventListener("kinetix-logout", handleLogout);
  }, []);

  const handleAuth = (data) => {
    setUser(data.user);
    setToken(data.access_token);
  };

  const handleLogout = () => {
    localStorage.removeItem("kinetix_access_token");
    localStorage.removeItem("kinetix_refresh_token");
    localStorage.removeItem("kinetix_user");
    setUser(null);
    setToken("");
  };

  // ── Chat state ─────────────────────────────────────────────
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [traces, setTraces] = useState([]);
  const [traceOpen, setTraceOpen] = useState(false);

  const messagesEndRef = useRef(null);
  const abortRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Shared event handler ───────────────────────────────────
  const makeEventHandler = () => {
    let assistantContent = "";

    return (event) => {
      switch (event.type) {
        case "thought":
        case "tool_start":
        case "tool_result":
          setTraces((prev) => [...prev, event]);
          break;

        case "answer":
          assistantContent = event.content || "";
          setMessages((prev) => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (updated[lastIdx]?.role === "assistant") {
              updated[lastIdx] = {
                role: "assistant",
                content: assistantContent,
                streaming: false,
              };
            }
            return updated;
          });
          setTraces((prev) => [...prev, event]);
          break;

        case "error":
          setTraces((prev) => [...prev, event]);
          if (!assistantContent) {
            setMessages((prev) => {
              const updated = [...prev];
              const lastIdx = updated.length - 1;
              if (updated[lastIdx]?.role === "assistant") {
                updated[lastIdx] = {
                  role: "assistant",
                  content: `⚠ Error: ${event.content || "Something went wrong."}`,
                  streaming: false,
                };
              }
              return updated;
            });
          }
          break;

        case "done":
          setIsStreaming(false);
          setMessages((prev) => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (updated[lastIdx]?.role === "assistant") {
              updated[lastIdx] = { ...updated[lastIdx], streaming: false };
            }
            return updated;
          });
          break;

        default:
          setTraces((prev) => [...prev, event]);
      }
    };
  };

  const sendMessage = useCallback(
    (text) => {
      if (!text.trim() || isStreaming) return;

      setMessages((prev) => [...prev, { role: "user", content: text }]);
      setInput("");
      setIsStreaming(true);

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "", streaming: true },
      ]);

      const handler = makeEventHandler();
      const controller = streamChat(text, handler);
      abortRef.current = controller;
    },
    [isStreaming]
  );

  const handleSend = useCallback(() => {
    sendMessage(input);
  }, [input, sendMessage]);

  const handleSuggestionClick = (text) => {
    sendMessage(text);
  };

  const clearTraces = () => setTraces([]);
  const hasMessages = messages.length > 0;

  // ── Render ─────────────────────────────────────────────────
  if (!isLoggedIn) {
    return <AuthPage onAuth={handleAuth} />;
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="logo-group">
          <div className="logo-mark">K</div>
          <span className="logo-text">Kinetix</span>
        </div>
        <div className="header-info">
          <span className="model-tag">ReAct Agent</span>
          <span className="header-user">
            {user?.username || "User"}
            {user?.role === "admin" && (
              <span className="role-badge">admin</span>
            )}
          </span>
          <button
            className="logout-btn"
            onClick={handleLogout}
            title="Sign out"
          >
            ↗ Logout
          </button>
          <span
            className={`header-badge ${isStreaming ? "online" : "offline"}`}
          >
            {isStreaming ? "● Processing" : "○ Ready"}
          </span>
        </div>
      </header>

      {/* Main: Chat + Trace */}
      <div className="main-layout">
        <div className="chat-panel">
          {!hasMessages ? (
            <div className="welcome-screen">
              <div className="welcome-icon">⚡</div>
              <h1 className="welcome-title">Welcome to Kinetix</h1>
              <p className="welcome-subtitle">
                Enterprise workflow automation powered by AI. Describe any task
                in natural language — I'll analyze data, schedule meetings, send
                emails, and more.
              </p>
              <div className="suggestion-grid">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.text}
                    className="suggestion-chip"
                    onClick={() => handleSuggestionClick(s.text)}
                  >
                    <span className="chip-icon">{s.icon}</span>
                    {s.text}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-messages">
              {messages.map((msg, i) => (
                <ChatMessage
                  key={i}
                  role={msg.role}
                  content={msg.content}
                  isStreaming={msg.streaming}
                />
              ))}
              {isStreaming &&
                messages[messages.length - 1]?.role === "assistant" &&
                !messages[messages.length - 1]?.content && (
                  <div className="thinking-indicator">
                    <div className="thinking-dots">
                      <span />
                      <span />
                      <span />
                    </div>
                    <span className="thinking-text">Agent is reasoning…</span>
                  </div>
                )}
              <div ref={messagesEndRef} />
            </div>
          )}

          <ChatInput
            value={input}
            onChange={setInput}
            onSubmit={handleSend}
            disabled={isStreaming}
            placeholder="Describe your workflow…"
          />
        </div>

        <TracePanel
          traces={traces}
          isActive={isStreaming}
          onClear={clearTraces}
          isOpen={traceOpen}
          onToggle={() => setTraceOpen(!traceOpen)}
        />
      </div>
    </div>
  );
}

export default App;
