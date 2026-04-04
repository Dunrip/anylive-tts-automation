import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

const SESSION_EXPIRED_PATTERNS = [
  "session expired",
  "session invalid",
  "run setup again",
  "no session file",
  "redirected to login",
];

function isSessionExpiredError(error: string): boolean {
  const lower = error.toLowerCase();
  return SESSION_EXPIRED_PATTERNS.some((p) => lower.includes(p));
}

interface ErrorBannerProps {
  error: string;
  sidecarUrl?: string | null;
  testId?: string;
  onSessionRefreshed?: () => void;
  client?: string;
  platform?: "tts" | "live";
}

export function ErrorBanner({ error, sidecarUrl, testId, onSessionRefreshed, client, platform = "tts" }: ErrorBannerProps): React.ReactElement {
  const [loginStatus, setLoginStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [loginMessage, setLoginMessage] = useState<string | null>(null);

  const sessionExpired = isSessionExpiredError(error);

  const handleRelogin = async (): Promise<void> => {
    if (!sidecarUrl) return;
    setLoginStatus("loading");
    setLoginMessage(null);
    try {
      const resp = await fetch(`${sidecarUrl}/api/session/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform: platform || "tts", client }),
      });
      if (!resp.ok) throw new Error(`Login failed: ${resp.status}`);
      const data = await resp.json();
      if (data.status === "ok") {
        setLoginStatus("done");
        setLoginMessage(`Logged in${data.display_name ? ` as ${data.display_name}` : ""}. You can retry now.`);
        onSessionRefreshed?.();
      } else if (data.status === "timeout") {
        setLoginStatus("error");
        setLoginMessage("Login timed out. Try again.");
      } else {
        setLoginStatus("error");
        setLoginMessage(data.error || "Login failed.");
      }
    } catch {
      setLoginStatus("error");
      setLoginMessage("Could not connect to sidecar.");
    }
  };

  if (loginStatus === "done" && loginMessage) {
    return (
      <div
        data-testid={testId}
        className="px-3 py-2 rounded-md border border-[var(--success)] text-[var(--success)] text-xs bg-[color-mix(in_srgb,var(--success)_10%,transparent)]"
      >
        {loginMessage}
      </div>
    );
  }

  return (
    <div
      data-testid={testId}
      className="px-3 py-2 rounded-md border border-[var(--error)] text-[var(--error)] text-xs bg-[color-mix(in_srgb,var(--error)_10%,transparent)]"
    >
      <div className="flex items-center justify-between gap-2">
        <span>{sessionExpired ? "Session expired — please re-login to continue." : error}</span>
        {sessionExpired && sidecarUrl && loginStatus !== "done" && (
          <Button
            data-testid="relogin-error-button"
            variant="success"
            size="xs"
            onClick={handleRelogin}
            disabled={loginStatus === "loading"}
            className="shrink-0"
          >
            {loginStatus === "loading" ? (
              <><Loader2 className="size-3 animate-spin" /> Logging in...</>
            ) : loginStatus === "error" ? "Retry" : "Re-login"}
          </Button>
        )}
      </div>
      {loginMessage && loginStatus === "error" && (
        <p className="mt-1 text-xs opacity-80">{loginMessage}</p>
      )}
    </div>
  );
}
