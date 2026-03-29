import { useEffect, useState } from "react";
import { toast } from "sonner";

export interface UpdateCheckState {
  installError: string | null;
  clearInstallError: () => void;
}

export function useUpdateCheck(): UpdateCheckState {
  const [installError, setInstallError] = useState<string | null>(null);

  useEffect(() => {
    if (import.meta.env.DEV) {
      return;
    }

    const checkForUpdates = async (): Promise<void> => {
      try {
        const { check } = await import("@tauri-apps/plugin-updater");
        const { relaunch } = await import("@tauri-apps/plugin-process");

        const update = await check();

        if (update) {
          toast.info(`Update available: v${update.version}. Click to install.`, {
            action: {
              label: "Install",
              onClick: async () => {
                setInstallError(null);
                try {
                  await update.downloadAndInstall();
                  await relaunch();
                } catch (err: unknown) {
                  setInstallError(
                    err instanceof Error ? err.message : "Update installation failed"
                  );
                }
              },
            },
            duration: Infinity,
          });
        }
      } catch {
        // Offline or update endpoint unavailable — update check is non-critical
      }
    };

    checkForUpdates();
  }, []);

  return { installError, clearInstallError: () => setInstallError(null) };
}
