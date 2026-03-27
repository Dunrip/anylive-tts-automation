import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { TTSConfig, LiveConfig } from "../../lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface SettingsPanelProps {
  client: string;
  sidecarUrl?: string | null;
}

const DEFAULT_TTS: TTSConfig = {
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

const DEFAULT_LIVE: LiveConfig = {
  base_url: "",
  audio_dir: "downloads",
  audio_extensions: [".mp3", ".wav"],
  csv_columns: {
    product_number: "No.",
    product_name: "Product Name",
    question: "Keywords",
    script_content: "TH Script",
    audio_code: "Audio Code",
  },
};

const inputClasses = "w-full px-2.5 py-1.5 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md text-sm box-border";
const labelClasses = "text-xs text-[var(--text-secondary)] block mb-1";
const sectionClasses = "mb-6";
const sectionTitleClasses = "text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3 pb-1.5 border-b border-[var(--border-default)]";

export function SettingsPanel({ client, sidecarUrl }: SettingsPanelProps): React.ReactElement {
  const [ttsConfig, setTtsConfig] = useState<TTSConfig>(DEFAULT_TTS);
  const [liveConfig, setLiveConfig] = useState<LiveConfig>(DEFAULT_LIVE);
  const [originalTts, setOriginalTts] = useState<TTSConfig>(DEFAULT_TTS);
  const [originalLive, setOriginalLive] = useState<LiveConfig>(DEFAULT_LIVE);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saved" | "error">("idle");

  useEffect(() => {
    if (!client) return;

    const applyConfig = (data: Record<string, unknown>): void => {
      const tts = (data.tts || DEFAULT_TTS) as TTSConfig;
      const live = (data.live || DEFAULT_LIVE) as LiveConfig;
      setTtsConfig(tts);
      setOriginalTts(tts);
      setLiveConfig(live);
      setOriginalLive(live);
    };

    if (sidecarUrl) {
      fetch(`${sidecarUrl}/api/configs/${client}`)
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then(applyConfig)
        .catch((err) => { console.error("SettingsPanel: sidecar config load failed:", err); });
    } else {
      Promise.resolve()
        .then(() => invoke<string>("read_client_config", { client }))
        .then((json) => applyConfig(JSON.parse(json)))
        .catch((err) => { console.error("SettingsPanel: tauri config load failed:", err); });
    }
  }, [sidecarUrl, client]);

  const handleSave = async (): Promise<void> => {
    setSaving(true);
    try {
      if (sidecarUrl) {
        const resp = await fetch(`${sidecarUrl}/api/configs/${client}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tts: ttsConfig, live: liveConfig }),
        });
        if (!resp.ok) { setSaveStatus("error"); return; }
      } else {
        await invoke("save_client_config", {
          client,
          tts: JSON.stringify(ttsConfig, null, 2),
          live: JSON.stringify(liveConfig, null, 2),
        });
      }
      setOriginalTts(ttsConfig);
      setOriginalLive(liveConfig);
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus("idle"), 2000);
    } catch {
      setSaveStatus("error");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = (): void => {
    setTtsConfig(originalTts);
    setLiveConfig(originalLive);
    setSaveStatus("idle");
  };

  const updateTts = (field: keyof TTSConfig, value: unknown): void => {
    setTtsConfig((prev) => ({ ...prev, [field]: value }));
  };

  const updateTtsCsv = (col: string, value: string): void => {
    setTtsConfig((prev) => ({
      ...prev,
      csv_columns: { ...prev.csv_columns, [col]: value },
    }));
  };

  const updateLive = (field: keyof LiveConfig, value: unknown): void => {
    setLiveConfig((prev) => ({ ...prev, [field]: value }));
  };

  const updateLiveCsv = (col: string, value: string): void => {
    setLiveConfig((prev) => ({
      ...prev,
      csv_columns: { ...prev.csv_columns, [col]: value },
    }));
  };

  return (
    <div data-testid="settings-panel" className="p-4 h-full overflow-y-auto">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-base font-semibold text-[var(--text-primary)] m-0">
          Settings — {client}
        </h2>
        <div className="flex gap-2 items-center">
          <Button data-testid="save-button" onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
          <Button data-testid="reset-button" variant="outline" onClick={handleReset}>Reset</Button>
          {saveStatus === "saved" && <span data-testid="save-success" className="text-xs text-[var(--success)]">Saved</span>}
          {saveStatus === "error" && <span data-testid="save-error" className="text-xs text-[var(--error)]">Save failed</span>}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-8">
        {/* TTS Column */}
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 pb-2 border-b border-[var(--border-default)]" data-testid="settings-tab-tts">
            TTS
          </h3>
          <div className={sectionClasses}>
            <p className={sectionTitleClasses}>Automation</p>
            <div className="mb-3">
              <label className={labelClasses}>Version Template</label>
              <input data-testid="input-version-template" type="text" value={ttsConfig.version_template} onChange={(e) => updateTts("version_template", e.target.value)} placeholder="Template_Name" className={inputClasses} />
            </div>
            <div className="mb-3">
              <label className={labelClasses}>Voice Name</label>
              <input data-testid="input-voice-name" type="text" value={ttsConfig.voice_name} onChange={(e) => updateTts("voice_name", e.target.value)} placeholder="Voice_Clone_Name" className={inputClasses} />
            </div>
            <div className="mb-3">
              <label className={labelClasses}>Max Scripts Per Version</label>
              <input data-testid="input-max-scripts" type="number" value={ttsConfig.max_scripts_per_version} onChange={(e) => updateTts("max_scripts_per_version", parseInt(e.target.value, 10))} min={1} max={50} className={cn(inputClasses, "w-[120px]")} />
            </div>
            <div className="flex flex-col gap-2">
              <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)] cursor-pointer">
                <input data-testid="toggle-voice-selection" type="checkbox" checked={ttsConfig.enable_voice_selection ?? false} onChange={(e) => updateTts("enable_voice_selection", e.target.checked)} />
                Enable Voice Selection
              </label>
              <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)] cursor-pointer">
                <input data-testid="toggle-product-info" type="checkbox" checked={ttsConfig.enable_product_info ?? false} onChange={(e) => updateTts("enable_product_info", e.target.checked)} />
                Enable Product Info
              </label>
            </div>
          </div>
          <div className={sectionClasses}>
            <p className={sectionTitleClasses}>CSV Column Mapping</p>
            {[{ key: "product_number", label: "Product Number" }, { key: "product_name", label: "Product Name" }, { key: "script_content", label: "Script Content" }, { key: "audio_code", label: "Audio Code" }].map(({ key, label }) => (
              <div key={key} className="mb-2.5">
                <label className={labelClasses}>{label}</label>
                <input data-testid={`input-csv-${key}`} type="text" value={(ttsConfig.csv_columns as unknown as Record<string, string>)?.[key] || ""} onChange={(e) => updateTtsCsv(key, e.target.value)} className={inputClasses} />
              </div>
            ))}
          </div>
        </div>

        {/* Live Column */}
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 pb-2 border-b border-[var(--border-default)]" data-testid="settings-tab-live">
            Live (FAQ / Scripts)
          </h3>
          <div className={sectionClasses}>
            <p className={sectionTitleClasses}>Audio</p>
            <div className="mb-3">
              <label className={labelClasses}>Audio Directory</label>
              <input data-testid="input-live-audio-dir" type="text" value={liveConfig.audio_dir || ""} onChange={(e) => updateLive("audio_dir", e.target.value)} placeholder="downloads" className={inputClasses} />
            </div>
            <div className="mb-3">
              <label className={labelClasses}>Audio Extensions</label>
              <div className={cn(inputClasses, "flex items-center gap-1.5 min-h-[34px] px-2 py-1.5 cursor-default")}>
                {[".mp3", ".wav"].map((ext) => {
                  const active = (liveConfig.audio_extensions || []).includes(ext);
                  return (
                    <button
                      key={ext}
                      type="button"
                      data-testid={`ext-tag-${ext.slice(1)}`}
                      onClick={() => {
                        const current = liveConfig.audio_extensions || [];
                        updateLive("audio_extensions", active ? current.filter((e) => e !== ext) : [...current, ext]);
                      }}
                      className={cn(
                        "px-2 py-0.5 rounded-md text-xs font-medium border-none cursor-pointer transition-all",
                        active
                          ? "bg-[var(--accent)] text-white"
                          : "bg-transparent text-[var(--text-muted)] border border-dashed border-[var(--border-default)]"
                      )}
                    >
                      {ext}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
          <div className={sectionClasses}>
            <p className={sectionTitleClasses}>CSV Column Mapping</p>
            {[{ key: "product_number", label: "Product Number" }, { key: "product_name", label: "Product Name" }, { key: "question", label: "Question/Keywords" }, { key: "script_content", label: "Script Content" }, { key: "audio_code", label: "Audio Code" }].map(({ key, label }) => (
              <div key={key} className="mb-2.5">
                <label className={labelClasses}>{label}</label>
                <input data-testid={`input-live-csv-${key}`} type="text" value={(liveConfig.csv_columns as unknown as Record<string, string>)?.[key] || ""} onChange={(e) => updateLiveCsv(key, e.target.value)} className={inputClasses} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
