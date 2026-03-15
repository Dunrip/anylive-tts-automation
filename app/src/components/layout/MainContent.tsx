import React from "react";
import { PanelType } from "../../lib/navigation";

interface MainContentProps {
  activePanel: PanelType;
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

export function MainContent({ activePanel }: MainContentProps): React.ReactElement {
  const renderPanel = (): React.ReactElement => {
    switch (activePanel) {
      case "tts":
        return <PlaceholderPanel name="TTS" />;
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
    </main>
  );
}
