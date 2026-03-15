import React, { useState } from "react";
import { Sidebar } from "./components/layout/Sidebar";
import { MainContent } from "./components/layout/MainContent";
import { useSidecar } from "./hooks/useSidecar";
import { PanelType } from "./lib/navigation";

function App(): React.ReactElement {
  const [activePanel, setActivePanel] = useState<PanelType>("tts");
  const [selectedClient, setSelectedClient] = useState<string>("default");
  const sidecar = useSidecar();
  const sessionValid = sidecar.isReady;

  // Mock client list — will be fetched from sidecar in Task 11
  const clients = ["default"];

  if (!sidecar.isReady && !sidecar.error) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          width: "100vw",
          backgroundColor: "var(--bg-base)",
          color: "var(--text-secondary)",
          fontSize: "14px",
        }}
      >
        Starting sidecar...
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        width: "100vw",
        overflow: "hidden",
        backgroundColor: "var(--bg-base)",
      }}
    >
      <Sidebar
        activePanel={activePanel}
        onPanelChange={setActivePanel}
        clients={clients}
        selectedClient={selectedClient}
        onClientChange={setSelectedClient}
        sessionValid={sessionValid}
        sidecarUrl={sidecar.sidecarUrl}
      />
      <MainContent activePanel={activePanel} client={selectedClient} sidecarUrl={sidecar.sidecarUrl} />
    </div>
  );
}

export default App;
