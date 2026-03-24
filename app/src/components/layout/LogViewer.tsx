import React, { useCallback, useEffect, useRef, useState } from "react";
import type { LogLevel, LogMessage, WSMessage } from "../../lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface LogViewerProps {
  messages: WSMessage[];
  isConnected: boolean;
  onClear?: () => void;
}

const LEVEL_COLORS: Record<LogLevel, string> = {
  INFO: "var(--text-primary)",
  WARN: "var(--warning)",
  ERROR: "var(--error)",
  DEBUG: "var(--text-muted)",
};

const STORAGE_KEY = "logviewer-height";
const DEFAULT_HEIGHT = 220;
const MIN_HEIGHT = 100;
const MAX_HEIGHT = 500;

function getStoredHeight(): number {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = parseInt(stored, 10);
      if (!isNaN(parsed) && parsed >= MIN_HEIGHT && parsed <= MAX_HEIGHT) return parsed;
    }
  } catch {
    // localStorage unavailable
  }
  return DEFAULT_HEIGHT;
}

function isLogMessage(msg: WSMessage): msg is LogMessage {
  return msg.type === "log";
}

function formatLogTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}

export function LogViewer({
  messages,
  isConnected,
  onClear,
}: LogViewerProps): React.ReactElement {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState("");
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [height, setHeight] = useState(getStoredHeight);
  const [enabledLevels, setEnabledLevels] = useState<Set<LogLevel>>(
    new Set(["INFO", "WARN", "ERROR", "DEBUG"] as LogLevel[])
  );
  const isDragging = useRef(false);
  const dragStartY = useRef(0);
  const dragStartHeight = useRef(0);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, autoScroll]);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 20;
    setAutoScroll(isAtBottom);
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    dragStartY.current = e.clientY;
    dragStartHeight.current = height;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "row-resize";
  }, [height]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent): void => {
      if (!isDragging.current) return;
      const delta = dragStartY.current - e.clientY;
      const newHeight = Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, dragStartHeight.current + delta));
      setHeight(newHeight);
    };

    const handleMouseUp = (): void => {
      if (!isDragging.current) return;
      isDragging.current = false;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      try {
        localStorage.setItem(STORAGE_KEY, String(height));
      } catch {
        // localStorage unavailable
      }
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [height]);

  const toggleLevel = (level: LogLevel): void => {
    setEnabledLevels((prev) => {
      const next = new Set(prev);
      if (next.has(level)) {
        next.delete(level);
      } else {
        next.add(level);
      }
      return next;
    });
  };

  const logMessages = messages.filter(isLogMessage);
  const filteredMessages = logMessages
    .filter((message) => enabledLevels.has(message.level))
    .filter((message) =>
      filter ? message.message.toLowerCase().includes(filter.toLowerCase()) : true
    );

  const copyToClipboard = (): void => {
    const text = filteredMessages
      .map((message) => `[${formatLogTime(message.timestamp)}] [${message.level}] ${message.message}`)
      .join("\n");
    void navigator.clipboard.writeText(text).catch(() => undefined);
  };

  const handleExport = async (): Promise<void> => {
    if (filteredMessages.length === 0) return;
    const content = filteredMessages
      .map((message) => `[${formatLogTime(message.timestamp)}] [${message.level}] ${message.message}`)
      .join("\n");
    try {
      const { save } = await import("@tauri-apps/plugin-dialog");
      const path = await save({
        defaultPath: "logs.txt",
        filters: [{ name: "Text", extensions: ["txt"] }],
      });
      if (!path) return; // user cancelled
      const { writeTextFile } = await import("@tauri-apps/plugin-fs");
      await writeTextFile(path, content);
    } catch {
      // silently ignore export errors
    }
  };

  return (
    <div
      data-testid="log-viewer"
      className="flex flex-col border-t border-[var(--border-default)] bg-[var(--bg-base)]"
    >
      <div
        data-testid="log-resize-handle"
        onMouseDown={handleMouseDown}
        className="h-1 cursor-row-resize bg-transparent hover:bg-[var(--border-active)] transition-colors shrink-0"
      />

      <div className="flex items-center gap-2 px-3 py-1.5 bg-[var(--bg-surface)] border-b border-[var(--border-default)]">
        <Button
          variant="ghost"
          size="icon-xs"
          data-testid="collapse-button"
          onClick={() => setIsCollapsed((value) => !value)}
          aria-label={isCollapsed ? "Expand logs" : "Collapse logs"}
        >
          {isCollapsed ? "▲" : "▼"}
        </Button>

        <span className="text-xs text-[var(--text-secondary)] font-medium">Logs</span>
        <div
          aria-label={isConnected ? "connected" : "disconnected"}
          className={cn("size-1.5 rounded-full", isConnected ? "bg-[var(--success)]" : "bg-[var(--text-muted)]")}
        />

        <span className="text-[length:var(--text-xs)] text-[var(--text-muted)]">
          {filteredMessages.length} messages
        </span>

        <div className="flex items-center gap-0.5">
          {(["INFO", "WARN", "ERROR", "DEBUG"] as LogLevel[]).map((level) => {
            const isActive = enabledLevels.has(level);
            return (
              <Button
                key={level}
                data-testid={`level-toggle-${level}`}
                variant="ghost"
                size="xs"
                onClick={() => toggleLevel(level)}
                className={cn(
                  "text-xs px-1.5 h-5",
                  isActive ? "opacity-100" : "opacity-30"
                )}
                style={isActive ? { color: LEVEL_COLORS[level] } : undefined}
              >
                {level}
              </Button>
            );
          })}
        </div>

        <input
          data-testid="log-filter"
          type="text"
          placeholder="Filter logs..."
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          className="flex-1 px-2 py-0.5 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded text-xs"
        />

        <Button variant="ghost" size="xs" data-testid="copy-logs-button" onClick={copyToClipboard}>
          Copy
        </Button>

        <Button
          variant="ghost"
          size="xs"
          data-testid="export-logs-button"
          onClick={() => { void handleExport(); }}
          disabled={filteredMessages.length === 0}
        >
          Export
        </Button>

        {onClear ? (
          <Button variant="ghost" size="xs" data-testid="clear-logs-button" onClick={onClear}>
            Clear
          </Button>
        ) : null}

        {!autoScroll ? (
          <Button size="xs" data-testid="resume-scroll-button" onClick={() => setAutoScroll(true)}>
            Resume
          </Button>
        ) : null}
      </div>

      {!isCollapsed ? (
        <div
          ref={scrollRef}
          data-testid="log-content"
          role="log"
          aria-live="polite"
          onScroll={handleScroll}
          className="overflow-y-auto p-2 px-3 font-mono text-xs leading-relaxed"
          style={{ height: `${height}px` }}
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
                <span className="text-[var(--text-muted)] mr-1.5 select-none">{formatLogTime(message.timestamp)}</span>
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
