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
    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 30;

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
        } catch {
          attempts += 1;
          await new Promise((resolve) => setTimeout(resolve, 500));
        }
      }

      if (!cancelled) {
        setState((prev) => ({
          ...prev,
          error: "Sidecar failed to start within 15 seconds",
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
