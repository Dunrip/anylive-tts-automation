import React, { useCallback, useState } from "react";
import { PanelType } from "../../lib/navigation";
import type { WSMessage } from "../../lib/types";
import { TTSPanel } from "../tts/TTSPanel";
import { LogViewer } from "./LogViewer";

interface MainContentProps {
  activePanel: PanelType;
  client: string;
  sidecarUrl?: string | null;
}

// Placeholder panels — will be replaced by actual panels in later tasks
function PlaceholderPanel({ name }: { name: string }): React.ReactElement {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        color: "var(--text-muted)",
        fontSize: "14px",
      }}
    >
      {name} Panel — Coming Soon
    </div>
  );
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
        return <PlaceholderPanel name="FAQ" />;
      case "scripts":
        return <PlaceholderPanel name="Scripts" />;
      case "history":
        return <PlaceholderPanel name="History" />;
      case "settings":
        return <PlaceholderPanel name="Settings" />;
      default:
        return <PlaceholderPanel name="Unknown" />;
    }
  };

  return (
    <main
      style={{
        flex: 1,
        height: "100vh",
        backgroundColor: "var(--bg-base)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Content area */}
      <div style={{ flex: 1, overflow: "auto", padding: "16px" }}>
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
