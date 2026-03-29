import React, { useCallback, useEffect, useRef, useState } from "react";
import { PanelType } from "../../lib/navigation";
import type { WSMessage } from "../../lib/types";
import { fetchWithTimeout } from "../../lib/fetchWithTimeout";
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

type PanelLogState = {
  messages: WSMessage[];
  isConnected: boolean;
  clearMessages: () => void;
};

const DEFAULT_LOG_STATE: PanelLogState = {
  messages: [],
  isConnected: false,
  clearMessages: () => undefined,
};

const SAVE_DEBOUNCE_MS = 300;

function isConfigShape(data: unknown): data is Record<string, unknown> {
  return data != null && typeof data === "object" && !Array.isArray(data);
}

export function MainContent({ activePanel, client, sidecarUrl }: MainContentProps): React.ReactElement {
  const [panelLogs, setPanelLogs] = useState<Record<string, PanelLogState>>({});
  const [error, setError] = useState<string | null>(null);

  const [ttsBaseUrl, setTtsBaseUrl] = useState("");
  const [liveBaseUrl, setLiveBaseUrl] = useState("");

  const ttsSaveAbortRef = useRef<AbortController | null>(null);
  const liveSaveAbortRef = useRef<AbortController | null>(null);
  const ttsSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const liveSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (ttsSaveTimerRef.current !== null) clearTimeout(ttsSaveTimerRef.current);
      if (liveSaveTimerRef.current !== null) clearTimeout(liveSaveTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!sidecarUrl || !client) return;
    setError(null);
    const controller = new AbortController();
    fetchWithTimeout(`${sidecarUrl}/api/configs/${client}`, { signal: controller.signal })
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((data: unknown) => {
        if (!isConfigShape(data)) return;
        const tts = isConfigShape(data.tts) ? data.tts : undefined;
        const live = isConfigShape(data.live) ? data.live : undefined;
        if (typeof tts?.base_url === "string") setTtsBaseUrl(tts.base_url);
        if (typeof live?.base_url === "string") setLiveBaseUrl(live.base_url);
      })
      .catch((err: unknown) => {
        if (err != null && (err as { name?: unknown }).name === "AbortError") return;
        setError("Failed to load configuration");
      });
    return () => { controller.abort(); };
  }, [sidecarUrl, client]);

  const saveTtsBaseUrl = useCallback((url: string) => {
    if (ttsSaveTimerRef.current !== null) {
      clearTimeout(ttsSaveTimerRef.current);
      ttsSaveTimerRef.current = null;
    }
    ttsSaveAbortRef.current?.abort();

    const prevUrl = ttsBaseUrl;
    setTtsBaseUrl(url);
    if (!sidecarUrl || !client) return;

    ttsSaveTimerRef.current = setTimeout(() => {
      ttsSaveTimerRef.current = null;
      const controller = new AbortController();
      ttsSaveAbortRef.current = controller;
      fetchWithTimeout(`${sidecarUrl}/api/configs/${client}`, { signal: controller.signal })
        .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
        .then((data: unknown) => {
          if (!isConfigShape(data)) throw new Error("Unexpected config format");
          const tts: Record<string, unknown> = isConfigShape(data.tts) ? { ...data.tts } : {};
          tts.base_url = url;
          return fetchWithTimeout(`${sidecarUrl}/api/configs/${client}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...data, tts }),
            signal: controller.signal,
          });
        })
        .catch((err: unknown) => {
          if (err != null && (err as { name?: unknown }).name === "AbortError") return;
          setTtsBaseUrl(prevUrl);
          setError("Failed to save TTS URL — change reverted");
        });
    }, SAVE_DEBOUNCE_MS);
  }, [sidecarUrl, client, ttsBaseUrl]);

  const saveLiveBaseUrl = useCallback((url: string) => {
    if (liveSaveTimerRef.current !== null) {
      clearTimeout(liveSaveTimerRef.current);
      liveSaveTimerRef.current = null;
    }
    liveSaveAbortRef.current?.abort();

    const prevUrl = liveBaseUrl;
    setLiveBaseUrl(url);
    if (!sidecarUrl || !client) return;

    liveSaveTimerRef.current = setTimeout(() => {
      liveSaveTimerRef.current = null;
      const controller = new AbortController();
      liveSaveAbortRef.current = controller;
      fetchWithTimeout(`${sidecarUrl}/api/configs/${client}`, { signal: controller.signal })
        .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
        .then((data: unknown) => {
          if (!isConfigShape(data)) throw new Error("Unexpected config format");
          const live: Record<string, unknown> = isConfigShape(data.live) ? { ...data.live } : {};
          live.base_url = url;
          return fetchWithTimeout(`${sidecarUrl}/api/configs/${client}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...data, live }),
            signal: controller.signal,
          });
        })
        .catch((err: unknown) => {
          if (err != null && (err as { name?: unknown }).name === "AbortError") return;
          setLiveBaseUrl(prevUrl);
          setError("Failed to save live URL — change reverted");
        });
    }, SAVE_DEBOUNCE_MS);
  }, [sidecarUrl, client, liveBaseUrl]);

  const handleTtsLogState = useCallback(
    (logState: { messages: WSMessage[]; isConnected: boolean; clearMessages: () => void }): void => {
      setPanelLogs((prev) => ({ ...prev, tts: logState }));
    },
    []
  );

  const handleFaqLogState = useCallback(
    (logState: { messages: WSMessage[]; isConnected: boolean; clearMessages: () => void }): void => {
      setPanelLogs((prev) => ({ ...prev, faq: logState }));
    },
    []
  );

  const handleScriptsLogState = useCallback(
    (logState: { messages: WSMessage[]; isConnected: boolean; clearMessages: () => void }): void => {
      setPanelLogs((prev) => ({ ...prev, scripts: logState }));
    },
    []
  );

  const activeLogState = panelLogs[activePanel] ?? DEFAULT_LOG_STATE;

  return (
    <main className="flex-1 h-full bg-[var(--bg-base)] overflow-hidden flex flex-col">
      {error && (
        <div
          data-testid="main-content-error"
          className="px-4 py-1 text-xs text-[var(--error)] bg-[var(--bg-elevated)] border-b border-[var(--border-default)] flex items-center justify-between shrink-0"
        >
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} className="ml-2 opacity-70 hover:opacity-100">×</button>
        </div>
      )}
      <div className="flex-1 overflow-auto relative">
        <div className="h-full p-4" style={{ display: activePanel === "tts" ? "block" : "none" }}>
          <TTSPanel client={client} sidecarUrl={sidecarUrl} onLogStateChange={handleTtsLogState} baseUrl={ttsBaseUrl} onBaseUrlChange={saveTtsBaseUrl} />
        </div>
        <div className="h-full p-4" style={{ display: activePanel === "faq" ? "block" : "none" }}>
          <FAQPanel client={client} sidecarUrl={sidecarUrl} baseUrl={liveBaseUrl} onBaseUrlChange={saveLiveBaseUrl} onLogStateChange={handleFaqLogState} />
        </div>
        <div className="h-full p-4" style={{ display: activePanel === "scripts" ? "block" : "none" }}>
          <ScriptsPanel client={client} sidecarUrl={sidecarUrl} baseUrl={liveBaseUrl} onBaseUrlChange={saveLiveBaseUrl} onLogStateChange={handleScriptsLogState} />
        </div>
        <div className="h-full p-4" style={{ display: activePanel === "history" ? "block" : "none" }}>
          <HistoryPanel sidecarUrl={sidecarUrl} isActive={activePanel === "history"} />
        </div>
        <div className="h-full p-4" style={{ display: activePanel === "settings" ? "block" : "none" }}>
          <SettingsPanel client={client} sidecarUrl={sidecarUrl} />
        </div>
      </div>

      <LogViewer
        messages={activeLogState.messages}
        isConnected={activeLogState.isConnected}
        onClear={activeLogState.clearMessages}
      />
    </main>
  );
}
