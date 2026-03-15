import React, { useState } from "react";
import { CSVPicker } from "../common/CSVPicker";
import { StatusBadge } from "../common/StatusBadge";
import { ProgressBar } from "../common/ProgressBar";
import { useAutomation } from "../../hooks/useAutomation";
import { useWebSocket } from "../../hooks/useWebSocket";
import type { CSVPreviewResponse } from "../../lib/types";

interface FAQPanelProps {
  client: string;
  sidecarUrl?: string | null;
}

export function FAQPanel({ client, sidecarUrl }: FAQPanelProps): React.ReactElement {
  const [csvPath, setCsvPath] = useState<string | null>(null);
  const [csvPreview, setCsvPreview] = useState<CSVPreviewResponse | null>(null);
  const [audioDir, setAudioDir] = useState<string>("");
  const [options, setOptions] = useState({
    headless: true,
    dry_run: false,
    debug: false,
  });

  const automation = useAutomation();
  const ws = useWebSocket(automation.wsUrl);

  // Process WebSocket messages
  const processedCountRef = React.useRef(0);
  React.useEffect(() => {
    const newMessages = ws.messages.slice(processedCountRef.current);
    newMessages.forEach(automation.handleMessage);
    processedCountRef.current = ws.messages.length;
  }, [ws.messages.length]);

  const configPath = `configs/${client}/live.json`;

  const handleCsvSelected = (path: string, preview: CSVPreviewResponse): void => {
    setCsvPath(path);
    setCsvPreview(preview);
  };

  const handleRun = async (): Promise<void> => {
    if (!csvPath || !sidecarUrl || automation.isRunning) return;
    await automation.startRun({
      sidecarUrl,
      endpoint: "/api/faq/run",
      configPath,
      csvPath,
      options: {
        headless: options.headless,
        dry_run: options.dry_run,
        debug: options.debug,
        audio_dir: audioDir || undefined,
      },
      estimatedVersions: csvPreview?.estimated_versions || 0,
    });
  };

  return (
    <div
      data-testid="faq-panel"
      style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px", height: "100%", overflowY: "auto" }}
    >
      <h2 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
        ❓ FAQ Automation
      </h2>

      {/* CSV Picker */}
      <CSVPicker
        onFileSelected={handleCsvSelected}
        onClear={() => { setCsvPath(null); setCsvPreview(null); }}
        sidecarUrl={sidecarUrl}
        configPath={configPath}
      />

      {/* Audio directory input */}
      <div>
        <label style={{ fontSize: "12px", color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>
          Audio Directory (optional)
        </label>
        <input
          data-testid="audio-dir-input"
          type="text"
          value={audioDir}
          onChange={(e) => setAudioDir(e.target.value)}
          placeholder="downloads/"
          style={{
            width: "100%",
            padding: "6px 10px",
            backgroundColor: "var(--bg-elevated)",
            color: "var(--text-primary)",
            border: "1px solid var(--border-default)",
            borderRadius: "6px",
            fontSize: "13px",
            boxSizing: "border-box",
          }}
        />
      </div>

      {/* Options */}
      <div style={{ display: "flex", gap: "16px" }}>
        {[
          { key: "headless" as const, label: "Headless" },
          { key: "dry_run" as const, label: "Dry Run" },
          { key: "debug" as const, label: "Debug" },
        ].map(({ key, label }) => (
          <label key={key} style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", color: "var(--text-secondary)", cursor: "pointer" }}>
            <input
              data-testid={`faq-option-${key}`}
              type="checkbox"
              checked={options[key]}
              onChange={() => setOptions((prev) => ({ ...prev, [key]: !prev[key] }))}
            />
            {label}
          </label>
        ))}
      </div>

      {/* Run button */}
      <div style={{ display: "flex", gap: "8px" }}>
        <button
          data-testid="faq-run-button"
          onClick={handleRun}
          disabled={!csvPath || automation.isRunning || !sidecarUrl}
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
      </div>

      {/* Error banner */}
      {automation.error && (
        <div data-testid="faq-error" style={{ padding: "8px 12px", backgroundColor: "rgba(239,68,68,0.1)", border: "1px solid var(--error)", borderRadius: "6px", fontSize: "13px", color: "var(--error)" }}>
          {automation.error}
        </div>
      )}

      {/* Progress */}
      {(automation.isRunning || automation.progress.current > 0) && (
        <ProgressBar current={automation.progress.current} total={automation.progress.total} />
      )}

      {/* Product list */}
      {automation.versions.length > 0 && (
        <div data-testid="product-list" style={{ border: "1px solid var(--border-default)", borderRadius: "6px", overflow: "hidden" }}>
          {automation.versions.map((v, i) => (
            <div
              key={i}
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
              <StatusBadge status={v.status} size="sm" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
