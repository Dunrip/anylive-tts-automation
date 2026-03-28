import { useEffect, useState } from "react";
import { getVersion } from "@tauri-apps/api/app";
import { isTauri } from "@tauri-apps/api/core";

export function useAppVersion(): string | undefined {
  const [version, setVersion] = useState<string | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;

    const fetchVersion = async (): Promise<void> => {
      // Guard: only attempt getVersion() inside Tauri shell
      if (!isTauri()) {
        if (!cancelled) {
          setVersion("dev");
        }
        return;
      }

      try {
        const appVersion = await getVersion();
        if (!cancelled) {
          setVersion(appVersion);
        }
      } catch {
        // Silently ignore rejection; version remains undefined
        // This handles cases where getVersion() fails outside Tauri context
      }
    };

    void fetchVersion();

    return () => {
      cancelled = true;
    };
  }, []);

  return version;
}
