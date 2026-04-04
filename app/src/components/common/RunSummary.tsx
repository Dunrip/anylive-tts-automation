import React from "react";
import type { JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { FolderOpen } from "lucide-react";
import { isTauri } from "@tauri-apps/api/core";
import { openFolder } from "@/lib/openFolder";

interface VersionEntry {
  name: string;
  status: JobStatus | string;
}

interface RunSummaryProps {
  versions: VersionEntry[];
  startTime?: number;
  csvFileName?: string;
  downloadDir?: string;
  onDismiss: () => void;
}

function formatDuration(startTime: number): string {
  const elapsedMs = Date.now() - startTime;
  const totalSeconds = Math.max(0, Math.floor(elapsedMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

function truncateFileName(name: string, maxLen = 24): string {
  if (name.length <= maxLen) return name;
  const ext = name.lastIndexOf(".");
  if (ext > 0 && name.length - ext <= 5) {
    const extPart = name.slice(ext);
    const base = name.slice(0, maxLen - extPart.length - 1);
    return `${base}…${extPart}`;
  }
  return `${name.slice(0, maxLen - 1)}…`;
}

export function RunSummary({
  versions,
  startTime,
  csvFileName,
  downloadDir,
  onDismiss,
}: RunSummaryProps): React.ReactElement | null {
  const nonPending = versions.filter((v) => v.status !== "pending");
  if (versions.length === 0 || nonPending.length === 0) return null;
  const isInTauri = isTauri();

  const successCount = versions.filter((v) => v.status === "success").length;
  const failedCount = versions.filter((v) => v.status === "failed").length;
  const duration = startTime != null ? formatDuration(startTime) : null;
  const fileName = csvFileName ? truncateFileName(csvFileName) : null;

  return (
    <div
      data-testid="run-summary"
      className="flex items-center gap-3 flex-wrap px-3 py-2 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-default)] text-xs"
    >
      <span
        data-testid="run-summary-success"
        className={cn(
          "flex items-center gap-1 font-medium",
          successCount > 0 ? "text-[var(--success)]" : "text-[var(--text-muted)]"
        )}
      >
        ✓ {successCount} success
      </span>

      <span
        data-testid="run-summary-failed"
        className={cn(
          "flex items-center gap-1 font-medium",
          failedCount > 0 ? "text-[var(--error)]" : "text-[var(--text-muted)]"
        )}
      >
        ✗ {failedCount} failed
      </span>

      <span className="text-[var(--text-secondary)]">
        / {versions.length} total
      </span>

      {duration != null && (
        <span className="text-[var(--text-secondary)] flex items-center gap-1">
          ⏱ {duration}
        </span>
      )}

      {fileName != null && (
        <span className="text-[var(--text-secondary)] flex items-center gap-1" title={csvFileName}>
          📄 {fileName}
        </span>
      )}

      <div className="flex-1" />

      {downloadDir != null && isInTauri && (
        <button
          type="button"
          data-testid="open-downloads-button"
          onClick={() => { void openFolder(downloadDir); }}
          aria-label="Open downloads folder"
          className="flex items-center gap-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors cursor-pointer bg-transparent border-none p-0 leading-none"
        >
          <FolderOpen className="w-3.5 h-3.5" />
          <span>Open folder</span>
        </button>
      )}

      <button
        type="button"
        data-testid="run-summary-dismiss"
        onClick={onDismiss}
        aria-label="Dismiss summary"
        className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors cursor-pointer bg-transparent border-none p-0 leading-none"
      >
        ×
      </button>
    </div>
  );
}
