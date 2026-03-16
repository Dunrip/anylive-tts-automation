import React, { useCallback, useEffect, useRef, useState } from "react";
import type { LogLevel, LogMessage, WSMessage } from "../../lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

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
      className="flex flex-col border-t border-[var(--border-default)] bg-[var(--bg-base)]"
    >
      <div className="flex items-center gap-2 px-3 py-1.5 bg-[var(--bg-surface)] border-b border-[var(--border-default)]">
        <Button
          variant="ghost"
          size="icon-xs"
          data-testid="collapse-button"
          onClick={() => setIsCollapsed((value) => !value)}
        >
          {isCollapsed ? "▲" : "▼"}
        </Button>

        <span className="text-xs text-[var(--text-secondary)] font-medium">Logs</span>
        <div
          aria-label={isConnected ? "connected" : "disconnected"}
          className={cn("size-1.5 rounded-full", isConnected ? "bg-[var(--success)]" : "bg-[var(--text-muted)]")}
        />

        <span className="text-[11px] text-[var(--text-muted)]">
          {filteredMessages.length} messages
        </span>

        <input
          data-testid="log-filter"
          type="text"
          placeholder="Filter logs..."
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          className="flex-1 px-2 py-0.5 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded text-xs"
        />

        <Button
          variant="ghost"
          size="xs"
          data-testid="copy-logs-button"
          onClick={copyToClipboard}
        >
          Copy
        </Button>

        {onClear ? (
          <Button
            variant="ghost"
            size="xs"
            data-testid="clear-logs-button"
            onClick={onClear}
          >
            Clear
          </Button>
        ) : null}

        {!autoScroll ? (
          <Button
            size="xs"
            data-testid="resume-scroll-button"
            onClick={() => setAutoScroll(true)}
          >
            Resume ↓
          </Button>
        ) : null}
      </div>

      {!isCollapsed ? (
        <div
          ref={scrollRef}
          data-testid="log-content"
          onScroll={handleScroll}
          className="overflow-y-auto p-2 px-3 font-mono text-xs leading-relaxed"
          style={{ height }}
        >
          {filteredMessages.length === 0 ? (
            <p className="text-[var(--text-muted)] m-0">
              {filter ? "No matching log messages" : "Waiting for logs..."}
            </p>
          ) : (
            filteredMessages.map((message, index) => (
              <div
                key={`${message.timestamp}-${index}`}
                data-testid={`log-line-${index}`}
                className="mb-px break-all"
                style={{
                  color: LEVEL_COLORS[message.level] ?? "var(--text-primary)",
                }}
              >
                <span className="text-[var(--text-muted)] mr-2">[{message.level}]</span>
                {message.version ? (
                  <span className="text-primary mr-2">[{message.version}]</span>
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
