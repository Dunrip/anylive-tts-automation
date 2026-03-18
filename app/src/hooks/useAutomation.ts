import { useCallback, useRef, useState } from "react";
import type { JobStatus, ProgressMessage, StatusMessage, WSMessage } from "../lib/types";

interface VersionStatus {
  name: string;
  status: JobStatus;
}

interface AutomationState {
  isRunning: boolean;
  jobId: string | null;
  progress: { current: number; total: number };
  versions: VersionStatus[];
  error: string | null;
  wsUrl: string | null;
}

interface RunParams {
  sidecarUrl: string;
  endpoint: string;
  configPath: string;
  csvPath: string;
  options: Record<string, unknown>;
  estimatedVersions?: number;
  versionNames?: string[];
}

function isProgressMessage(msg: WSMessage): msg is ProgressMessage {
  return msg.type === "progress";
}

function isStatusMessage(msg: WSMessage): msg is StatusMessage {
  return msg.type === "status";
}

function toWebSocketUrl(sidecarUrl: string, jobId: string): string {
  const wsBase = sidecarUrl.startsWith("https://")
    ? sidecarUrl.replace("https://", "wss://")
    : sidecarUrl.replace("http://", "ws://");
  return `${wsBase}/api/jobs/${jobId}/ws`;
}

export function useAutomation() {
  const [state, setState] = useState<AutomationState>({
    isRunning: false,
    jobId: null,
    progress: { current: 0, total: 0 },
    versions: [],
    error: null,
    wsUrl: null,
  });

  const abortRef = useRef<boolean>(false);

  const startRun = useCallback(async (params: RunParams): Promise<void> => {
    const {
      sidecarUrl,
      endpoint,
      configPath,
      csvPath,
      options,
      estimatedVersions = 0,
      versionNames = [],
    } = params;

    abortRef.current = false;

    setState((prev) => ({
      ...prev,
      isRunning: true,
      jobId: null,
      progress: { current: 0, total: estimatedVersions },
      versions: Array.from({ length: estimatedVersions }, (_, i) => ({
        name: versionNames[i] || `Version ${i + 1}`,
        status: "pending" as JobStatus,
      })),
      error: null,
      wsUrl: null,
    }));

    try {
      const response = await fetch(`${sidecarUrl}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config_path: configPath,
          csv_path: csvPath,
          options,
        }),
      });

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(
          typeof errorPayload.detail === "string"
            ? errorPayload.detail
            : `HTTP ${response.status}`
        );
      }

      const payload = (await response.json()) as { job_id: string };

      if (abortRef.current) {
        return;
      }

      setState((prev) => ({
        ...prev,
        jobId: payload.job_id,
        wsUrl: toWebSocketUrl(sidecarUrl, payload.job_id),
      }));
    } catch (error) {
      if (abortRef.current) {
        return;
      }

      setState((prev) => ({
        ...prev,
        isRunning: false,
        error: error instanceof Error ? error.message : "Failed to start job",
      }));
    }
  }, []);

  const handleMessage = useCallback((msg: WSMessage): void => {
    if (isProgressMessage(msg)) {
      setState((prev) => ({
        ...prev,
        progress: { current: msg.current, total: msg.total },
        versions: prev.versions.map((version, index) => ({
          ...version,
          status:
            index < msg.current - 1
              ? "success"
              : index === msg.current - 1
                ? "running"
                : version.status,
          name: index === msg.current - 1 ? msg.version_name : version.name,
        })),
      }));
      return;
    }

    if (!isStatusMessage(msg)) {
      return;
    }

    if (msg.status === "success") {
      setState((prev) => ({
        ...prev,
        isRunning: false,
        versions: prev.versions.map((version) => ({
          ...version,
          status: version.status === "failed" ? "failed" : "success",
        })),
      }));
    } else if (msg.status === "failed" || msg.status === "cancelled") {
      setState((prev) => ({
        ...prev,
        isRunning: false,
        versions: prev.versions.map((version) => ({
          ...version,
          status: version.status === "running" ? msg.status : version.status,
        })),
      }));
    }
  }, []);

  // Poll job status as fallback when WS doesn't deliver progress
  const pollJobStatus = useCallback(async (sidecarUrl: string, jobId: string): Promise<void> => {
    try {
      const resp = await fetch(`${sidecarUrl}/api/jobs/${jobId}`);
      if (!resp.ok) return;
      const data = (await resp.json()) as {
        status: string;
        progress: { current: number; total: number };
        error?: string | null;
      };

      setState((prev) => {
        const newProgress = data.progress;
        // Only update if progress actually changed
        if (newProgress.current === prev.progress.current && newProgress.total === prev.progress.total) {
          return prev;
        }
        return {
          ...prev,
          progress: newProgress,
          versions: prev.versions.map((version, index) => ({
            ...version,
            status:
              index < newProgress.current
                ? "success"
                : index === newProgress.current
                  ? "running"
                  : version.status,
          })),
        };
      });

      // Check if job finished
      if (data.status === "success") {
        setState((prev) => ({
          ...prev,
          isRunning: false,
          error: data.error || null,
          progress: data.progress,
          versions: prev.versions.map((version) => ({
            ...version,
            status: version.status === "failed" ? "failed" : "success",
          })),
        }));
      } else if (data.status === "failed" || data.status === "cancelled") {
        setState((prev) => ({
          ...prev,
          isRunning: false,
          error: data.error || null,
          progress: data.progress,
          versions: prev.versions.map((version) => ({
            ...version,
            status: version.status === "running" ? data.status as "failed" | "cancelled" : version.status,
          })),
        }));
      }
    } catch {
      // Silently ignore poll errors
    }
  }, []);

  const reset = useCallback((): void => {
    abortRef.current = true;
    setState({
      isRunning: false,
      jobId: null,
      progress: { current: 0, total: 0 },
      versions: [],
      error: null,
      wsUrl: null,
    });
  }, []);

  const cancelJob = useCallback(async (sidecarUrl: string): Promise<void> => {
    if (!state.jobId) return;
    try {
      await fetch(`${sidecarUrl}/api/jobs/${state.jobId}/cancel`, { method: "POST" });
    } catch {
      // silently ignore cancel errors
    }
  }, [state.jobId]);

  return {
    ...state,
    startRun,
    handleMessage,
    pollJobStatus,
    reset,
    cancelJob,
  };
}
