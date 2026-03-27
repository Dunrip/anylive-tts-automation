import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SetupWizardProps {
  sidecarUrl: string;
  onComplete: () => void;
}

export function SetupWizard({ sidecarUrl, onComplete }: SetupWizardProps): React.ReactElement {
  const [installing, setInstalling] = useState(false);
  const [status, setStatus] = useState<"idle" | "installing" | "done" | "error">("idle");
  const [message, setMessage] = useState<string>("");
  const completeTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const handleInstall = async (): Promise<void> => {
    setInstalling(true);
    setStatus("installing");
    setMessage("Installing Chromium browser...");

    try {
      const resp = await fetch(`${sidecarUrl}/api/setup/install-chromium`, {
        method: "POST",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      if (data.status === "installed" || data.status === "already_installed") {
        setStatus("done");
        setMessage("Chromium installed successfully!");
        completeTimeoutRef.current = setTimeout(onComplete, 1500);
      } else {
        setStatus("error");
        setMessage(data.error || "Installation failed");
      }
    } catch {
      setStatus("error");
      setMessage("Could not connect to sidecar");
    } finally {
      setInstalling(false);
    }
  };

  useEffect(() => {
    return () => {
      if (completeTimeoutRef.current) clearTimeout(completeTimeoutRef.current);
    };
  }, []);

  return (
    <div
      data-testid="setup-wizard"
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/70"
    >
      <div className="w-[90%] max-w-[400px] rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-8">
        <h2 className="mb-3 text-[length:var(--text-xl)] font-semibold text-[var(--text-primary)]">
          Browser Setup Required
        </h2>
        <p className="mb-6 text-sm text-[var(--text-secondary)]">
          Chromium browser is required for automation. Install it now to get started.
        </p>

        {message && (
          <p
            data-testid="setup-message"
            className={cn(
              "mb-4 text-sm",
              status === "error" ? "text-[var(--error)]" : status === "done" ? "text-[var(--success)]" : "text-[var(--text-secondary)]"
            )}
          >
            {message}
          </p>
        )}

        <div className="flex gap-2">
          <Button
            data-testid="install-button"
            onClick={handleInstall}
            disabled={installing || status === "done"}
          >
            {installing ? "Installing..." : status === "done" ? "Done" : "Install Chromium"}
          </Button>
        </div>
      </div>
    </div>
  );
}
