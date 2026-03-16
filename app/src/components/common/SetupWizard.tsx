import React, { useState } from "react";
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

  const handleInstall = async (): Promise<void> => {
    setInstalling(true);
    setStatus("installing");
    setMessage("Installing Chromium browser...");

    try {
      const resp = await fetch(`${sidecarUrl}/api/setup/install-chromium`, {
        method: "POST",
      });
      const data = await resp.json();

      if (data.status === "installed" || data.status === "already_installed") {
        setStatus("done");
        setMessage("Chromium installed successfully!");
        setTimeout(onComplete, 1500);
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

  return (
    <div
      data-testid="setup-wizard"
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/70"
    >
      <div className="w-[90%] max-w-[400px] rounded-xl border border-border-default bg-bg-elevated p-8">
        <h2 className="mb-3 text-[18px] font-semibold text-text-primary">
          Browser Setup Required
        </h2>
        <p className="mb-6 text-sm text-text-secondary">
          Chromium browser is required for automation. Install it now to get started.
        </p>

        {message && (
          <p
            data-testid="setup-message"
            className={cn(
              "mb-4 text-[13px]",
              status === "error" ? "text-error" : status === "done" ? "text-success" : "text-text-secondary"
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
            className={cn(
              "border-none bg-accent px-6 py-2.5 text-sm font-semibold text-white",
              (installing || status === "done") ? "cursor-not-allowed opacity-70" : "cursor-pointer"
            )}
          >
            {installing ? "Installing..." : status === "done" ? "Done ✓" : "Install Chromium"}
          </Button>
        </div>
      </div>
    </div>
  );
}
