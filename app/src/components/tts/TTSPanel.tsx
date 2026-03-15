import React, { useState } from "react";
import { CSVPicker } from "../common/CSVPicker";
import { StatusBadge } from "../common/StatusBadge";
import { ProgressBar } from "../common/ProgressBar";
import type { JobStatus, CSVPreviewResponse } from "../../lib/types";

interface VersionItem {
  name: string;
  status: JobStatus;
  duration?: number; // ms
}

interface TTSPanelProps {
  client: string;
  sidecarUrl?: string | null;
  onRunStart?: (jobId: string) => void;
}

interface RunOptions {
  headless: boolean;
  dry_run: boolean;
  debug: boolean;
  start_version?: number;
  limit?: number;
}

export function TTSPanel({ client, sidecarUrl, onRunStart }: TTSPanelProps): React.ReactElement {
  const [csvPath, setCsvPath] = useState<string | null>(null);
  const [options, setOptions] = useState<RunOptions>({
    headless: true,
    dry_run: false,
    debug: false,
  });
  const [versions, setVersions] = useState<VersionItem[]>([]);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [isRunning, setIsRunning] = useState(false);
  const [jobStartTime, setJobStartTime] = useState<number | undefined>();

  const configPath = `configs/${client}/tts.json`;

  const handleCsvSelected = (path: string, preview: CSVPreviewResponse): void => {
    setCsvPath(path);
    // Initialize version list from preview
    setVersions(
      Array.from({ length: preview.estimated_versions }, (_, i) => ({
        name: `Version ${i + 1}`,
        status: "pending" as JobStatus,
      }))
    );
  };

  const handleRun = async (): Promise<void> => {
    if (!csvPath || !sidecarUrl || isRunning) return;

    setIsRunning(true);
    setJobStartTime(Date.now());
    setProgress({ current: 0, total: versions.length });

    try {
      const resp = await fetch(`${sidecarUrl}/api/tts/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config_path: configPath,
          csv_path: csvPath,
          options: {
            headless: options.headless,
            dry_run: options.dry_run,
            debug: options.debug,
            start_version: options.start_version,
            limit: options.limit,
          },
        }),
      });

      if (resp.ok) {
        const { job_id } = await resp.json();
        onRunStart?.(job_id);
      }
    } catch {
      setIsRunning(false);
    }
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
        onClear={() => { setCsvPath(null); setVersions([]); }}
        sidecarUrl={sidecarUrl}
        configPath={configPath}
      />

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
          disabled={!csvPath || isRunning || !sidecarUrl}
          title={!sidecarUrl ? "Sidecar not connected" : !csvPath ? "Select a CSV file first" : ""}
          style={{
            padding: "8px 24px",
            backgroundColor: isRunning ? "var(--bg-elevated)" : "var(--accent)",
            color: "white",
            border: "none",
            borderRadius: "6px",
            fontSize: "14px",
            fontWeight: 600,
            cursor: !csvPath || isRunning || !sidecarUrl ? "not-allowed" : "pointer",
            opacity: !csvPath || isRunning || !sidecarUrl ? 0.6 : 1,
          }}
        >
          {isRunning ? "⟳ Running..." : "▶ Run"}
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
      {(isRunning || progress.current > 0) && (
        <ProgressBar
          current={progress.current}
          total={progress.total}
          startTime={jobStartTime}
        />
      )}

      {/* Version list */}
      {versions.length > 0 && (
        <div>
          <p style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "8px" }}>
            {versions.length} versions
          </p>
          <div
            data-testid="version-list"
            style={{
              border: "1px solid var(--border-default)",
              borderRadius: "6px",
              overflow: "hidden",
            }}
          >
            {versions.map((v, i) => (
              <div
                key={i}
                data-testid={`version-item-${i}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  borderBottom: i < versions.length - 1 ? "1px solid var(--border-default)" : "none",
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
