import React, { useState } from "react";
import { CSVPicker } from "../common/CSVPicker";
import { StatusBadge } from "../common/StatusBadge";
import { ProgressBar } from "../common/ProgressBar";
import { useAutomation } from "../../hooks/useAutomation";
import { useWebSocket } from "../../hooks/useWebSocket";
import { useAutomationPanel } from "../../hooks/useAutomationPanel";
import type { CSVPreviewResponse, WSMessage } from "../../lib/types";
import { Button } from "@/components/ui/button";
import { OptionSwitch } from "@/components/common/OptionSwitch";
import { cn } from "@/lib/utils";

interface FAQPanelProps {
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

export function FAQPanel({ client, sidecarUrl, baseUrl = "", onBaseUrlChange, onLogStateChange }: FAQPanelProps): React.ReactElement {
  const [csvPath, setCsvPath] = useState<string | null>(null);
  const [csvPreview, setCsvPreview] = useState<CSVPreviewResponse | null>(null);
  const [audioDir, setAudioDir] = useState<string>("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [options, setOptions] = useState<{
    headless: boolean;
    dry_run: boolean;
    debug: boolean;
    start_product?: number;
    limit?: number;
  }>({
    headless: false,
    dry_run: false,
    debug: false,
  });

  const automation = useAutomation();
  const ws = useWebSocket(automation.wsUrl);

  useAutomationPanel({
    ws,
    automation,
    sidecarUrl,
    onLogStateChange,
  });

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
        start_product: options.start_product,
        limit: options.limit,
      },
      estimatedVersions: csvPreview?.estimated_versions || 0,
    });
  };

  return (
    <div
      data-testid="faq-panel"
      className="flex flex-col gap-4 p-4 h-full overflow-y-auto"
    >
      <h2 className="text-base font-semibold text-[var(--text-primary)] m-0">
        FAQ Automation
      </h2>

       {/* Base URL (shared with Scripts) */}
       <div className="flex items-center gap-2">
         <label htmlFor="faq-base-url" className="text-xs text-[var(--text-muted)] shrink-0">URL</label>
         <input
           id="faq-base-url"
           data-testid="input-faq-base-url"
           type="text"
           value={baseUrl}
           onChange={(e) => onBaseUrlChange?.(e.target.value)}
           placeholder="https://live.app.anylive.jp/live/SESSION_ID"
           className="flex-1 px-2.5 py-1.5 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md text-sm"
         />
       </div>

      {/* CSV Picker */}
      <CSVPicker
        onFileSelected={handleCsvSelected}
        onClear={() => { setCsvPath(null); setCsvPreview(null); }}
        sidecarUrl={sidecarUrl}
        configPath={configPath}
        automationType="faq"
      />

       {/* Audio directory input */}
       <div>
         <label htmlFor="faq-audio-dir" className="text-xs text-[var(--text-secondary)] block mb-1">
           Audio Directory (optional)
         </label>
         <input
           id="faq-audio-dir"
           data-testid="audio-dir-input"
           type="text"
           value={audioDir}
           onChange={(e) => setAudioDir(e.target.value)}
           placeholder="downloads/"
           className="w-full px-2.5 py-1.5 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md text-sm box-border"
         />
      </div>

      {/* Options */}
      <div className="flex gap-4">
        <OptionSwitch
          id="faq-option-headless"
          testId="faq-option-headless"
          checked={options.headless}
          onCheckedChange={(checked) => setOptions((prev) => ({ ...prev, headless: checked }))}
          label="Headless"
          description="Run browser in background without visible window"
        />
        <OptionSwitch
          id="faq-option-dry_run"
          testId="faq-option-dry_run"
          checked={options.dry_run}
          onCheckedChange={(checked) => setOptions((prev) => ({ ...prev, dry_run: checked }))}
          label="Dry Run"
          description="Fill forms without generating speech or saving"
        />
        <OptionSwitch
          id="faq-option-debug"
          testId="faq-option-debug"
          checked={options.debug}
          onCheckedChange={(checked) => setOptions((prev) => ({ ...prev, debug: checked }))}
          label="Debug"
          description="Slow motion with pause-on-error for troubleshooting"
        />
      </div>

      {/* Advanced options */}
       <div>
         <button
           type="button"
           data-testid="faq-toggle-advanced"
           onClick={() => setShowAdvanced((prev) => !prev)}
           className="flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors cursor-pointer bg-transparent border-none p-0"
         >
           <span className={cn("transition-transform text-xs", showAdvanced && "rotate-90")}>▶</span>
           Advanced (Optional)
         </button>
        {showAdvanced && (
          <div className="mt-2 flex gap-4">
             <div className="flex flex-col gap-1">
               <label htmlFor="faq-start-product" className="text-xs text-[var(--text-muted)]">Start from product</label>
               <input
                 id="faq-start-product"
                 data-testid="faq-option-start-product"
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
               <label htmlFor="faq-limit-products" className="text-xs text-[var(--text-muted)]">Limit products</label>
               <input
                 id="faq-limit-products"
                 data-testid="faq-option-limit"
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
        )}
      </div>

      {/* Run button */}
      <div className="flex gap-2">
        <Button
          data-testid="faq-run-button"
          onClick={handleRun}
          disabled={!csvPath || automation.isRunning || !sidecarUrl}
          variant={automation.isRunning ? "secondary" : "success"}
        >
          {automation.isRunning ? "Running..." : "Run"}
        </Button>
      </div>

      {/* Error banner */}
      {automation.error && (
        <div data-testid="faq-error" className="px-3 py-2 bg-[color-mix(in_srgb,var(--error)_10%,transparent)] border border-[var(--error)] rounded-md text-sm text-[var(--error)]">
          {automation.error}
        </div>
      )}

      {/* Progress */}
      {(automation.isRunning || automation.progress.current > 0) && (
        <ProgressBar current={automation.progress.current} total={automation.progress.total} />
      )}

      {/* Product list */}
      {automation.versions.length > 0 && (
        <div data-testid="product-list" className="border border-[var(--border-default)] rounded-md overflow-hidden">
           {automation.versions.map((v, i) => (
             <div
               key={v.name}
              className={cn(
                "flex items-center justify-between px-3 py-2",
                i < automation.versions.length - 1 && "border-b border-[var(--border-default)]",
                i % 2 !== 0 && "bg-[var(--bg-surface)]"
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
