import React, { useEffect, useState } from "react";

interface ProgressBarProps {
  current: number;
  total: number;
  startTime?: number; // Unix timestamp ms when job started
}

function formatDuration(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}m ${rem}s`;
}

export function ProgressBar({ current, total, startTime }: ProgressBarProps): React.ReactElement {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startTime || current === 0) return;
    const interval = setInterval(() => {
      setElapsed(Date.now() - startTime);
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime, current]);

  const percentage = total > 0 ? Math.round((current / total) * 100) : 0;

  // Estimate remaining time
  let estimatedRemaining: string | null = null;
  if (current > 0 && total > current && elapsed > 0) {
    const msPerItem = elapsed / current;
    const remaining = msPerItem * (total - current);
    estimatedRemaining = formatDuration(remaining);
  }

  return (
    <div data-testid="progress-bar" style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
      {/* Progress track */}
      <div
        style={{
          height: "4px",
          backgroundColor: "var(--bg-elevated)",
          borderRadius: "2px",
          overflow: "hidden",
        }}
      >
        <div
          data-testid="progress-fill"
          style={{
            height: "100%",
            width: `${percentage}%`,
            backgroundColor: "var(--accent)",
            borderRadius: "2px",
            transition: "width 0.3s ease",
          }}
        />
      </div>

      {/* Progress text */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span
          data-testid="progress-text"
          style={{ fontSize: "12px", color: "var(--text-secondary)" }}
        >
          {current}/{total} versions ({percentage}%)
        </span>
        {estimatedRemaining && (
          <span
            data-testid="progress-eta"
            style={{ fontSize: "11px", color: "var(--text-muted)" }}
          >
            ~{estimatedRemaining} remaining
          </span>
        )}
        {elapsed > 0 && (
          <span
            data-testid="progress-elapsed"
            style={{ fontSize: "11px", color: "var(--text-muted)" }}
          >
            {formatDuration(elapsed)} elapsed
          </span>
        )}
      </div>
    </div>
  );
}
