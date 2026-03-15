import React, { useState } from "react";
import { Sidebar } from "./components/layout/Sidebar";
import { MainContent } from "./components/layout/MainContent";
import { PanelType } from "./lib/navigation";

function App(): React.ReactElement {
  const [activePanel, setActivePanel] = useState<PanelType>("tts");
  const [selectedClient, setSelectedClient] = useState<string>("default");
  const [sessionValid] = useState<boolean>(false); // Will be fetched from sidecar in Task 11

  // Mock client list — will be fetched from sidecar in Task 11
  const clients = ["default"];

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
      />
      <MainContent activePanel={activePanel} />
    </div>
  );
}

export default App;
