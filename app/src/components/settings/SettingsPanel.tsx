import React, { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { TTSConfig, LiveConfig } from "../../lib/types";
import { fetchWithTimeout } from "../../lib/fetchWithTimeout";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { OptionSwitch } from "@/components/common/OptionSwitch";

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

function isTTSConfig(data: unknown): data is TTSConfig {
  if (data == null || typeof data !== "object" || Array.isArray(data)) return false;
  const d = data as Record<string, unknown>;
  return (
    typeof d.base_url === "string" &&
    typeof d.version_template === "string" &&
    typeof d.voice_name === "string" &&
    typeof d.max_scripts_per_version === "number"
  );
}

function isLiveConfig(data: unknown): data is LiveConfig {
  return data != null && typeof data === "object" && !Array.isArray(data);
}

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
  const [loadError, setLoadError] = useState<string | null>(null);
  const saveStatusTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    if (!client) return;

    const controller = new AbortController();
    let unmounted = false;

    const applyConfig = (data: unknown): void => {
      if (unmounted) return;
      if (data == null || typeof data !== "object" || Array.isArray(data)) return;
      const cfg = data as Record<string, unknown>;
      const tts = isTTSConfig(cfg.tts) ? cfg.tts : DEFAULT_TTS;
      const live = isLiveConfig(cfg.live) ? cfg.live : DEFAULT_LIVE;
      setTtsConfig(tts);
      setOriginalTts(tts);
      setLiveConfig(live);
      setOriginalLive(live);
    };

    if (sidecarUrl) {
      fetchWithTimeout(`${sidecarUrl}/api/configs/${client}`, { signal: controller.signal })
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then(applyConfig)
        .catch((err: unknown) => {
          if (err != null && (err as { name?: unknown }).name === "AbortError") return;
          if (!unmounted) setLoadError("Failed to load configuration");
        });
    } else {
      Promise.resolve()
        .then(() => invoke<string>("read_client_config", { client }))
        .then((json) => applyConfig(JSON.parse(json) as unknown))
        .catch(() => {
          if (!unmounted) setLoadError("Failed to load configuration");
        });
    }

    return () => {
      unmounted = true;
      controller.abort();
    };
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
      saveStatusTimeoutRef.current = setTimeout(() => setSaveStatus("idle"), 2000);
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

  useEffect(() => {
    return () => {
      if (saveStatusTimeoutRef.current) clearTimeout(saveStatusTimeoutRef.current);
    };
  }, []);

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

  const isDirty =
    JSON.stringify(ttsConfig) !== JSON.stringify(originalTts) ||
    JSON.stringify(liveConfig) !== JSON.stringify(originalLive);

  return (
    <div data-testid="settings-panel" className="p-4 h-full overflow-y-auto">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-base font-semibold text-[var(--text-primary)] m-0">
          Settings — {client}
        </h2>
        <div className="flex gap-2 items-center">
          <div className="relative">
            <Button data-testid="save-button" variant="success" onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
            {isDirty && !saving && saveStatus === "idle" && (
              <span className="absolute -top-1 -right-1 size-1.5 rounded-full bg-[var(--warning)]" />
            )}
          </div>
          <Button data-testid="reset-button" variant="outline" onClick={handleReset}>Reset</Button>
          {saveStatus === "saved" && <span data-testid="save-success" className="text-xs text-[var(--success)]">✓ Saved</span>}
          {saveStatus === "error" && <span data-testid="save-error" className="text-xs text-[var(--error)]">Save failed</span>}
          {loadError && <span data-testid="load-error" className="text-xs text-[var(--error)]">{loadError}</span>}
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
               <label htmlFor="settings-version-template" className={labelClasses}>Version Template</label>
               <input id="settings-version-template" data-testid="input-version-template" type="text" value={ttsConfig.version_template} onChange={(e) => updateTts("version_template", e.target.value)} placeholder="Template_Name" className={inputClasses} />
             </div>
             <div className="mb-3">
               <label htmlFor="settings-voice-name" className={labelClasses}>Voice Name</label>
               <input id="settings-voice-name" data-testid="input-voice-name" type="text" value={ttsConfig.voice_name} onChange={(e) => updateTts("voice_name", e.target.value)} placeholder="Voice_Clone_Name" className={inputClasses} />
             </div>
             <div className="mb-3">
               <label htmlFor="settings-max-scripts" className={labelClasses}>Max Scripts Per Version</label>
               <input id="settings-max-scripts" data-testid="input-max-scripts" type="number" value={ttsConfig.max_scripts_per_version} onChange={(e) => updateTts("max_scripts_per_version", parseInt(e.target.value, 10))} min={1} max={50} className={cn(inputClasses, "w-[120px]")} />
             </div>
            <div className="flex flex-col gap-2">
              <OptionSwitch
                id="settings-voice-selection"
                testId="toggle-voice-selection"
                checked={ttsConfig.enable_voice_selection ?? false}
                onCheckedChange={(checked) => updateTts("enable_voice_selection", checked)}
                label="Enable Voice Selection"
                description="Show voice dropdown when creating versions"
              />
              <OptionSwitch
                id="settings-product-info"
                testId="toggle-product-info"
                checked={ttsConfig.enable_product_info ?? false}
                onCheckedChange={(checked) => updateTts("enable_product_info", checked)}
                label="Enable Product Info"
                description="Include product name and selling point fields"
              />
            </div>
          </div>
          <div className={sectionClasses}>
            <p className={sectionTitleClasses}>CSV Column Mapping</p>
             {[{ key: "product_number", label: "Product Number" }, { key: "product_name", label: "Product Name" }, { key: "script_content", label: "Script Content" }, { key: "audio_code", label: "Audio Code" }].map(({ key, label }) => (
               <div key={key} className="mb-2.5">
                 <label htmlFor={`settings-csv-tts-${key}`} className={labelClasses}>{label}</label>
                 <input id={`settings-csv-tts-${key}`} data-testid={`input-csv-${key}`} type="text" value={(ttsConfig.csv_columns as unknown as Record<string, string>)?.[key] || ""} onChange={(e) => updateTtsCsv(key, e.target.value)} className={inputClasses} />
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
               <label htmlFor="settings-audio-dir" className={labelClasses}>Audio Directory</label>
               <input id="settings-audio-dir" data-testid="input-live-audio-dir" type="text" value={liveConfig.audio_dir || ""} onChange={(e) => updateLive("audio_dir", e.target.value)} placeholder="downloads" className={inputClasses} />
             </div>
             <div className="mb-3">
               <label htmlFor="settings-audio-extensions" className={labelClasses}>Audio Extensions</label>
               <div id="settings-audio-extensions" className={cn(inputClasses, "flex items-center gap-1.5 min-h-[34px] px-2 py-1.5 cursor-default")}>
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
                 <label htmlFor={`settings-csv-live-${key}`} className={labelClasses}>{label}</label>
                 <input id={`settings-csv-live-${key}`} data-testid={`input-live-csv-${key}`} type="text" value={(liveConfig.csv_columns as unknown as Record<string, string>)?.[key] || ""} onChange={(e) => updateLiveCsv(key, e.target.value)} className={inputClasses} />
               </div>
             ))}
          </div>
        </div>
      </div>
    </div>
  );
}
