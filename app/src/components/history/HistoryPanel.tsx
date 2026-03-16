import React, { useState } from "react";
import { StatusBadge } from "../common/StatusBadge";
import { useHistory } from "../../hooks/useHistory";
import type { AutomationType, JobStatus } from "../../lib/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface HistoryPanelProps {
  sidecarUrl?: string | null;
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

export function HistoryPanel({ sidecarUrl }: HistoryPanelProps): React.ReactElement {
  const { runs, loading, error, refresh } = useHistory(sidecarUrl);
  const [filter, setFilter] = useState<FilterType>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filteredRuns = filter === "all"
    ? runs
    : runs.filter((r) => r.automation_type === filter);

  const successRate = runs.length > 0
    ? Math.round((runs.filter((r) => r.status === "success").length / runs.length) * 100)
    : 0;

  return (
    <div
      data-testid="history-panel"
      className="flex flex-col gap-4 p-4 h-full overflow-y-auto"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[var(--text-primary)] m-0">
          📊 History
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
            className="flex-1 px-3.5 py-2.5 bg-[var(--bg-surface)] rounded-md border border-[var(--border-default)]"
          >
            <p className="text-[11px] text-[var(--text-muted)] m-0 mb-1">{label}</p>
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
      {loading && <p className="text-[var(--text-muted)] text-[13px]">Loading...</p>}
      {error && <p className="text-[var(--error)] text-[13px]">{error}</p>}

      {/* History table */}
      {!loading && filteredRuns.length === 0 ? (
        <p data-testid="empty-history" className="text-[var(--text-muted)] text-[13px]">
          No runs yet. Start an automation to see history here.
        </p>
      ) : (
        <div className="border border-[var(--border-default)] rounded-md overflow-hidden">
          {/* Table header */}
          <div
            className="grid grid-cols-[1fr_80px_80px_100px_80px] px-3 py-2 bg-[var(--bg-elevated)] border-b border-[var(--border-default)] text-[11px] text-[var(--text-muted)] font-semibold"
          >
            <span>Date</span>
            <span>Type</span>
            <span>Status</span>
            <span>Duration</span>
            <span>Versions</span>
          </div>

          {/* Table rows */}
          {filteredRuns.map((run) => (
            <React.Fragment key={run.id}>
              <div
                data-testid={`history-row-${run.id}`}
                onClick={() => setExpandedId(expandedId === run.id ? null : run.id)}
                className={cn(
                  "grid grid-cols-[1fr_80px_80px_100px_80px] px-3 py-2.5 border-b border-[var(--border-default)] cursor-pointer text-[13px]",
                  expandedId === run.id ? "bg-[var(--bg-surface)]" : "bg-transparent"
                )}
              >
                <span className="text-[var(--text-secondary)]">{formatDate(run.started_at)}</span>
                <span className="text-[var(--text-primary)] uppercase text-[11px]">
                  {run.automation_type}
                </span>
                <StatusBadge status={run.status as JobStatus} size="sm" />
                <span className="text-[var(--text-muted)] text-[12px]">
                  {formatDuration(run.started_at, run.finished_at)}
                </span>
                <span className="text-[var(--text-secondary)] text-[12px]">
                  {run.versions_success}/{run.versions_total}
                </span>
              </div>

              {/* Expanded detail */}
              {expandedId === run.id && (
                <div
                  data-testid={`history-detail-${run.id}`}
                  className="px-4 py-3 bg-[var(--bg-elevated)] border-b border-[var(--border-default)] text-[12px] text-[var(--text-secondary)]"
                >
                  <p className="m-0 mb-1">Job ID: <span className="text-[var(--text-primary)] font-mono">{run.id}</span></p>
                  <p className="m-0 mb-1">Client: {run.client}</p>
                  {run.error && (
                    <p className="m-0 text-[var(--error)]">Error: {run.error}</p>
                  )}
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      )}
    </div>
  );
}
