import React, { useState } from "react";

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
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.7)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        style={{
          backgroundColor: "var(--bg-elevated)",
          border: "1px solid var(--border-default)",
          borderRadius: "12px",
          padding: "32px",
          maxWidth: "400px",
          width: "90%",
        }}
      >
        <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "12px" }}>
          Browser Setup Required
        </h2>
        <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "24px" }}>
          Chromium browser is required for automation. Install it now to get started.
        </p>

        {message && (
          <p
            data-testid="setup-message"
            style={{
              fontSize: "13px",
              color: status === "error" ? "var(--error)" : status === "done" ? "var(--success)" : "var(--text-secondary)",
              marginBottom: "16px",
            }}
          >
            {message}
          </p>
        )}

        <div style={{ display: "flex", gap: "8px" }}>
          <button
            data-testid="install-button"
            onClick={handleInstall}
            disabled={installing || status === "done"}
            style={{
              padding: "10px 24px",
              backgroundColor: "var(--accent)",
              color: "white",
              border: "none",
              borderRadius: "6px",
              fontSize: "14px",
              fontWeight: 600,
              cursor: installing || status === "done" ? "not-allowed" : "pointer",
              opacity: installing || status === "done" ? 0.7 : 1,
            }}
          >
            {installing ? "Installing..." : status === "done" ? "Done ✓" : "Install Chromium"}
          </button>
        </div>
      </div>
    </div>
  );
}
