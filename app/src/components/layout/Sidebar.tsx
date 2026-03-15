import React from "react";
import { NAV_ITEMS, PanelType } from "../../lib/navigation";

interface SidebarProps {
  activePanel: PanelType;
  onPanelChange: (panel: PanelType) => void;
  clients: string[];
  selectedClient: string;
  onClientChange: (client: string) => void;
  sessionValid: boolean;
  onRelogin?: () => void;
}

export function Sidebar({
  activePanel,
  onPanelChange,
  clients,
  selectedClient,
  onClientChange,
  sessionValid,
  onRelogin,
}: SidebarProps): React.ReactElement {
  return (
    <aside
      style={{
        width: "220px",
        minWidth: "220px",
        height: "100vh",
        backgroundColor: "var(--bg-surface)",
        borderRight: "1px solid var(--border-default)",
        display: "flex",
        flexDirection: "column",
        padding: "12px 0",
      }}
    >
      {/* App title */}
      <div
        style={{
          padding: "0 16px 12px",
          borderBottom: "1px solid var(--border-default)",
          marginBottom: "8px",
        }}
      >
        <h1
          style={{
            fontSize: "14px",
            fontWeight: 600,
            color: "var(--text-primary)",
            margin: 0,
          }}
        >
          AnyLive TTS
        </h1>
      </div>

      {/* Client switcher */}
      <div style={{ padding: "0 12px 12px" }}>
        <label
          style={{
            fontSize: "11px",
            color: "var(--text-muted)",
            display: "block",
            marginBottom: "4px",
          }}
        >
          CLIENT
        </label>
        <select
          data-testid="client-switcher"
          value={selectedClient}
          onChange={(e) => onClientChange(e.target.value)}
          style={{
            width: "100%",
            backgroundColor: "var(--bg-elevated)",
            color: "var(--text-primary)",
            border: "1px solid var(--border-default)",
            borderRadius: "6px",
            padding: "6px 8px",
            fontSize: "13px",
            cursor: "pointer",
          }}
        >
          {clients.map((client) => (
            <option key={client} value={client}>
              {client}
            </option>
          ))}
        </select>
      </div>

      {/* Navigation items */}
      <nav style={{ flex: 1, padding: "0 8px" }}>
        {NAV_ITEMS.map((item) => {
          const isActive = activePanel === item.panel;
          return (
            <button
              key={item.id}
              data-testid={`nav-${item.id}`}
              onClick={() => onPanelChange(item.panel)}
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "8px 12px",
                borderRadius: "6px",
                border: "none",
                backgroundColor: isActive ? "var(--bg-hover)" : "transparent",
                color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                cursor: "pointer",
                fontSize: "13px",
                fontWeight: isActive ? 500 : 400,
                textAlign: "left",
                borderLeft: isActive
                  ? "2px solid var(--accent)"
                  : "2px solid transparent",
                marginBottom: "2px",
              }}
            >
              <span style={{ fontSize: "16px" }}>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Session indicator */}
      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--border-default)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginBottom: sessionValid ? 0 : "8px",
          }}
        >
          <div
            data-testid="session-dot"
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              backgroundColor: sessionValid ? "var(--success)" : "var(--error)",
              flexShrink: 0,
            }}
          />
          <span
            style={{
              fontSize: "12px",
              color: sessionValid ? "var(--success)" : "var(--error)",
            }}
          >
            {sessionValid ? "Session Active" : "Session Expired"}
          </span>
        </div>
        {!sessionValid && onRelogin && (
          <button
            data-testid="relogin-button"
            onClick={onRelogin}
            style={{
              width: "100%",
              padding: "4px 8px",
              backgroundColor: "var(--accent)",
              color: "white",
              border: "none",
              borderRadius: "4px",
              fontSize: "12px",
              cursor: "pointer",
            }}
          >
            Re-login
          </button>
        )}
      </div>
    </aside>
  );
}
