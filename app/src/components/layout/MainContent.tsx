import React, { useCallback, useState } from "react";
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

  const handleLogStateChange = useCallback(
    (logState: { messages: WSMessage[]; isConnected: boolean; clearMessages: () => void }): void => {
      setWsMessages(logState.messages);
      setWsConnected(logState.isConnected);
      setClearLogs(() => logState.clearMessages);
    },
    []
  );

  const renderPanel = (): React.ReactElement => {
    switch (activePanel) {
      case "tts":
        return (
          <TTSPanel
            client={client}
            sidecarUrl={sidecarUrl}
            onLogStateChange={handleLogStateChange}
          />
        );
      case "faq":
        return (
          <FAQPanel
            client={client}
            sidecarUrl={sidecarUrl}
          />
        );
      case "scripts":
        return (
          <ScriptsPanel
            client={client}
            sidecarUrl={sidecarUrl}
          />
        );
      case "history":
        return <HistoryPanel sidecarUrl={sidecarUrl} />;
      case "settings":
        return <SettingsPanel client={client} sidecarUrl={sidecarUrl} />;
      default:
        return <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-sm">Unknown Panel</div>;
    }
  };

  return (
    <main className="flex-1 h-full bg-[var(--bg-base)] overflow-hidden flex flex-col">
      {/* Content area */}
      <div className="flex-1 overflow-auto p-4">
        {renderPanel()}
      </div>

      <LogViewer
        messages={wsMessages}
        isConnected={wsConnected}
        onClear={clearLogs}
        height="220px"
      />
    </main>
  );
}
