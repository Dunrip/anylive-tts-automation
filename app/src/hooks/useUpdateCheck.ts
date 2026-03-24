import { useEffect } from "react";
import { toast } from "sonner";

export function useUpdateCheck(): void {
  useEffect(() => {
    // Only run update check in production
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
                try {
                  await update.downloadAndInstall();
                  await relaunch();
                } catch {
                  // Silently ignore installation errors
                }
              },
            },
            duration: Infinity,
          });
        }
      } catch {
        // Silently ignore errors (offline, endpoint unavailable, etc.)
      }
    };

    checkForUpdates();
  }, []);
}
