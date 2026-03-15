import React, { useState, useEffect } from "react";
import type { TTSConfig } from "../../lib/types";

interface SettingsPanelProps {
  client: string;
  sidecarUrl?: string | null;
}

const DEFAULT_CONFIG: TTSConfig = {
  base_url: "",
  version_template: "",
  voice_name: "",
  max_scripts_per_version: 10,
  enable_voice_selection: false,
  enable_product_info: false,
  csv_columns: {
    product_number: "No.",
    product_name: "Product Name",
    script_content: "TH Script",
    audio_code: "Audio Code",
  },
};

export function SettingsPanel({ client, sidecarUrl }: SettingsPanelProps): React.ReactElement {
  const [config, setConfig] = useState<TTSConfig>(DEFAULT_CONFIG);
  const [originalConfig, setOriginalConfig] = useState<TTSConfig>(DEFAULT_CONFIG);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saved" | "error">("idle");

  // Load config from sidecar
  useEffect(() => {
    if (!sidecarUrl || !client) return;

    fetch(`${sidecarUrl}/api/configs/${client}`)
      .then((r) => r.json())
      .then((data) => {
        const tts = data.tts || DEFAULT_CONFIG;
        setConfig(tts);
        setOriginalConfig(tts);
      })
      .catch(() => {
        // Use defaults if sidecar unavailable
      });
  }, [sidecarUrl, client]);

  const handleSave = async (): Promise<void> => {
    if (!sidecarUrl) return;
    setSaving(true);
    try {
      const resp = await fetch(`${sidecarUrl}/api/configs/${client}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tts: config }),
      });
      if (resp.ok) {
        setOriginalConfig(config);
        setSaveStatus("saved");
        setTimeout(() => setSaveStatus("idle"), 2000);
      } else {
        setSaveStatus("error");
      }
    } catch {
      setSaveStatus("error");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = (): void => {
    setConfig(originalConfig);
    setSaveStatus("idle");
  };

  const updateField = (field: keyof TTSConfig, value: unknown): void => {
    setConfig((prev) => ({ ...prev, [field]: value }));
  };

  const updateCsvColumn = (col: string, value: string): void => {
    setConfig((prev) => ({
      ...prev,
      csv_columns: { ...prev.csv_columns, [col]: value },
    }));
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "6px 10px",
    backgroundColor: "var(--bg-elevated)",
    color: "var(--text-primary)",
    border: "1px solid var(--border-default)",
    borderRadius: "6px",
    fontSize: "13px",
    boxSizing: "border-box",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: "12px",
    color: "var(--text-secondary)",
    display: "block",
    marginBottom: "4px",
  };

  const sectionStyle: React.CSSProperties = {
    marginBottom: "24px",
  };

  const sectionTitleStyle: React.CSSProperties = {
    fontSize: "11px",
    fontWeight: 600,
    color: "var(--text-muted)",
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    marginBottom: "12px",
    paddingBottom: "6px",
    borderBottom: "1px solid var(--border-default)",
  };

  return (
    <div
      data-testid="settings-panel"
      style={{
        padding: "16px",
        height: "100%",
        overflowY: "auto",
        maxWidth: "600px",
      }}
    >
      <h2 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "20px" }}>
        Settings — {client}
      </h2>

      {/* Connection section */}
      <div style={sectionStyle}>
        <p style={sectionTitleStyle}>Connection</p>
        <div style={{ marginBottom: "12px" }}>
          <label style={labelStyle}>Base URL</label>
          <input
            data-testid="input-base-url"
            type="text"
            value={config.base_url}
            onChange={(e) => updateField("base_url", e.target.value)}
            placeholder="https://app.anylive.jp/scripts/XXX"
            style={inputStyle}
          />
        </div>
      </div>

      {/* Automation section */}
      <div style={sectionStyle}>
        <p style={sectionTitleStyle}>Automation</p>
        <div style={{ marginBottom: "12px" }}>
          <label style={labelStyle}>Version Template</label>
          <input
            data-testid="input-version-template"
            type="text"
            value={config.version_template}
            onChange={(e) => updateField("version_template", e.target.value)}
            placeholder="Template_Name"
            style={inputStyle}
          />
        </div>
        <div style={{ marginBottom: "12px" }}>
          <label style={labelStyle}>Voice Name</label>
          <input
            data-testid="input-voice-name"
            type="text"
            value={config.voice_name}
            onChange={(e) => updateField("voice_name", e.target.value)}
            placeholder="Voice_Clone_Name"
            style={inputStyle}
          />
        </div>
        <div style={{ marginBottom: "12px" }}>
          <label style={labelStyle}>Max Scripts Per Version</label>
          <input
            data-testid="input-max-scripts"
            type="number"
            value={config.max_scripts_per_version}
            onChange={(e) => updateField("max_scripts_per_version", parseInt(e.target.value, 10))}
            min={1}
            max={50}
            style={{ ...inputStyle, width: "120px" }}
          />
        </div>
        <div style={{ display: "flex", gap: "16px" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--text-secondary)", cursor: "pointer" }}>
            <input
              data-testid="toggle-voice-selection"
              type="checkbox"
              checked={config.enable_voice_selection ?? false}
              onChange={(e) => updateField("enable_voice_selection", e.target.checked)}
            />
            Enable Voice Selection
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--text-secondary)", cursor: "pointer" }}>
            <input
              data-testid="toggle-product-info"
              type="checkbox"
              checked={config.enable_product_info ?? false}
              onChange={(e) => updateField("enable_product_info", e.target.checked)}
            />
            Enable Product Info
          </label>
        </div>
      </div>

      {/* CSV Columns section */}
      <div style={sectionStyle}>
        <p style={sectionTitleStyle}>CSV Column Mapping</p>
        {[
          { key: "product_number", label: "Product Number Column" },
          { key: "product_name", label: "Product Name Column" },
          { key: "script_content", label: "Script Content Column" },
          { key: "audio_code", label: "Audio Code Column" },
        ].map(({ key, label }) => (
          <div key={key} style={{ marginBottom: "10px" }}>
            <label style={labelStyle}>{label}</label>
            <input
              data-testid={`input-csv-${key}`}
              type="text"
              value={(config.csv_columns as unknown as Record<string, string>)?.[key] || ""}
              onChange={(e) => updateCsvColumn(key, e.target.value)}
              style={inputStyle}
            />
          </div>
        ))}
      </div>

      {/* Action buttons */}
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <button
          data-testid="save-button"
          onClick={handleSave}
          disabled={saving || !sidecarUrl}
          style={{
            padding: "8px 20px",
            backgroundColor: "var(--accent)",
            color: "white",
            border: "none",
            borderRadius: "6px",
            fontSize: "13px",
            cursor: saving || !sidecarUrl ? "not-allowed" : "pointer",
            opacity: saving || !sidecarUrl ? 0.7 : 1,
          }}
        >
          {saving ? "Saving..." : "Save"}
        </button>
        <button
          data-testid="reset-button"
          onClick={handleReset}
          style={{
            padding: "8px 16px",
            backgroundColor: "transparent",
            color: "var(--text-secondary)",
            border: "1px solid var(--border-default)",
            borderRadius: "6px",
            fontSize: "13px",
            cursor: "pointer",
          }}
        >
          Reset
        </button>
        {saveStatus === "saved" && (
          <span data-testid="save-success" style={{ fontSize: "12px", color: "var(--success)" }}>
            ✓ Saved
          </span>
        )}
        {saveStatus === "error" && (
          <span data-testid="save-error" style={{ fontSize: "12px", color: "var(--error)" }}>
            ✗ Save failed
          </span>
        )}
      </div>

      {/* File path info */}
      {sidecarUrl && (
        <p style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "16px" }}>
          Config: configs/{client}/tts.json
        </p>
      )}
    </div>
  );
}
