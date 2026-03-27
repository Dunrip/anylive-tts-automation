import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

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

  return state;
}
