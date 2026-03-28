import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Sidebar } from "./components/layout/Sidebar";
import { MainContent } from "./components/layout/MainContent";
import { Titlebar } from "./components/layout/Titlebar";
import { Onboarding } from "./components/common/Onboarding";
import { Toaster } from "./components/ui/sonner";
import { useSidecar } from "./hooks/useSidecar";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { useUpdateCheck } from "./hooks/useUpdateCheck";
import { useAppVersion } from "./hooks/useAppVersion";
import { PanelType } from "./lib/navigation";
import { SessionStatus } from "./lib/types";

function App(): React.ReactElement {
  const [activePanel, setActivePanel] = useState<PanelType>("tts");
  const [selectedClient, setSelectedClient] = useState<string>("default");
  const [clients, setClients] = useState<string[]>(["default"]);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [userDisplayName, setUserDisplayName] = useState<string | null>(null);
  const [sessionValid, setSessionValid] = useState<boolean>(false);
  const [chromiumInstalled, setChromiumInstalled] = useState<boolean | null>(null);
  const [loginInProgress, setLoginInProgress] = useState<boolean>(false);
  const sidecar = useSidecar();
  const appVersion = useAppVersion();

  useKeyboardShortcuts({
    onPanelChange: setActivePanel,
  });

  useUpdateCheck();

  useEffect(() => {
    const loadClientsFromRust = async (): Promise<void> => {
      try {
        const list = await invoke<string[]>("list_client_configs");
        if (Array.isArray(list) && list.length > 0) setClients(list);
      } catch {
        // Rust command not available (e.g. running in browser dev mode)
      }
    };
    loadClientsFromRust();
  }, []);

  useEffect(() => {
    if (!sidecar.sidecarUrl) return;

    fetch(`${sidecar.sidecarUrl}/api/configs`)
      .then((r) => r.json())
      .then((data: string[]) => {
        if (Array.isArray(data) && data.length > 0) {
          setClients(data);
          if (!data.includes(selectedClient)) {
            setSelectedClient(data[0]);
          }
        }
      })
      .catch(() => {
      });
  }, [sidecar.sidecarUrl, selectedClient]);

  useEffect(() => {
    if (!sidecar.sidecarUrl || !selectedClient) return;

    fetch(`${sidecar.sidecarUrl}/api/session/${selectedClient}/tts`)
      .then((r) => r.json())
      .then((data: SessionStatus) => {
        setSessionValid(data.valid);
        if (data.valid) {
          setUserDisplayName(data.display_name);
          setUserEmail(data.email);
        }
      })
      .catch(() => {
      });
  }, [sidecar.sidecarUrl, selectedClient]);

  useEffect(() => {
    if (!sidecar.sidecarUrl) return;

    fetch(`${sidecar.sidecarUrl}/api/setup/chromium-status`)
      .then((r) => r.json())
      .then((data: { installed: boolean; path: string | null }) => {
        setChromiumInstalled(data.installed);
      })
      .catch(() => {
        setChromiumInstalled(true);
      });
  }, [sidecar.sidecarUrl]);

  const handleRelogin = async (): Promise<void> => {
    if (!sidecar.sidecarUrl) return;
    setLoginInProgress(true);
    try {
      const resp = await fetch(`${sidecar.sidecarUrl}/api/session/login`, { method: "POST" });
      if (!resp.ok) throw new Error(`Login request failed: ${resp.status}`);
      const data = await resp.json();
      if (data.status === "ok") {
        const sessionResp = await fetch(`${sidecar.sidecarUrl}/api/session/${selectedClient}/tts`);
        if (!sessionResp.ok) throw new Error(`Session fetch failed: ${sessionResp.status}`);
        const sessionData: SessionStatus = await sessionResp.json();
        setSessionValid(sessionData.valid);
        if (sessionData.valid) {
          setUserDisplayName(sessionData.display_name);
          setUserEmail(sessionData.email);
        }
      }
    } catch {
    } finally {
      setLoginInProgress(false);
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
      <Toaster />
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
          userEmail={userEmail}
          userDisplayName={userDisplayName}
          onRelogin={loginInProgress ? undefined : handleRelogin}
          onClientCreated={(name) => { setClients((prev) => [...prev, name].sort()); setSelectedClient(name); }}
          onClientDeleted={(name) => { setClients((prev) => prev.filter((c) => c !== name)); setSelectedClient("default"); }}
          appVersion={appVersion}
        />
        <MainContent activePanel={activePanel} client={selectedClient} sidecarUrl={sidecar.sidecarUrl} />
      </div>
      {sidecar.sidecarUrl && chromiumInstalled !== null && (chromiumInstalled === false || !sessionValid) && !loginInProgress && (
        <Onboarding
          sidecarUrl={sidecar.sidecarUrl}
          chromiumInstalled={chromiumInstalled}
          sessionValid={sessionValid}
          onComplete={({ sessionValid: valid, displayName, email }) => {
            setChromiumInstalled(true);
            setSessionValid(valid);
            if (displayName) setUserDisplayName(displayName);
            if (email) setUserEmail(email);
          }}
        />
      )}
    </div>
  );
}

export default App;
