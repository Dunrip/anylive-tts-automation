import { useState, useEffect, useCallback } from "react";
import type { HistoryRun } from "../lib/types";

interface HistoryState {
  runs: HistoryRun[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

function isHistoryRunArray(data: unknown): data is HistoryRun[] {
  return (
    Array.isArray(data) &&
    data.every(
      (item) =>
        item != null &&
        typeof item === "object" &&
        typeof (item as Record<string, unknown>).id === "string" &&
        typeof (item as Record<string, unknown>).status === "string" &&
        typeof (item as Record<string, unknown>).started_at === "string"
    )
  );
}

export function useHistory(sidecarUrl: string | null | undefined): HistoryState {
  const [runs, setRuns] = useState<HistoryRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async (): Promise<void> => {
    if (!sidecarUrl) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${sidecarUrl}/api/history`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const rawData: unknown = await resp.json();
      if (!isHistoryRunArray(rawData)) throw new Error("Invalid history response shape");
      setRuns(rawData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, [sidecarUrl]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return { runs, loading, error, refresh: fetchHistory };
}
