import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import "./App.css";

function App() {
  const [status, setStatus] = useState("idle");
  const [health, setHealth] = useState("");

  async function checkHealth() {
    setStatus("checking");
    try {
      const response = await invoke<{ status: string }>("get_health");
      setHealth(JSON.stringify(response));
      setStatus("ok");
    } catch (error) {
      setHealth(String(error));
      setStatus("error");
    }
  }

  return (
    <main className="container">
      <h1>Tauri v2 Sidecar Spike</h1>
      <button type="button" onClick={checkHealth}>
        Check Sidecar Health
      </button>
      <p>State: {status}</p>
      <pre>{health}</pre>
    </main>
  );
}

export default App;
