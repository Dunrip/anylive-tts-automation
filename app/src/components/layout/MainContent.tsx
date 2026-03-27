import React, { useCallback, useEffect, useState } from "react";
import { PanelType } from "../../lib/navigation";
import type { WSMessage } from "../../lib/types";
import { TTSPanel } from "../tts/TTSPanel";
import { FAQPanel } from "../faq/FAQPanel";
import { ScriptsPanel } from "../scripts/ScriptsPanel";
import { HistoryPanel } from "../history/HistoryPanel";
import { SettingsPanel } from "../settings/SettingsPanel";
import { LogViewer } from "./LogViewer";

interface MainContentProps {
  activePanel: PanelType;
  client: string;
  sidecarUrl?: string | null;
}



export function MainContent({ activePanel, client, sidecarUrl }: MainContentProps): React.ReactElement {
  const [wsMessages, setWsMessages] = useState<WSMessage[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [clearLogs, setClearLogs] = useState<() => void>(() => () => undefined);

  // Lifted URL state — TTS has its own, FAQ+Scripts share live URL
  const [ttsBaseUrl, setTtsBaseUrl] = useState("");
  const [liveBaseUrl, setLiveBaseUrl] = useState("");

  useEffect(() => {
    if (!sidecarUrl || !client) return;
    fetch(`${sidecarUrl}/api/configs/${client}`)
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((data: Record<string, unknown>) => {
        const tts = data.tts as Record<string, unknown> | undefined;
        const live = data.live as Record<string, unknown> | undefined;
        if (tts?.base_url) setTtsBaseUrl(tts.base_url as string);
        if (live?.base_url) setLiveBaseUrl(live.base_url as string);
      })
      .catch((err) => { console.error("MainContent: initial config load failed:", err); });
  }, [sidecarUrl, client]);

  const saveTtsBaseUrl = useCallback((url: string) => {
    setTtsBaseUrl(url);
    if (!sidecarUrl || !client) return;
    fetch(`${sidecarUrl}/api/configs/${client}`)
      .then((r) => r.json())
      .then((data: Record<string, unknown>) => {
        const tts = (data.tts || {}) as Record<string, unknown>;
        tts.base_url = url;
        return fetch(`${sidecarUrl}/api/configs/${client}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...data, tts }),
        });
      })
      .catch((err) => { console.error("MainContent: TTS base URL save failed:", err); });
  }, [sidecarUrl, client]);

  const saveLiveBaseUrl = useCallback((url: string) => {
    setLiveBaseUrl(url);
    if (!sidecarUrl || !client) return;
    fetch(`${sidecarUrl}/api/configs/${client}`)
      .then((r) => r.json())
      .then((data: Record<string, unknown>) => {
        const live = (data.live || {}) as Record<string, unknown>;
        live.base_url = url;
        return fetch(`${sidecarUrl}/api/configs/${client}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...data, live }),
        });
      })
      .catch((err) => { console.error("MainContent: Live base URL save failed:", err); });
  }, [sidecarUrl, client]);

  const handleLogStateChange = useCallback(
    (logState: { messages: WSMessage[]; isConnected: boolean; clearMessages: () => void }): void => {
      setWsMessages(logState.messages);
      setWsConnected(logState.isConnected);
      setClearLogs(() => logState.clearMessages);
    },
    []
  );

  return (
    <main className="flex-1 h-full bg-[var(--bg-base)] overflow-hidden flex flex-col">
      {/* All panels stay mounted — hidden via CSS to preserve state across tab switches */}
      <div className="flex-1 overflow-auto relative">
        <div className="h-full p-4" style={{ display: activePanel === "tts" ? "block" : "none" }}>
          <TTSPanel client={client} sidecarUrl={sidecarUrl} onLogStateChange={handleLogStateChange} baseUrl={ttsBaseUrl} onBaseUrlChange={saveTtsBaseUrl} />
        </div>
        <div className="h-full p-4" style={{ display: activePanel === "faq" ? "block" : "none" }}>
          <FAQPanel client={client} sidecarUrl={sidecarUrl} baseUrl={liveBaseUrl} onBaseUrlChange={saveLiveBaseUrl} onLogStateChange={handleLogStateChange} />
        </div>
        <div className="h-full p-4" style={{ display: activePanel === "scripts" ? "block" : "none" }}>
          <ScriptsPanel client={client} sidecarUrl={sidecarUrl} baseUrl={liveBaseUrl} onBaseUrlChange={saveLiveBaseUrl} onLogStateChange={handleLogStateChange} />
        </div>
        <div className="h-full p-4" style={{ display: activePanel === "history" ? "block" : "none" }}>
          <HistoryPanel sidecarUrl={sidecarUrl} isActive={activePanel === "history"} />
        </div>
        <div className="h-full p-4" style={{ display: activePanel === "settings" ? "block" : "none" }}>
          <SettingsPanel client={client} sidecarUrl={sidecarUrl} />
        </div>
      </div>

      <LogViewer
        messages={wsMessages}
        isConnected={wsConnected}
        onClear={clearLogs}
      />
    </main>
  );
}
