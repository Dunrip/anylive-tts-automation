import React, { useState } from "react";
import { StatusBadge } from "../common/StatusBadge";
import { useHistory } from "../../hooks/useHistory";
import type { AutomationType, JobStatus } from "../../lib/types";

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
      style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px", height: "100%", overflowY: "auto" }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h2 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
          📊 History
        </h2>
        <button
          data-testid="refresh-button"
          onClick={refresh}
          style={{
            padding: "4px 12px",
            backgroundColor: "transparent",
            color: "var(--text-secondary)",
            border: "1px solid var(--border-default)",
            borderRadius: "4px",
            fontSize: "12px",
            cursor: "pointer",
          }}
        >
          ↻ Refresh
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: "flex", gap: "16px" }}>
        {[
          { label: "Total Runs", value: runs.length },
          { label: "Success Rate", value: `${successRate}%` },
          { label: "Last Run", value: runs[0] ? formatDate(runs[0].started_at) : "—" },
        ].map(({ label, value }) => (
          <div
            key={label}
            style={{
              flex: 1,
              padding: "10px 14px",
              backgroundColor: "var(--bg-surface)",
              borderRadius: "6px",
              border: "1px solid var(--border-default)",
            }}
          >
            <p style={{ fontSize: "11px", color: "var(--text-muted)", margin: "0 0 4px" }}>{label}</p>
            <p style={{ fontSize: "18px", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>{value}</p>
          </div>
        ))}
      </div>

      {/* Type filter tabs */}
      <div style={{ display: "flex", gap: "4px", borderBottom: "1px solid var(--border-default)", paddingBottom: "8px" }}>
        {(["all", "tts", "faq", "script"] as FilterType[]).map((type) => (
          <button
            key={type}
            data-testid={`filter-${type}`}
            onClick={() => setFilter(type)}
            style={{
              padding: "4px 12px",
              backgroundColor: filter === type ? "var(--accent)" : "transparent",
              color: filter === type ? "white" : "var(--text-secondary)",
              border: "none",
              borderRadius: "4px",
              fontSize: "12px",
              cursor: "pointer",
              fontWeight: filter === type ? 600 : 400,
            }}
          >
            {TYPE_LABELS[type]}
          </button>
        ))}
      </div>

      {/* Loading / Error */}
      {loading && <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>Loading...</p>}
      {error && <p style={{ color: "var(--error)", fontSize: "13px" }}>{error}</p>}

      {/* History table */}
      {!loading && filteredRuns.length === 0 ? (
        <p data-testid="empty-history" style={{ color: "var(--text-muted)", fontSize: "13px" }}>
          No runs yet. Start an automation to see history here.
        </p>
      ) : (
        <div style={{ border: "1px solid var(--border-default)", borderRadius: "6px", overflow: "hidden" }}>
          {/* Table header */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 80px 80px 100px 80px",
              padding: "8px 12px",
              backgroundColor: "var(--bg-elevated)",
              borderBottom: "1px solid var(--border-default)",
              fontSize: "11px",
              color: "var(--text-muted)",
              fontWeight: 600,
            }}
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
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 80px 80px 100px 80px",
                  padding: "10px 12px",
                  borderBottom: "1px solid var(--border-default)",
                  cursor: "pointer",
                  backgroundColor: expandedId === run.id ? "var(--bg-surface)" : "transparent",
                  fontSize: "13px",
                }}
              >
                <span style={{ color: "var(--text-secondary)" }}>{formatDate(run.started_at)}</span>
                <span style={{ color: "var(--text-primary)", textTransform: "uppercase", fontSize: "11px" }}>
                  {run.automation_type}
                </span>
                <StatusBadge status={run.status as JobStatus} size="sm" />
                <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>
                  {formatDuration(run.started_at, run.finished_at)}
                </span>
                <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>
                  {run.versions_success}/{run.versions_total}
                </span>
              </div>

              {/* Expanded detail */}
              {expandedId === run.id && (
                <div
                  data-testid={`history-detail-${run.id}`}
                  style={{
                    padding: "12px 16px",
                    backgroundColor: "var(--bg-elevated)",
                    borderBottom: "1px solid var(--border-default)",
                    fontSize: "12px",
                    color: "var(--text-secondary)",
                  }}
                >
                  <p style={{ margin: "0 0 4px" }}>Job ID: <span style={{ color: "var(--text-primary)", fontFamily: "monospace" }}>{run.id}</span></p>
                  <p style={{ margin: "0 0 4px" }}>Client: {run.client}</p>
                  {run.error && (
                    <p style={{ margin: "0", color: "var(--error)" }}>Error: {run.error}</p>
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
