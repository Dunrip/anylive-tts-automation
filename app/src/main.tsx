import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource-variable/onest";
import App from "./App";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
