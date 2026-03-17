import React from "react";
import { cn } from "@/lib/utils";
import type { JobStatus } from "../../lib/types";

interface StatusBadgeProps {
  status: JobStatus;
  size?: "sm" | "md";
}

const STATUS_CONFIG: Record<JobStatus, { icon: string; label: string; colorClass: string }> = {
  pending: { icon: "○", label: "Pending", colorClass: "text-[var(--text-muted)]" },
  running: { icon: "⟳", label: "Running", colorClass: "text-[var(--running)]" },
  success: { icon: "✓", label: "Success", colorClass: "text-[var(--success)]" },
  failed: { icon: "✗", label: "Failed", colorClass: "text-[var(--error)]" },
  cancelled: { icon: "⊘", label: "Cancelled", colorClass: "text-[var(--text-muted)]" },
};

export function StatusBadge({ status, size = "md" }: StatusBadgeProps): React.ReactElement {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  const textSizeClass = size === "sm" ? "text-[length:var(--text-xs)]" : "text-xs";

  return (
    <span
      data-testid={`status-badge-${status}`}
      className={cn(
        "inline-flex items-center gap-1",
        textSizeClass,
        config.colorClass,
        status === "running" && "font-semibold"
      )}
    >
      <span className={cn("inline-block", status === "running" && "animate-spin")}>
        {config.icon}
      </span>
      <span>{config.label}</span>
    </span>
  );
}
