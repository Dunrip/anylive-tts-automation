import React, { useState, useEffect } from "react";
import { Sidebar } from "./components/layout/Sidebar";
import { MainContent } from "./components/layout/MainContent";
import { Titlebar } from "./components/layout/Titlebar";
import { SetupWizard } from "./components/common/SetupWizard";
import { useSidecar } from "./hooks/useSidecar";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { PanelType } from "./lib/navigation";

function App(): React.ReactElement {
  const [activePanel, setActivePanel] = useState<PanelType>("tts");
  const [selectedClient, setSelectedClient] = useState<string>("default");
  const [chromiumReady, setChromiumReady] = useState(true);
  const sidecar = useSidecar();
  const sessionValid = sidecar.isReady;

  useKeyboardShortcuts({
    onPanelChange: setActivePanel,
  });

  const [clients, setClients] = useState<string[]>(["default"]);

  useEffect(() => {
    const loadClientsFromRust = async (): Promise<void> => {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const list = await invoke<string[]>("list_client_configs");
        if (Array.isArray(list) && list.length > 0) setClients(list);
      } catch {
        // Rust command not available (e.g. running in browser dev mode)
      }
    };
    loadClientsFromRust();
  }, []);

  useEffect(() => {
    if (!sidecar.isReady || !sidecar.sidecarUrl) return;

    fetch(`${sidecar.sidecarUrl}/api/setup/status`)
      .then((r) => r.json())
      .then((data) => {
        if (data.chromium_installed === false) setChromiumReady(false);
      })
      .catch(() => {});

    fetch(`${sidecar.sidecarUrl}/api/configs`)
      .then((r) => r.json())
      .then((data: string[]) => {
        if (Array.isArray(data) && data.length > 0) setClients(data);
      })
      .catch(() => {});
  }, [sidecar.isReady, sidecar.sidecarUrl]);

  const handleRelogin = async (): Promise<void> => {
    try {
      const { WebviewWindow } = await import("@tauri-apps/api/webviewWindow");
      const login = new WebviewWindow("login", {
        url: "https://app.anylive.jp",
        title: "AnyLive Login",
        width: 900,
        height: 700,
        center: true,
      });
      login.once("tauri://error", () => {
        window.open("https://app.anylive.jp", "_blank");
      });
    } catch {
      window.open("https://app.anylive.jp", "_blank");
    }
  };

  if (!sidecar.isReady && !sidecar.error) {
    return (
      <div className="flex items-center justify-center h-screen w-screen bg-[var(--bg-base)] text-[var(--text-secondary)] text-sm">
        Starting sidecar...
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[var(--bg-base)]">
      <Titlebar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          activePanel={activePanel}
          onPanelChange={setActivePanel}
          clients={clients}
          selectedClient={selectedClient}
          onClientChange={setSelectedClient}
          sessionValid={sessionValid}
          sidecarUrl={sidecar.sidecarUrl}
          onRelogin={handleRelogin}
          onClientCreated={(name) => { setClients((prev) => [...prev, name].sort()); setSelectedClient(name); }}
          onClientDeleted={(name) => { setClients((prev) => prev.filter((c) => c !== name)); setSelectedClient("default"); }}
        />
        <MainContent activePanel={activePanel} client={selectedClient} sidecarUrl={sidecar.sidecarUrl} />
      </div>
      {!chromiumReady && sidecar.sidecarUrl && (
        <SetupWizard sidecarUrl={sidecar.sidecarUrl} onComplete={() => setChromiumReady(true)} />
      )}
    </div>
  );
}

export default App;
