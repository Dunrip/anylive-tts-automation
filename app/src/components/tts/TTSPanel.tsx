import React, { useEffect, useRef, useState } from "react";
import { CSVPicker } from "../common/CSVPicker";
import { StatusBadge } from "../common/StatusBadge";
import { ProgressBar } from "../common/ProgressBar";
import { useAutomation } from "../../hooks/useAutomation";
import { useWebSocket } from "../../hooks/useWebSocket";
import type { CSVPreviewResponse, WSMessage } from "../../lib/types";

interface TTSPanelProps {
  client: string;
  sidecarUrl?: string | null;
  onRunStart?: (jobId: string) => void;
  onLogStateChange?: (logState: {
    messages: WSMessage[];
    isConnected: boolean;
    clearMessages: () => void;
  }) => void;
}

interface RunOptions {
  headless: boolean;
  dry_run: boolean;
  debug: boolean;
  start_version?: number;
  limit?: number;
}

export function TTSPanel({
  client,
  sidecarUrl,
  onRunStart,
  onLogStateChange,
}: TTSPanelProps): React.ReactElement {
  const [csvPath, setCsvPath] = useState<string | null>(null);
  const [estimatedVersions, setEstimatedVersions] = useState(0);
  const [options, setOptions] = useState<RunOptions>({
    headless: true,
    dry_run: false,
    debug: false,
  });
  const [jobStartTime, setJobStartTime] = useState<number | undefined>();
  const processedCountRef = useRef(0);
  const hasConnectedRef = useRef(false);
  const automation = useAutomation();
  const ws = useWebSocket(automation.wsUrl);

  const configPath = `configs/${client}/tts.json`;

  const handleCsvSelected = (path: string, preview: CSVPreviewResponse): void => {
    setCsvPath(path);
    setEstimatedVersions(preview.estimated_versions);
  };

  useEffect(() => {
    if (ws.isConnected) {
      hasConnectedRef.current = true;
    }
  }, [ws.isConnected]);

  useEffect(() => {
    processedCountRef.current = 0;
    hasConnectedRef.current = false;
  }, [automation.wsUrl]);

  useEffect(() => {
    const newMessages = ws.messages.slice(processedCountRef.current);
    newMessages.forEach(automation.handleMessage);
    processedCountRef.current = ws.messages.length;
  }, [ws.messages, automation.handleMessage]);

  useEffect(() => {
    if (!onLogStateChange) {
      return;
    }
    onLogStateChange({
      messages: ws.messages,
      isConnected: ws.isConnected,
      clearMessages: ws.clearMessages,
    });
  }, [ws.messages, ws.isConnected, ws.clearMessages, onLogStateChange]);

  useEffect(() => {
    if (automation.jobId) {
      onRunStart?.(automation.jobId);
    }
  }, [automation.jobId, onRunStart]);

  const handleRun = async (): Promise<void> => {
    if (!csvPath || !sidecarUrl || automation.isRunning) {
      return;
    }

    ws.clearMessages();
    processedCountRef.current = 0;
    setJobStartTime(Date.now());

    await automation.startRun({
      sidecarUrl,
      endpoint: "/api/tts/run",
      configPath,
      csvPath,
      options: {
        headless: options.headless,
        dry_run: options.dry_run,
        debug: options.debug,
        start_version: options.start_version,
        limit: options.limit,
      },
      estimatedVersions,
    });
  };

  const toggleOption = (key: keyof RunOptions): void => {
    setOptions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div
      data-testid="tts-panel"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        padding: "16px",
        height: "100%",
        overflowY: "auto",
      }}
    >
      <h2 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
        🎙️ TTS Automation
      </h2>

      {/* CSV Picker */}
      <CSVPicker
        onFileSelected={handleCsvSelected}
        onClear={() => {
          setCsvPath(null);
          setEstimatedVersions(0);
          automation.reset();
          ws.clearMessages();
          processedCountRef.current = 0;
        }}
        sidecarUrl={sidecarUrl}
        configPath={configPath}
      />

      {automation.error ? (
        <div
          data-testid="automation-error"
          style={{
            padding: "8px 10px",
            borderRadius: "6px",
            border: "1px solid var(--error)",
            color: "var(--error)",
            fontSize: "12px",
            backgroundColor: "color-mix(in srgb, var(--error) 10%, transparent)",
          }}
        >
          {automation.error}
        </div>
      ) : null}

      {automation.isRunning && automation.wsUrl && hasConnectedRef.current && !ws.isConnected ? (
        <div
          data-testid="connection-lost-banner"
          style={{
            padding: "8px 10px",
            borderRadius: "6px",
            border: "1px solid var(--warning)",
            color: "var(--warning)",
            fontSize: "12px",
            backgroundColor: "color-mix(in srgb, var(--warning) 10%, transparent)",
          }}
        >
          Connection lost
        </div>
      ) : null}

      {/* Options row */}
      <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
        {[
          { key: "headless" as const, label: "Headless" },
          { key: "dry_run" as const, label: "Dry Run" },
          { key: "debug" as const, label: "Debug" },
        ].map(({ key, label }) => (
          <label
            key={key}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "13px",
              color: "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            <input
              data-testid={`option-${key}`}
              type="checkbox"
              checked={options[key] as boolean}
              onChange={() => toggleOption(key)}
            />
            {label}
          </label>
        ))}
      </div>

      {/* Run button */}
      <div style={{ display: "flex", gap: "8px" }}>
        <button
          data-testid="run-button"
          onClick={handleRun}
          disabled={!csvPath || automation.isRunning || !sidecarUrl}
          title={!sidecarUrl ? "Sidecar not connected" : !csvPath ? "Select a CSV file first" : ""}
          style={{
            padding: "8px 24px",
            backgroundColor: automation.isRunning ? "var(--bg-elevated)" : "var(--accent)",
            color: "white",
            border: "none",
            borderRadius: "6px",
            fontSize: "14px",
            fontWeight: 600,
            cursor: !csvPath || automation.isRunning || !sidecarUrl ? "not-allowed" : "pointer",
            opacity: !csvPath || automation.isRunning || !sidecarUrl ? 0.6 : 1,
          }}
        >
          {automation.isRunning ? "⟳ Running..." : "▶ Run"}
        </button>
        <button
          data-testid="stop-button"
          disabled={true}
          title="Stop not available in MVP"
          style={{
            padding: "8px 16px",
            backgroundColor: "transparent",
            color: "var(--text-muted)",
            border: "1px solid var(--border-default)",
            borderRadius: "6px",
            fontSize: "14px",
            cursor: "not-allowed",
            opacity: 0.5,
          }}
        >
          ⏹ Stop
        </button>
      </div>

      {/* Progress bar (shown when running or has progress) */}
      {(automation.isRunning || automation.progress.current > 0) && (
        <ProgressBar
          current={automation.progress.current}
          total={automation.progress.total}
          startTime={jobStartTime}
        />
      )}

      {/* Version list */}
      {automation.versions.length > 0 && (
        <div>
          <p style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "8px" }}>
            {automation.versions.length} versions
          </p>
          <div
            data-testid="version-list"
            style={{
              border: "1px solid var(--border-default)",
              borderRadius: "6px",
              overflow: "hidden",
            }}
          >
            {automation.versions.map((v, i) => (
              <div
                key={i}
                data-testid={`version-item-${i}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  borderBottom: i < automation.versions.length - 1 ? "1px solid var(--border-default)" : "none",
                  backgroundColor: i % 2 === 0 ? "transparent" : "var(--bg-surface)",
                }}
              >
                <span style={{ fontSize: "13px", color: "var(--text-primary)" }}>{v.name}</span>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <StatusBadge status={v.status} size="sm" />
                  {v.status === "failed" && (
                    <button
                      style={{
                        fontSize: "11px",
                        padding: "2px 6px",
                        backgroundColor: "transparent",
                        color: "var(--text-muted)",
                        border: "1px solid var(--border-default)",
                        borderRadius: "3px",
                        cursor: "pointer",
                      }}
                    >
                      Retry
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
