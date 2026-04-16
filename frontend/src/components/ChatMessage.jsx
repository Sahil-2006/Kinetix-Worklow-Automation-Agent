import { useState } from "react";

/**
 * Renders a single message bubble as Markdown-lite text.
 * Handles basic markdown: **bold**, `code`, bullet lists.
 */
function renderMarkdown(text) {
  if (!text) return null;

  const lines = text.split("\n");
  const elements = [];
  let listItems = [];

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`}>
          {listItems.map((li, i) => (
            <li key={i}>{formatInline(li)}</li>
          ))}
        </ul>
      );
      listItems = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Bullet list items
    if (/^[-*•]\s/.test(trimmed)) {
      listItems.push(trimmed.replace(/^[-*•]\s+/, ""));
      continue;
    }

    // Numbered list items
    if (/^\d+\.\s/.test(trimmed)) {
      listItems.push(trimmed.replace(/^\d+\.\s+/, ""));
      continue;
    }

    flushList();

    // Empty line
    if (!trimmed) continue;

    // Regular paragraph
    elements.push(<p key={`p-${i}`}>{formatInline(trimmed)}</p>);
  }

  flushList();
  return elements;
}

/** Inline formatting: **bold**, `code` */
function formatInline(text) {
  const parts = [];
  const regex = /(\*\*(.+?)\*\*|`(.+?)`)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    if (match[2]) {
      parts.push(<strong key={match.index}>{match[2]}</strong>);
    } else if (match[3]) {
      parts.push(<code key={match.index}>{match[3]}</code>);
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length ? parts : text;
}

export default function ChatMessage({ role, content, isStreaming }) {
  const isUser = role === "user";

  return (
    <div className={`message-row ${isUser ? "user" : "agent"}`}>
      <div
        className={`message-avatar ${isUser ? "user-avatar" : "agent-avatar"}`}
      >
        {isUser ? "Y" : "K"}
      </div>
      <div
        className={`message-bubble ${isUser ? "user-bubble" : "agent-bubble"}`}
      >
        {renderMarkdown(content)}
        {isStreaming && <span className="streaming-cursor" />}
      </div>
    </div>
  );
}
