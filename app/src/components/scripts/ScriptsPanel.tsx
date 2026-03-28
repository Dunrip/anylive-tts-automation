import React, { useState } from "react";
import { CSVPicker } from "../common/CSVPicker";
import { StatusBadge } from "../common/StatusBadge";
import { ProgressBar } from "../common/ProgressBar";
import { useAutomation } from "../../hooks/useAutomation";
import { useWebSocket } from "../../hooks/useWebSocket";
import type { CSVPreviewResponse, WSMessage } from "../../lib/types";
import { Button } from "@/components/ui/button";

import { cn } from "@/lib/utils";

interface ScriptsPanelProps {
  client: string;
  sidecarUrl?: string | null;
  baseUrl?: string;
  onBaseUrlChange?: (url: string) => void;
  onLogStateChange?: (logState: {
    messages: WSMessage[];
    isConnected: boolean;
    clearMessages: () => void;
  }) => void;
}

export function ScriptsPanel({ client, sidecarUrl, baseUrl = "", onBaseUrlChange, onLogStateChange }: ScriptsPanelProps): React.ReactElement {
  const [csvPath, setCsvPath] = useState<string | null>(null);
  const [csvPreview, setCsvPreview] = useState<CSVPreviewResponse | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [showReplaceConfirm, setShowReplaceConfirm] = useState(false);
  const [replaceError, setReplaceError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [options, setOptions] = useState<{
    headless: boolean;
    dry_run: boolean;
    debug: boolean;
    start_product?: number;
    limit?: number;
    audio_dir: string;
  }>({
    headless: false,
    dry_run: false,
    debug: false,
    audio_dir: "",
  });

  const automation = useAutomation();
  const ws = useWebSocket(automation.wsUrl);

  const processedCountRef = React.useRef(0);
  React.useEffect(() => {
    const newMessages = ws.messages.slice(processedCountRef.current);
    newMessages.forEach(automation.handleMessage);
    processedCountRef.current = ws.messages.length;
  }, [ws.messages, automation.handleMessage]);

  // Poll job status every 2s as fallback for WS progress
  React.useEffect(() => {
    if (!automation.isRunning || !automation.jobId || !sidecarUrl) return;
    const interval = setInterval(() => {
      automation.pollJobStatus(sidecarUrl, automation.jobId!);
    }, 2000);
    return () => clearInterval(interval);
  }, [automation.isRunning, automation.jobId, sidecarUrl, automation.pollJobStatus]);

  React.useEffect(() => {
    if (!onLogStateChange) return;
    onLogStateChange({
      messages: ws.messages,
      isConnected: ws.isConnected,
      clearMessages: ws.clearMessages,
    });
  }, [ws.messages, ws.isConnected, ws.clearMessages, onLogStateChange]);

  const configPath = `configs/${client}/live.json`;

  const handleRun = async (): Promise<void> => {
    if (!csvPath || !sidecarUrl || automation.isRunning) return;
    await automation.startRun({
      sidecarUrl,
      endpoint: "/api/scripts/run",
      configPath,
      csvPath,
      options: {
        headless: options.headless,
        dry_run: options.dry_run,
        debug: options.debug,
        start_product: options.start_product,
        limit: options.limit,
        audio_dir: options.audio_dir || undefined,
      },
      estimatedVersions: csvPreview?.estimated_versions || 0,
    });
  };

  const handleDelete = async (): Promise<void> => {
    if (!sidecarUrl || automation.isRunning) return;
    setShowDeleteConfirm(false);
    setDeleteError(null);

    try {
      const resp = await fetch(`${sidecarUrl}/api/scripts/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config_path: configPath,
          options: {
            headless: options.headless,
            dry_run: options.dry_run,
            start_product: options.start_product,
            limit: options.limit,
          },
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: "Delete failed" }));
        setDeleteError(err.detail || "Delete failed");
      }
    } catch {
      setDeleteError("Could not connect to sidecar");
    }
  };

  const handleReplace = async (): Promise<void> => {
    if (!sidecarUrl || automation.isRunning) return;
    setShowReplaceConfirm(false);
    setReplaceError(null);

    try {
      await automation.startRun({
        sidecarUrl,
        endpoint: "/api/scripts/replace",
        configPath,
        csvPath: "",
        options: {
          headless: options.headless,
          dry_run: options.dry_run,
          start_product: options.start_product,
          limit: options.limit,
        },
      });
    } catch {
      setReplaceError("Could not connect to sidecar");
    }
  };

  return (
    <div
      data-testid="scripts-panel"
      className="flex flex-col gap-4 p-4 h-full overflow-y-auto"
    >
      <h2 className="text-base font-semibold text-[var(--text-primary)] m-0">
        Script Automation
      </h2>

       {/* Base URL (shared with FAQ) */}
       <div className="flex items-center gap-2">
         <label htmlFor="scripts-base-url" className="text-xs text-[var(--text-muted)] shrink-0">URL</label>
         <input
           id="scripts-base-url"
           data-testid="input-scripts-base-url"
           type="text"
           value={baseUrl}
           onChange={(e) => onBaseUrlChange?.(e.target.value)}
           placeholder="https://live.app.anylive.jp/live/SESSION_ID"
           className="flex-1 px-2.5 py-1.5 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md text-sm"
         />
       </div>

      {/* CSV Picker */}
      <CSVPicker
        onFileSelected={(path, preview) => { setCsvPath(path); setCsvPreview(preview); }}
        onClear={() => { setCsvPath(null); setCsvPreview(null); }}
        sidecarUrl={sidecarUrl}
        configPath={configPath}
        automationType="script"
      />

      {/* Options */}
      <div className="flex gap-4">
        {[
          { key: "headless" as const, label: "Headless" },
          { key: "dry_run" as const, label: "Dry Run" },
          { key: "debug" as const, label: "Debug" },
        ].map(({ key, label }) => (
          <label key={key} className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] cursor-pointer">
            <input type="checkbox"
              data-testid={`scripts-option-${key}`}
              checked={options[key] as boolean}
              onChange={() => setOptions((prev) => ({ ...prev, [key]: !prev[key] as boolean }))}
             
            />
            {label}
          </label>
        ))}
      </div>

       <div>
         <button
           type="button"
           data-testid="scripts-toggle-advanced"
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
                 <label htmlFor="scripts-start-product" className="text-xs text-[var(--text-muted)]">Start from product</label>
                 <input
                   id="scripts-start-product"
                   data-testid="scripts-option-start-product"
                   type="number"
                   min={1}
                   placeholder="1"
                   value={options.start_product ?? ""}
                   onChange={(e) => setOptions((prev) => ({
                     ...prev,
                     start_product: e.target.value ? parseInt(e.target.value, 10) : undefined,
                   }))}
                   className="w-[100px] px-2 py-1 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md text-xs"
                 />
              </div>
               <div className="flex flex-col gap-1">
                 <label htmlFor="scripts-limit-products" className="text-xs text-[var(--text-muted)]">Limit products</label>
                 <input
                   id="scripts-limit-products"
                   data-testid="scripts-option-limit"
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
             <div className="flex flex-col gap-1">
               <label htmlFor="scripts-audio-dir" className="text-xs text-[var(--text-muted)]">Audio directory</label>
               <input
                 id="scripts-audio-dir"
                 data-testid="scripts-option-audio-dir"
                 type="text"
                 placeholder="downloads/"
                 value={options.audio_dir}
                 onChange={(e) => setOptions((prev) => ({ ...prev, audio_dir: e.target.value }))}
                 className="w-full max-w-[300px] px-2 py-1 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md text-xs"
               />
            </div>
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <Button
          data-testid="scripts-run-button"
          onClick={handleRun}
          disabled={!csvPath || automation.isRunning || !sidecarUrl}
          variant={automation.isRunning ? "secondary" : "success"}
        >
          {automation.isRunning ? "Running..." : "Upload Scripts"}
        </Button>

        <Button
          data-testid="replace-products-button"
          onClick={() => setShowReplaceConfirm(true)}
          disabled={automation.isRunning || !sidecarUrl}
          variant="outline"
        >
          Replace Products
        </Button>

        <Button
          data-testid="delete-scripts-button"
          onClick={() => setShowDeleteConfirm(true)}
          disabled={automation.isRunning || !sidecarUrl}
          className="bg-[var(--error)] text-white hover:opacity-90"
        >
          Delete All Scripts
        </Button>
      </div>

      {deleteError && (
        <div className="px-3 py-2 bg-[color-mix(in_srgb,var(--error)_10%,transparent)] border border-[var(--error)] rounded-md text-sm text-[var(--error)]">
          {deleteError}
        </div>
      )}
      {replaceError && (
        <div className="px-3 py-2 bg-[color-mix(in_srgb,var(--error)_10%,transparent)] border border-[var(--error)] rounded-md text-sm text-[var(--error)]">
          {replaceError}
        </div>
      )}

      {/* Replace confirmation dialog */}
      {showReplaceConfirm && (
        <div
          data-testid="replace-confirm-dialog"
          className="p-4 bg-[var(--bg-elevated)] border border-[var(--warning)] rounded-lg"
        >
          <p className="text-sm text-[var(--text-primary)] mb-3">
            Are you sure you want to replace all products? This will delete existing products and upload new ones. This cannot be undone.
          </p>
          <div className="flex gap-2">
            <Button
              data-testid="confirm-replace-button"
              variant="destructive"
              onClick={handleReplace}
            >
              Yes, Replace All
            </Button>
            <Button
              data-testid="cancel-replace-button"
              variant="outline"
              onClick={() => setShowReplaceConfirm(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Delete confirmation dialog */}
      {showDeleteConfirm && (
        <div
          data-testid="delete-confirm-dialog"
          className="p-4 bg-[var(--bg-elevated)] border border-[var(--error)] rounded-lg"
        >
          <p className="text-sm text-[var(--text-primary)] mb-3">
            Are you sure you want to delete ALL scripts from all products? This cannot be undone.
          </p>
          <div className="flex gap-2">
            <Button
              data-testid="confirm-delete-button"
              variant="destructive"
              onClick={handleDelete}
            >
              Yes, Delete All
            </Button>
            <Button
              data-testid="cancel-delete-button"
              variant="outline"
              onClick={() => setShowDeleteConfirm(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Progress */}
      {(automation.isRunning || automation.progress.current > 0) && (
        <ProgressBar current={automation.progress.current} total={automation.progress.total} />
      )}

      {/* Version list */}
      {automation.versions.length > 0 && (
        <div data-testid="scripts-version-list" className="border border-[var(--border-default)] rounded-md overflow-hidden">
           {automation.versions.map((v, i) => (
             <div
               key={v.name}
              className={cn(
                "flex items-center justify-between px-3 py-2",
                i < automation.versions.length - 1 && "border-b border-[var(--border-default)]",
                i % 2 === 0 ? "bg-transparent" : "bg-[var(--bg-surface)]"
              )}
            >
              <span className="text-sm text-[var(--text-primary)]">{v.name}</span>
              <StatusBadge status={v.status} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
