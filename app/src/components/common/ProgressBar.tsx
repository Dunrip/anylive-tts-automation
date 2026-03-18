import React, { useEffect, useState } from "react";
import { Progress } from "@/components/ui/progress";

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

  // current = "about to process item N" (1-indexed), so completed = current - 1
  // Exception: when current >= total, all items have been emitted (last one processing or done)
  const completedItems = current >= total ? total : Math.max(0, current - 1);
  const percentage = total > 0 ? Math.round((completedItems / total) * 100) : 0;

  // Estimate remaining time based on completed items
  let estimatedRemaining: string | null = null;
  if (completedItems > 0 && completedItems < total && elapsed > 0) {
    const msPerItem = elapsed / completedItems;
    const remainingItems = total - completedItems;
    estimatedRemaining = formatDuration(msPerItem * remainingItems);
  }

  return (
    <div data-testid="progress-bar" className="flex flex-col gap-1">
      {/* Progress track */}
      <Progress value={percentage} className="h-1" data-testid="progress-fill" />

      {/* Progress text */}
      <div className="flex justify-between items-center">
        <span
          data-testid="progress-text"
          className="text-xs text-[var(--text-secondary)]"
        >
          {completedItems}/{total} versions ({percentage}%)
        </span>
        {estimatedRemaining && (
          <span
            data-testid="progress-eta"
            className="text-xs text-[var(--text-muted)]"
          >
            ~{estimatedRemaining} remaining
          </span>
        )}
        {elapsed > 0 && (
          <span
            data-testid="progress-elapsed"
            className="text-xs text-[var(--text-muted)]"
          >
            {formatDuration(elapsed)} elapsed
          </span>
        )}
      </div>
    </div>
  );
}
