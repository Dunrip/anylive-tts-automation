import React, { useEffect, useRef, useState } from "react";
import { CSVPicker } from "../common/CSVPicker";
import { StatusBadge } from "../common/StatusBadge";
import { ProgressBar } from "../common/ProgressBar";
import { useAutomation } from "../../hooks/useAutomation";
import { useWebSocket } from "../../hooks/useWebSocket";
import { useNotification } from "../../hooks/useNotification";
import { Button } from "@/components/ui/button";

import { cn } from "@/lib/utils";
import type { CSVPreviewResponse, WSMessage } from "../../lib/types";

interface TTSPanelProps {
  client: string;
  sidecarUrl?: string | null;
  baseUrl?: string;
  onBaseUrlChange?: (url: string) => void;
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
  download: boolean;
  replace: boolean;
  verify: boolean;
  flat_mode: boolean;
  no_save: boolean;
  start_version?: number;
  limit?: number;
  version_filter: string;
}

type BooleanOptionKey = "headless" | "dry_run" | "debug" | "download" | "replace" | "verify" | "flat_mode" | "no_save";

export function TTSPanel({
  client,
  sidecarUrl,
  baseUrl = "",
  onBaseUrlChange,
  onRunStart,
  onLogStateChange,
}: TTSPanelProps): React.ReactElement {
  const [csvPath, setCsvPath] = useState<string | null>(null);
  const [estimatedVersions, setEstimatedVersions] = useState(0);
  const [versionNames, setVersionNames] = useState<string[]>([]);
  const [options, setOptions] = useState<RunOptions>({
    headless: false,
    dry_run: false,
    debug: false,
    download: false,
    replace: false,
    verify: false,
    flat_mode: false,
    no_save: false,
    version_filter: "",
  });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [jobStartTime, setJobStartTime] = useState<number | undefined>();
  const processedCountRef = useRef(0);
  const hasConnectedRef = useRef(false);
  const wasRunningRef = useRef(false);
  const automation = useAutomation();
  const ws = useWebSocket(automation.wsUrl);
  const { sendJobNotification } = useNotification({ enabled: true });

  const configPath = `configs/${client}/tts.json`;

  const handleCsvSelected = (path: string, preview: CSVPreviewResponse): void => {
    setCsvPath(path);
    setEstimatedVersions(preview.estimated_versions);
    setVersionNames(preview.version_names || []);
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

  // Poll job status every 2s as fallback for WS progress
  useEffect(() => {
    if (!automation.isRunning || !automation.jobId || !sidecarUrl) return;
    const interval = setInterval(() => {
      automation.pollJobStatus(sidecarUrl, automation.jobId!);
    }, 2000);
    return () => clearInterval(interval);
  }, [automation.isRunning, automation.jobId, sidecarUrl, automation.pollJobStatus]);

  useEffect(() => {
    if (!onLogStateChange) {
      return;
    }
    // Merge WS messages with polled log messages (fallback when WS fails)
    const wsLogCount = ws.messages.filter((m) => m.type === "log").length;
    const messages = wsLogCount > 0 ? ws.messages : [...ws.messages, ...automation.polledMessages];
    onLogStateChange({
      messages,
      isConnected: ws.isConnected,
      clearMessages: ws.clearMessages,
    });
  }, [ws.messages, ws.isConnected, ws.clearMessages, onLogStateChange, automation.polledMessages]);

  useEffect(() => {
    if (automation.jobId) {
      onRunStart?.(automation.jobId);
    }
  }, [automation.jobId, onRunStart]);

  useEffect(() => {
    if (wasRunningRef.current && !automation.isRunning) {
      const successCount = automation.versions.filter((v) => v.status === "success").length;
      const failedCount = automation.versions.filter((v) => v.status === "failed").length;
      sendJobNotification("tts", {
        versionsTotal: automation.versions.length,
        versionsSuccess: successCount,
        versionsFailed: failedCount,
        error: automation.error ?? undefined,
      });
    }
    wasRunningRef.current = automation.isRunning;
  }, [automation.isRunning]);

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
        download: options.download,
        replace: options.replace,
        verify: options.verify,
        flat_mode: options.flat_mode,
        no_save: options.no_save,
        start_version: options.start_version,
        limit: options.limit,
        version_filter: options.version_filter || undefined,
      },
      estimatedVersions,
      versionNames,
    });
  };

  const toggleOption = (key: BooleanOptionKey): void => {
    setOptions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div
      data-testid="tts-panel"
      className="flex flex-col gap-4 p-4 h-full overflow-y-auto"
    >
      <h2 className="text-base font-semibold text-[var(--text-primary)] m-0">
        TTS Automation
      </h2>

      {/* Base URL */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-[var(--text-muted)] shrink-0">URL</label>
        <input
          data-testid="input-tts-base-url"
          type="text"
          value={baseUrl}
          onChange={(e) => onBaseUrlChange?.(e.target.value)}
          placeholder="https://app.anylive.jp/live-assets/XXX"
          className="flex-1 px-2.5 py-1.5 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md text-sm"
        />
      </div>

      <CSVPicker
        onFileSelected={handleCsvSelected}
        onClear={() => {
          setCsvPath(null);
          setEstimatedVersions(0);
          setVersionNames([]);
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
          className="px-2.5 py-2 rounded-md border border-[var(--error)] text-[var(--error)] text-xs bg-[color-mix(in_srgb,var(--error)_10%,transparent)]"
        >
          {automation.error}
        </div>
      ) : null}

      {automation.isRunning && automation.wsUrl && hasConnectedRef.current && !ws.isConnected ? (
        <div
          data-testid="connection-lost-banner"
          className="px-2.5 py-2 rounded-md border border-[var(--warning)] text-[var(--warning)] text-xs bg-[color-mix(in_srgb,var(--warning)_10%,transparent)]"
        >
          Connection lost
        </div>
      ) : null}

      <div className="flex items-center gap-3 px-3 py-2 rounded-md bg-[var(--bg-surface)] border border-[var(--border-default)]">
        <label className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] cursor-pointer font-medium">
          <input type="checkbox"
            data-testid="option-download"
            checked={options.download}
            onChange={() => toggleOption("download")}
           
          />
          Download Mode
        </label>
        <span className="text-xs text-[var(--text-muted)]">
          {options.download ? "Download files from existing versions" : "Create and fill new versions"}
        </span>
      </div>

      {options.download ? (
        <div className="flex flex-col gap-3">
          <div className="flex gap-4 flex-wrap">
            <label className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] cursor-pointer">
              <input type="checkbox" data-testid="option-headless"  checked={options.headless} onChange={() => toggleOption("headless")} />
              Headless
            </label>
            <label className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] cursor-pointer">
              <input type="checkbox" data-testid="option-replace"  checked={options.replace} onChange={() => toggleOption("replace")} />
              Replace existing
            </label>
            <label className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] cursor-pointer">
              <input type="checkbox" data-testid="option-verify"  checked={options.verify} onChange={() => toggleOption("verify")} />
              Verify after
            </label>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--text-muted)]">Version filter</label>
            <input
              data-testid="option-version-filter"
              type="text"
              placeholder="e.g. 1-5,8,10-12 (blank = all)"
              value={options.version_filter}
              onChange={(e) => setOptions((prev) => ({ ...prev, version_filter: e.target.value }))}
              className="w-full max-w-[250px] px-2 py-1 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md text-xs"
            />
          </div>
        </div>
      ) : (
        <>
          <div className="flex gap-4 flex-wrap">
            {[
              { key: "headless" as BooleanOptionKey, label: "Headless" },
              { key: "dry_run" as BooleanOptionKey, label: "Dry Run" },
              { key: "debug" as BooleanOptionKey, label: "Debug" },
            ].map(({ key, label }) => (
              <label
                key={key}
                className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] cursor-pointer"
              >
                <input type="checkbox"
                  data-testid={`option-${key}`}
                  checked={options[key]}
                  onChange={() => toggleOption(key)}
                 
                />
                {label}
              </label>
            ))}
          </div>

          <div>
            <button
              data-testid="toggle-advanced"
              onClick={() => setShowAdvanced((prev) => !prev)}
              className="flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors cursor-pointer bg-transparent border-none p-0"
            >
              <span className={cn("transition-transform text-xs", showAdvanced && "rotate-90")}>▶</span>
              Advanced (Optional)
            </button>
            {showAdvanced && (
              <div className="mt-2 flex flex-col gap-3">
                <div className="flex gap-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-[var(--text-muted)]">Start from version</label>
                    <input
                      data-testid="option-start-version"
                      type="number"
                      min={1}
                      placeholder="1"
                      value={options.start_version ?? ""}
                      onChange={(e) => setOptions((prev) => ({
                        ...prev,
                        start_version: e.target.value ? parseInt(e.target.value, 10) : undefined,
                      }))}
                      className="w-[100px] px-2 py-1 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md text-xs"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-[var(--text-muted)]">Limit versions</label>
                    <input
                      data-testid="option-limit"
                      type="number"
                      min={1}
                      placeholder="All"
                      value={options.limit ?? ""}
                      onChange={(e) => setOptions((prev) => ({
                        ...prev,
                        limit: e.target.value ? parseInt(e.target.value, 10) : undefined,
                      }))}
                      className="w-[100px] px-2 py-1 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md text-xs"
                    />
                  </div>
                </div>
                <div className="flex gap-4">
                  <label className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] cursor-pointer">
                    <input type="checkbox" data-testid="option-flat_mode"  checked={options.flat_mode} onChange={() => toggleOption("flat_mode")} />
                    Flat mode
                  </label>
                  <label className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] cursor-pointer">
                    <input type="checkbox" data-testid="option-no_save"  checked={options.no_save} onChange={() => toggleOption("no_save")} />
                    No save
                  </label>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      <div className="flex gap-2">
        <Button
          data-testid="run-button"
          onClick={handleRun}
          disabled={!csvPath || automation.isRunning || !sidecarUrl}
          title={!sidecarUrl ? "Sidecar not connected" : !csvPath ? "Select a CSV file first" : ""}
          variant={automation.isRunning ? "secondary" : "default"}
        >
          {automation.isRunning ? "Running..." : options.download ? "Download" : "Run"}
        </Button>
        {automation.isRunning && (
          <Button
            data-testid="cancel-button"
            variant="outline"
            onClick={() => { if (sidecarUrl) void automation.cancelJob(sidecarUrl); }}
          >
            Cancel
          </Button>
        )}
      </div>

      {(automation.isRunning || automation.progress.current > 0) && (
        <ProgressBar
          current={automation.progress.current}
          total={automation.progress.total}
          startTime={jobStartTime}
        />
      )}

      {automation.versions.length > 0 && (
        <div>
          <p className="text-xs text-[var(--text-muted)] mb-2">
            {automation.versions.length} versions
          </p>
          <div
            data-testid="version-list"
            className="border border-[var(--border-default)] rounded-md overflow-hidden"
          >
            {automation.versions.map((v, i) => (
              <div
                key={i}
                data-testid={`version-item-${i}`}
                className={cn(
                  "flex items-center justify-between px-3 py-2",
                  i < automation.versions.length - 1 && "border-b border-[var(--border-default)]",
                  i % 2 !== 0 && "bg-[var(--bg-surface)]"
                )}
              >
                <span className="text-sm text-[var(--text-primary)]">{v.name}</span>
                <div className="flex items-center gap-2">
                  <StatusBadge status={v.status} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
