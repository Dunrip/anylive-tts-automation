import React, { useCallback, useEffect, useRef, useState } from "react";
import type { LogLevel, LogMessage, WSMessage } from "../../lib/types";

interface LogViewerProps {
  messages: WSMessage[];
  isConnected: boolean;
  onClear?: () => void;
  height?: string;
}

const LEVEL_COLORS: Record<LogLevel, string> = {
  INFO: "var(--text-primary)",
  WARN: "var(--warning)",
  ERROR: "var(--error)",
  DEBUG: "var(--text-muted)",
};

function isLogMessage(msg: WSMessage): msg is LogMessage {
  return msg.type === "log";
}

export function LogViewer({
  messages,
  isConnected,
  onClear,
  height = "200px",
}: LogViewerProps): React.ReactElement {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState("");
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, autoScroll]);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) {
      return;
    }

    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 20;
    setAutoScroll(isAtBottom);
  }, []);

  const logMessages = messages.filter(isLogMessage);
  const filteredMessages = filter
    ? logMessages.filter((message) =>
        message.message.toLowerCase().includes(filter.toLowerCase())
      )
    : logMessages;

  const copyToClipboard = (): void => {
    const text = filteredMessages.map((message) => `[${message.level}] ${message.message}`).join("\n");
    void navigator.clipboard.writeText(text).catch(() => undefined);
  };

  return (
    <div
      data-testid="log-viewer"
      style={{
        display: "flex",
        flexDirection: "column",
        borderTop: "1px solid var(--border-default)",
        backgroundColor: "var(--bg-base)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "6px 12px",
          backgroundColor: "var(--bg-surface)",
          borderBottom: "1px solid var(--border-default)",
        }}
      >
        <button
          data-testid="collapse-button"
          onClick={() => setIsCollapsed((value) => !value)}
          style={{
            background: "none",
            border: "none",
            color: "var(--text-muted)",
            cursor: "pointer",
            fontSize: "12px",
            padding: "0 4px",
          }}
        >
          {isCollapsed ? "▲" : "▼"}
        </button>

        <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 500 }}>Logs</span>
        <div
          aria-label={isConnected ? "connected" : "disconnected"}
          style={{
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            backgroundColor: isConnected ? "var(--success)" : "var(--text-muted)",
          }}
        />

        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
          {filteredMessages.length} messages
        </span>

        <input
          data-testid="log-filter"
          type="text"
          placeholder="Filter logs..."
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          style={{
            flex: 1,
            padding: "2px 8px",
            backgroundColor: "var(--bg-elevated)",
            color: "var(--text-primary)",
            border: "1px solid var(--border-default)",
            borderRadius: "4px",
            fontSize: "12px",
          }}
        />

        <button
          data-testid="copy-logs-button"
          onClick={copyToClipboard}
          style={{
            background: "none",
            border: "none",
            color: "var(--text-muted)",
            cursor: "pointer",
            fontSize: "11px",
          }}
        >
          Copy
        </button>

        {onClear ? (
          <button
            data-testid="clear-logs-button"
            onClick={onClear}
            style={{
              background: "none",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              fontSize: "11px",
            }}
          >
            Clear
          </button>
        ) : null}

        {!autoScroll ? (
          <button
            data-testid="resume-scroll-button"
            onClick={() => setAutoScroll(true)}
            style={{
              padding: "2px 8px",
              backgroundColor: "var(--accent)",
              color: "white",
              border: "none",
              borderRadius: "4px",
              fontSize: "11px",
              cursor: "pointer",
            }}
          >
            Resume ↓
          </button>
        ) : null}
      </div>

      {!isCollapsed ? (
        <div
          ref={scrollRef}
          data-testid="log-content"
          onScroll={handleScroll}
          style={{
            height,
            overflowY: "auto",
            padding: "8px 12px",
            fontFamily: '"JetBrains Mono", "SF Mono", monospace',
            fontSize: "12px",
            lineHeight: "1.6",
          }}
        >
          {filteredMessages.length === 0 ? (
            <p style={{ color: "var(--text-muted)", margin: 0 }}>
              {filter ? "No matching log messages" : "Waiting for logs..."}
            </p>
          ) : (
            filteredMessages.map((message, index) => (
              <div
                key={`${message.timestamp}-${index}`}
                data-testid={`log-line-${index}`}
                style={{
                  color: LEVEL_COLORS[message.level] ?? "var(--text-primary)",
                  marginBottom: "1px",
                  wordBreak: "break-all",
                }}
              >
                <span style={{ color: "var(--text-muted)", marginRight: "8px" }}>[{message.level}]</span>
                {message.version ? (
                  <span style={{ color: "var(--accent)", marginRight: "8px" }}>[{message.version}]</span>
                ) : null}
                {message.message}
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
