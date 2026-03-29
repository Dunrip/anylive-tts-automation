import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

const HEALTH_CHECK_INTERVAL_MS = 10_000;
const HEALTH_CHECK_TIMEOUT_MS = 5_000;
const HEALTH_CHECK_FAILURE_THRESHOLD = 3;

interface SidecarState {
  port: number | null;
  sidecarUrl: string | null;
  isReady: boolean;
  error: string | null;
}

export function useSidecar(): SidecarState {
  const [state, setState] = useState<SidecarState>({
    port: null,
    sidecarUrl: null,
    isReady: false,
    error: null,
  });

  useEffect(() => {
    // E2E / dev-mode: bypass Tauri invoke when env var is set
    const envUrl = import.meta.env.VITE_SIDECAR_URL as string | undefined;
    if (envUrl) {
      setState({ port: null, sidecarUrl: envUrl, isReady: true, error: null });
      return;
    }

    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 60;
    let lastError: string = "";

    const pollForPort = async (): Promise<void> => {
      while (!cancelled && attempts < maxAttempts) {
        try {
          const port = await invoke<number>("get_sidecar_port");
          if (!cancelled) {
            setState({
              port,
              sidecarUrl: `http://127.0.0.1:${port}`,
              isReady: true,
              error: null,
            });
          }
          return;
        } catch (err) {
          lastError = String(err);
          attempts += 1;
          await new Promise((resolve) => setTimeout(resolve, 500));
        }
      }

      if (!cancelled) {
        setState((prev) => ({
          ...prev,
          error: `Sidecar failed to start after 30s: ${lastError}`,
        }));
      }
    };

    void pollForPort();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!state.sidecarUrl) return;

    const url = state.sidecarUrl;
    let consecutiveFailures = 0;

    const intervalId = setInterval(() => {
      void (async () => {
        const controller = new AbortController();
        const abortTimeoutId = setTimeout(
          () => controller.abort(),
          HEALTH_CHECK_TIMEOUT_MS
        );

        try {
          const response = await fetch(`${url}/health`, {
            signal: controller.signal,
          });
          clearTimeout(abortTimeoutId);

          if (!response.ok) {
            throw new Error(`Health check returned ${response.status}`);
          }

          consecutiveFailures = 0;
          setState((prev) => {
            if (!prev.isReady) {
              return { ...prev, isReady: true, error: null };
            }
            return prev;
          });
        } catch (err) {
          clearTimeout(abortTimeoutId);
          consecutiveFailures += 1;

          if (consecutiveFailures >= HEALTH_CHECK_FAILURE_THRESHOLD) {
            setState((prev) => ({
              ...prev,
              isReady: false,
              error: `Sidecar health check failed: ${String(err)}`,
            }));
          }
        }
      })();
    }, HEALTH_CHECK_INTERVAL_MS);

    return () => {
      clearInterval(intervalId);
    };
  }, [state.sidecarUrl]);

  return state;
}
