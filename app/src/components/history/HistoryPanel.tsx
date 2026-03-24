import React, { useEffect, useState } from "react";
import { StatusBadge } from "../common/StatusBadge";
import { useHistory } from "../../hooks/useHistory";
import type { AutomationType, JobStatus } from "../../lib/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface HistoryPanelProps {
  sidecarUrl?: string | null;
  isActive?: boolean;
}

type FilterType = "all" | AutomationType;

const TYPE_LABELS: Record<string, string> = {
  all: "All",
  tts: "TTS",
  faq: "FAQ",
  script: "Script",
};

function formatDuration(startedAt: string, finishedAt?: string): string {
  if (!finishedAt) return "—";
  const start = new Date(startedAt).getTime();
  const end = new Date(finishedAt).getTime();
  const ms = end - start;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function HistoryPanel({ sidecarUrl, isActive }: HistoryPanelProps): React.ReactElement {
  const { runs, loading, error, refresh } = useHistory(sidecarUrl);
  const [filter, setFilter] = useState<FilterType>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Auto-refresh when panel becomes active
  useEffect(() => {
    if (isActive) refresh();
  }, [isActive]); // eslint-disable-line react-hooks/exhaustive-deps

  const filteredRuns = filter === "all"
    ? runs
    : runs.filter((r) => r.automation_type === filter);

  const successRate = runs.length > 0
    ? Math.round((runs.filter((r) => r.status === "success").length / runs.length) * 100)
    : 0;

  return (
    <div
      data-testid="history-panel"
      className="flex flex-col gap-4 w-full"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-primary)] m-0">
          History
        </h2>
        <Button
          data-testid="refresh-button"
          onClick={refresh}
          variant="outline"
          size="xs"
        >
          ↻ Refresh
        </Button>
      </div>

      {/* Stats */}
      <div className="flex gap-4">
        {[
          { label: "Total Runs", value: runs.length },
          { label: "Success Rate", value: `${successRate}%` },
          { label: "Last Run", value: runs[0] ? formatDate(runs[0].started_at) : "—" },
        ].map(({ label, value }) => (
          <div
            key={label}
            className="flex-1 px-4 py-3 bg-[var(--bg-surface)] rounded-md border border-[var(--border-default)]"
          >
            <p className="text-xs text-[var(--text-muted)] m-0 mb-1">{label}</p>
            <p className="text-lg font-semibold text-[var(--text-primary)] m-0">{value}</p>
          </div>
        ))}
      </div>

      {/* Type filter tabs */}
      <div className="flex gap-1 border-b border-[var(--border-default)] pb-2">
        {(["all", "tts", "faq", "script"] as FilterType[]).map((type) => (
          <Button
            key={type}
            data-testid={`filter-${type}`}
            onClick={() => setFilter(type)}
            variant="ghost"
            size="xs"
            className={cn(
              filter === type && "bg-primary text-primary-foreground font-semibold"
            )}
          >
            {TYPE_LABELS[type]}
          </Button>
        ))}
      </div>

      {/* Loading / Error */}
      {loading && <p className="text-[var(--text-muted)] text-sm">Loading...</p>}
      {error && (
        <p className="text-[var(--text-muted)] text-sm">
          {sidecarUrl ? error : "Sidecar not connected. Start the sidecar to view run history."}
        </p>
      )}

      {/* History table */}
      {!loading && filteredRuns.length === 0 ? (
        <p data-testid="empty-history" className="text-[var(--text-muted)] text-sm">
          No runs yet. Start an automation to see history here.
        </p>
      ) : (
        <table className="w-full border-collapse border border-[var(--border-default)] rounded-md text-sm">
          <thead>
            <tr className="bg-[var(--bg-elevated)] text-xs text-[var(--text-muted)] font-semibold text-left">
              <th className="px-4 py-2 border-b border-[var(--border-default)]">Date</th>
              <th className="px-4 py-2 border-b border-[var(--border-default)]">CSV</th>
              <th className="px-4 py-2 border-b border-[var(--border-default)]">Type</th>
              <th className="px-4 py-2 border-b border-[var(--border-default)]">Status</th>
              <th className="px-4 py-2 border-b border-[var(--border-default)]">Duration</th>
              <th className="px-4 py-2 border-b border-[var(--border-default)]">Versions</th>
            </tr>
          </thead>
          <tbody>
            {filteredRuns.map((run) => (
              <React.Fragment key={run.id}>
                <tr
                  data-testid={`history-row-${run.id}`}
                  onClick={() => setExpandedId(expandedId === run.id ? null : run.id)}
                  className={cn(
                    "cursor-pointer transition-colors",
                    expandedId === run.id ? "bg-[var(--bg-surface)]" : "hover:bg-[var(--bg-hover)]"
                  )}
                >
                  <td className="px-4 py-2.5 border-b border-[var(--border-default)] text-[var(--text-secondary)]">{formatDate(run.started_at)}</td>
                  <td className="px-4 py-2.5 border-b border-[var(--border-default)] text-[var(--text-muted)] text-xs max-w-[180px] overflow-hidden text-ellipsis whitespace-nowrap" title={run.csv_file}>{run.csv_file ?? "—"}</td>
                  <td className="px-4 py-2.5 border-b border-[var(--border-default)] text-[var(--text-primary)] uppercase text-xs">{run.automation_type}</td>
                  <td className="px-4 py-2.5 border-b border-[var(--border-default)]"><StatusBadge status={run.status as JobStatus} size="sm" /></td>
                  <td className="px-4 py-2.5 border-b border-[var(--border-default)] text-[var(--text-muted)] text-xs">{formatDuration(run.started_at, run.finished_at)}</td>
                  <td className="px-4 py-2.5 border-b border-[var(--border-default)] text-[var(--text-secondary)] text-xs tabular-nums">{run.versions_success}/{run.versions_total}</td>
                </tr>
                {expandedId === run.id && (
                  <tr data-testid={`history-detail-${run.id}`}>
                    <td colSpan={6} className="px-4 py-3 bg-[var(--bg-elevated)] border-b border-[var(--border-default)] text-xs text-[var(--text-secondary)]">
                      <p className="m-0 mb-1">Job ID: <span className="text-[var(--text-primary)] font-mono">{run.id}</span></p>
                      <p className="m-0 mb-1">Client: {run.client}</p>
                      {run.error && <p className="m-0 text-[var(--error)]">Error: {run.error}</p>}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
