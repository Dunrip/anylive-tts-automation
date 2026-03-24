import { useCallback } from "react";

interface NotificationOptions {
  enabled: boolean;
}

interface JobResult {
  versionsTotal: number;
  versionsSuccess: number;
  versionsFailed: number;
  error?: string;
}

function formatNotificationMessage(automationType: string, result: JobResult): { title: string; body: string } {
  const { versionsTotal, versionsSuccess, versionsFailed, error } = result;

  if (error) {
    return {
      title: `${automationType.toUpperCase()} Automation Failed`,
      body: error,
    };
  }

  if (versionsFailed === 0) {
    return {
      title: `${automationType.toUpperCase()} Automation Complete`,
      body: `${versionsTotal}/${versionsTotal} versions succeeded`,
    };
  }

  return {
    title: `${automationType.toUpperCase()} Automation Complete`,
    body: `${versionsSuccess}/${versionsTotal} succeeded, ${versionsFailed} failed`,
  };
}

export function useNotification({ enabled }: NotificationOptions) {
  const sendJobNotification = useCallback(
    async (automationType: string, result: JobResult): Promise<void> => {
      if (!enabled) return;

      const { title, body } = formatNotificationMessage(automationType, result);

      try {
        const { sendNotification, isPermissionGranted, requestPermission } =
          await import("@tauri-apps/plugin-notification");

        let permissionGranted = await isPermissionGranted();
        if (!permissionGranted) {
          const permission = await requestPermission();
          permissionGranted = permission === "granted";
        }

        if (permissionGranted) {
          await sendNotification({ title, body });
        }
      } catch {
        // Notifications not available (e.g., in test environment)
      }
    },
    [enabled]
  );

  return { sendJobNotification, formatNotificationMessage };
}

export { formatNotificationMessage };
