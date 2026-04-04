import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Sidebar } from "./components/layout/Sidebar";
import { MainContent } from "./components/layout/MainContent";
import { Titlebar } from "./components/layout/Titlebar";
import { Onboarding } from "./components/common/Onboarding";
import { ShortcutsModal } from "./components/common/ShortcutsModal";
import { Toaster } from "./components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useSidecar } from "./hooks/useSidecar";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { useUpdateCheck } from "./hooks/useUpdateCheck";
import { useAppVersion } from "./hooks/useAppVersion";
import { fetchWithTimeout } from "./lib/fetchWithTimeout";
import { PanelType } from "./lib/navigation";
import { SessionStatus } from "./lib/types";

function App(): React.ReactElement {
  const [activePanel, setActivePanel] = useState<PanelType>("tts");
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [selectedClient, setSelectedClient] = useState<string>("default");
  const [clients, setClients] = useState<string[]>(["default"]);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [userDisplayName, setUserDisplayName] = useState<string | null>(null);
  const [sessionValid, setSessionValid] = useState<boolean>(false);
  const [liveSessionValid, setLiveSessionValid] = useState<boolean>(false);
  const [chromiumInstalled, setChromiumInstalled] = useState<boolean | null>(null);
  const [loginInProgress, setLoginInProgress] = useState<boolean>(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [sidecarConfigError, setSidecarConfigError] = useState<boolean>(false);
  const sidecar = useSidecar();
  const appVersion = useAppVersion();
  const { installError, clearInstallError } = useUpdateCheck();

  useKeyboardShortcuts({
    onPanelChange: setActivePanel,
    onShowShortcuts: () => setShortcutsOpen(true),
  });

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

    setSidecarConfigError(false);
    const controller = new AbortController();
    fetchWithTimeout(`${sidecar.sidecarUrl}/api/configs`, { signal: controller.signal })
      .then((r) => r.json())
      .then((data: string[]) => {
        if (Array.isArray(data) && data.length > 0) {
          setClients(data);
          if (!data.includes(selectedClient)) {
            setSelectedClient(data[0]);
          }
        }
      })
      .catch((err: unknown) => {
        if (err != null && (err as { name?: unknown }).name === "AbortError") return;
        setSidecarConfigError(true);
      });
    return () => { controller.abort(); };
  }, [sidecar.sidecarUrl, selectedClient]);

  useEffect(() => {
    if (!sidecar.sidecarUrl || !selectedClient) return;

    const controller = new AbortController();
    fetchWithTimeout(`${sidecar.sidecarUrl}/api/session/${selectedClient}/tts`, { signal: controller.signal })
      .then((r) => r.json())
      .then((data: SessionStatus) => {
        setSessionValid(data.valid);
        if (data.valid) {
          setUserDisplayName(data.display_name);
          setUserEmail(data.email);
        }
      })
      .catch((err: unknown) => {
        if (err != null && (err as { name?: unknown }).name === "AbortError") return;
        setSessionValid(false);
      });
    return () => { controller.abort(); };
  }, [sidecar.sidecarUrl, selectedClient]);

  useEffect(() => {
    if (!sidecar.sidecarUrl || !selectedClient) return;

    const controller = new AbortController();
    fetchWithTimeout(`${sidecar.sidecarUrl}/api/session/${selectedClient}/live`, { signal: controller.signal })
      .then((r) => r.json())
      .then((data: SessionStatus) => {
        setLiveSessionValid(data.valid);
      })
      .catch((err: unknown) => {
        if (err != null && (err as { name?: unknown }).name === "AbortError") return;
        setLiveSessionValid(false);
      });
    return () => { controller.abort(); };
  }, [sidecar.sidecarUrl, selectedClient]);

  useEffect(() => {
    if (!sidecar.sidecarUrl) return;

    const controller = new AbortController();
    fetchWithTimeout(`${sidecar.sidecarUrl}/api/setup/chromium-status`, { signal: controller.signal })
      .then((r) => r.json())
      .then((data: { installed: boolean; path: string | null }) => {
        setChromiumInstalled(data.installed);
      })
      .catch((err: unknown) => {
        if (err != null && (err as { name?: unknown }).name === "AbortError") return;
        // Non-abort error: leave chromiumInstalled as null (status unknown).
        // Do NOT force installed=true — that would silently bypass the setup wizard.
      });
    return () => { controller.abort(); };
  }, [sidecar.sidecarUrl]);

  const handleRelogin = async (): Promise<void> => {
    if (!sidecar.sidecarUrl) return;
    setLoginInProgress(true);
    setLoginError(null);
    try {
      const platform = activePanel === "faq" || activePanel === "scripts" ? "live" : "tts";
      const resp = await fetch(`${sidecar.sidecarUrl}/api/session/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform, client: selectedClient }),
      });
      if (!resp.ok) throw new Error(`Login request failed: ${resp.status}`);
      const data = await resp.json();
      if (data.status === "ok") {
        if (platform === "live") {
          const sessionResp = await fetch(`${sidecar.sidecarUrl}/api/session/${selectedClient}/live`);
          if (!sessionResp.ok) throw new Error(`Session fetch failed: ${sessionResp.status}`);
          const sessionData: SessionStatus = await sessionResp.json();
          setLiveSessionValid(sessionData.valid);
        } else {
          const sessionResp = await fetch(`${sidecar.sidecarUrl}/api/session/${selectedClient}/tts`);
          if (!sessionResp.ok) throw new Error(`Session fetch failed: ${sessionResp.status}`);
          const sessionData: SessionStatus = await sessionResp.json();
          setSessionValid(sessionData.valid);
          if (sessionData.valid) {
            setUserDisplayName(sessionData.display_name);
            setUserEmail(sessionData.email);
          }
        }
      }
    } catch (err) {
      setLoginError(String(err));
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
    <TooltipProvider>
      <div className="flex flex-col h-screen w-screen overflow-hidden bg-[var(--bg-base)]">
        <Toaster />
        <Titlebar />
        {sidecarConfigError && (
          <div
            data-testid="sidecar-config-error"
            className="px-3 py-1 text-xs bg-[var(--warning)] text-[var(--bg-base)] shrink-0"
          >
            Failed to load client list — sidecar unreachable
          </div>
        )}
        {installError && (
          <div
            data-testid="install-error-banner"
            className="px-3 py-1 text-xs bg-[var(--error)] text-white flex items-center justify-between shrink-0"
          >
            <span>Update installation failed: {installError}</span>
            <button type="button" onClick={clearInstallError} className="ml-2 opacity-80 hover:opacity-100">×</button>
          </div>
        )}
        <div className="flex flex-1 overflow-hidden">
          <Sidebar
            activePanel={activePanel}
            onPanelChange={setActivePanel}
            clients={clients}
            selectedClient={selectedClient}
            onClientChange={setSelectedClient}
            sessionValid={sessionValid}
            liveSessionValid={liveSessionValid}
            sidecarUrl={sidecar.sidecarUrl}
            userEmail={userEmail}
            userDisplayName={userDisplayName}
            onRelogin={loginInProgress ? undefined : handleRelogin}
            loginError={loginError}
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
        <ShortcutsModal open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
      </div>
    </TooltipProvider>
  );
}

export default App;
