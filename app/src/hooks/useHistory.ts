import { useState, useEffect, useCallback } from "react";
import type { HistoryRun } from "../lib/types";

interface HistoryState {
  runs: HistoryRun[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
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
      const data: HistoryRun[] = await resp.json();
      setRuns(data);
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
