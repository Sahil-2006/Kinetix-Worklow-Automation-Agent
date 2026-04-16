import { useEffect, useRef, useState } from "react";

const LABEL_MAP = {
  thought: "THINKING",
  tool_start: "TOOL START",
  tool_result: "TOOL RESULT",
  error: "ERROR",
  answer: "ANSWER",
  done: "DONE",
};

function TraceEntry({ entry }) {
  const [expanded, setExpanded] = useState(false);
  const type = entry.type;
  const isFailed = type === "tool_result" && entry.status === "failed";

  let className = `trace-entry ${type.replace("_", "-")}`;
  if (isFailed) className += " failed";

  let content = "";
  switch (type) {
    case "thought":
      content = entry.content || "";
      break;
    case "tool_start":
      content = `${entry.tool}(${
        entry.arguments ? Object.keys(entry.arguments).join(", ") : ""
      })`;
      break;
    case "tool_result":
      content = isFailed
        ? `✗ ${entry.tool} → ${entry.error || "failed"}`
        : `✓ ${entry.tool} → success`;
      break;
    case "error":
      content = entry.content || "Unknown error";
      break;
    case "answer":
      content = (entry.content || "").slice(0, 120) + (entry.content?.length > 120 ? "…" : "");
      break;
    default:
      content = JSON.stringify(entry);
  }

  const hasOutput =
    type === "tool_result" && entry.output && Object.keys(entry.output).length > 0;

  return (
    <div className={className}>
      <div className="trace-entry-label">
        {LABEL_MAP[type] || type.toUpperCase()}
        {entry.iteration !== undefined ? ` · iter ${entry.iteration + 1}` : ""}
      </div>
      <div className="trace-entry-content">{content}</div>
      {hasOutput && (
        <>
          <button
            className="trace-output-toggle"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "▾ hide output" : "▸ show output"}
          </button>
          {expanded && (
            <div className="trace-output-json">
              {JSON.stringify(entry.output, null, 2)}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function TracePanel({
  traces,
  isActive,
  onClear,
  isOpen,
  onToggle,
}) {
  const bodyRef = useRef(null);

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [traces]);

  return (
    <>
      {/* Mobile toggle button */}
      <button
        className="trace-toggle-btn"
        onClick={onToggle}
        title="Toggle trace panel"
      >
        {isOpen ? "✕" : "⚡"}
      </button>

      <aside className={`trace-panel ${isOpen ? "open" : ""}`}>
        <div className="trace-header">
          <div className="trace-title">
            <span
              className={`trace-title-dot ${isActive ? "" : "idle"}`}
            />
            Agent Trace
          </div>
          {traces.length > 0 && (
            <button className="trace-clear-btn" onClick={onClear}>
              Clear
            </button>
          )}
        </div>

        <div className="trace-body" ref={bodyRef}>
          {traces.length === 0 ? (
            <div className="trace-empty">
              Trace events will appear here in real-time as the agent reasons and acts.
            </div>
          ) : (
            traces
              .filter((t) => t.type !== "done")
              .map((entry, i) => <TraceEntry key={i} entry={entry} />)
          )}
        </div>
      </aside>
    </>
  );
}
