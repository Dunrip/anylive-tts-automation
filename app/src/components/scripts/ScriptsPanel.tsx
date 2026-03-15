import React, { useState } from "react";
import { CSVPicker } from "../common/CSVPicker";
import { StatusBadge } from "../common/StatusBadge";
import { ProgressBar } from "../common/ProgressBar";
import { useAutomation } from "../../hooks/useAutomation";
import { useWebSocket } from "../../hooks/useWebSocket";
import type { CSVPreviewResponse } from "../../lib/types";

interface ScriptsPanelProps {
  client: string;
  sidecarUrl?: string | null;
}

export function ScriptsPanel({ client, sidecarUrl }: ScriptsPanelProps): React.ReactElement {
  const [csvPath, setCsvPath] = useState<string | null>(null);
  const [csvPreview, setCsvPreview] = useState<CSVPreviewResponse | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [options, setOptions] = useState({
    headless: true,
    dry_run: false,
    debug: false,
  });

  const automation = useAutomation();
  const ws = useWebSocket(automation.wsUrl);

  const processedCountRef = React.useRef(0);
  React.useEffect(() => {
    const newMessages = ws.messages.slice(processedCountRef.current);
    newMessages.forEach(automation.handleMessage);
    processedCountRef.current = ws.messages.length;
  }, [ws.messages.length]);

  const configPath = `configs/${client}/live.json`;

  const handleRun = async (): Promise<void> => {
    if (!csvPath || !sidecarUrl || automation.isRunning) return;
    await automation.startRun({
      sidecarUrl,
      endpoint: "/api/scripts/run",
      configPath,
      csvPath,
      options: { headless: options.headless, dry_run: options.dry_run, debug: options.debug },
      estimatedVersions: csvPreview?.estimated_versions || 0,
    });
  };

  const handleDelete = async (): Promise<void> => {
    if (!sidecarUrl || automation.isRunning) return;
    setShowDeleteConfirm(false);

    try {
      const resp = await fetch(`${sidecarUrl}/api/scripts/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config_path: configPath,
          options: { headless: options.headless, dry_run: options.dry_run },
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: "Delete failed" }));
        console.error("Delete failed:", err.detail);
      }
    } catch (err) {
      console.error("Delete request failed:", err);
    }
  };

  return (
    <div
      data-testid="scripts-panel"
      style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px", height: "100%", overflowY: "auto" }}
    >
      <h2 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
        📜 Script Automation
      </h2>

      {/* CSV Picker */}
      <CSVPicker
        onFileSelected={(path, preview) => { setCsvPath(path); setCsvPreview(preview); }}
        onClear={() => { setCsvPath(null); setCsvPreview(null); }}
        sidecarUrl={sidecarUrl}
        configPath={configPath}
      />

      {/* Options */}
      <div style={{ display: "flex", gap: "16px" }}>
        {[
          { key: "headless" as const, label: "Headless" },
          { key: "dry_run" as const, label: "Dry Run" },
          { key: "debug" as const, label: "Debug" },
        ].map(({ key, label }) => (
          <label key={key} style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", color: "var(--text-secondary)", cursor: "pointer" }}>
            <input
              data-testid={`scripts-option-${key}`}
              type="checkbox"
              checked={options[key]}
              onChange={() => setOptions((prev) => ({ ...prev, [key]: !prev[key] }))}
            />
            {label}
          </label>
        ))}
      </div>

      {/* Action buttons */}
      <div style={{ display: "flex", gap: "8px" }}>
        <button
          data-testid="scripts-run-button"
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
          {automation.isRunning ? "⟳ Running..." : "▶ Upload Scripts"}
        </button>

        <button
          data-testid="delete-scripts-button"
          onClick={() => setShowDeleteConfirm(true)}
          disabled={automation.isRunning || !sidecarUrl}
          style={{
            padding: "8px 16px",
            backgroundColor: "transparent",
            color: "var(--error)",
            border: "1px solid var(--error)",
            borderRadius: "6px",
            fontSize: "13px",
            cursor: automation.isRunning || !sidecarUrl ? "not-allowed" : "pointer",
            opacity: automation.isRunning || !sidecarUrl ? 0.5 : 1,
          }}
        >
          🗑 Delete All Scripts
        </button>
      </div>

      {/* Delete confirmation dialog */}
      {showDeleteConfirm && (
        <div
          data-testid="delete-confirm-dialog"
          style={{
            padding: "16px",
            backgroundColor: "var(--bg-elevated)",
            border: "1px solid var(--error)",
            borderRadius: "8px",
          }}
        >
          <p style={{ fontSize: "14px", color: "var(--text-primary)", marginBottom: "12px" }}>
            Are you sure you want to delete ALL scripts from all products? This cannot be undone.
          </p>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              data-testid="confirm-delete-button"
              onClick={handleDelete}
              style={{
                padding: "6px 16px",
                backgroundColor: "var(--error)",
                color: "white",
                border: "none",
                borderRadius: "6px",
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Yes, Delete All
            </button>
            <button
              data-testid="cancel-delete-button"
              onClick={() => setShowDeleteConfirm(false)}
              style={{
                padding: "6px 16px",
                backgroundColor: "transparent",
                color: "var(--text-secondary)",
                border: "1px solid var(--border-default)",
                borderRadius: "6px",
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Progress */}
      {(automation.isRunning || automation.progress.current > 0) && (
        <ProgressBar current={automation.progress.current} total={automation.progress.total} />
      )}

      {/* Version list */}
      {automation.versions.length > 0 && (
        <div data-testid="scripts-version-list" style={{ border: "1px solid var(--border-default)", borderRadius: "6px", overflow: "hidden" }}>
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
