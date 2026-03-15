import React from "react";
import type { JobStatus } from "../../lib/types";

interface StatusBadgeProps {
  status: JobStatus;
  size?: "sm" | "md";
}

const STATUS_CONFIG: Record<JobStatus, { icon: string; label: string; color: string }> = {
  pending: { icon: "○", label: "Pending", color: "var(--text-muted)" },
  running: { icon: "⟳", label: "Running", color: "var(--running)" },
  success: { icon: "✓", label: "Success", color: "var(--success)" },
  failed: { icon: "✗", label: "Failed", color: "var(--error)" },
  cancelled: { icon: "⊘", label: "Cancelled", color: "var(--text-muted)" },
};

export function StatusBadge({ status, size = "md" }: StatusBadgeProps): React.ReactElement {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  const fontSize = size === "sm" ? "11px" : "12px";

  return (
    <span
      data-testid={`status-badge-${status}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        fontSize,
        color: config.color,
        fontWeight: status === "running" ? 600 : 400,
      }}
    >
      <span
        style={{
          animation: status === "running" ? "spin 1s linear infinite" : "none",
          display: "inline-block",
        }}
      >
        {config.icon}
      </span>
      <span>{config.label}</span>
    </span>
  );
}
