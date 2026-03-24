// ============================================================
// Shared TypeScript types for AnyLive TTS Desktop App
// ============================================================

// ----- Job / Automation States -----

export type JobStatus = "pending" | "running" | "success" | "failed" | "cancelled";
export type AutomationType = "tts" | "faq" | "script";

// ----- Sidecar API Types -----

export interface HealthResponse {
  status: string;
  version: string;
}

export interface AutomationOptions {
  headless: boolean;
  dry_run: boolean;
  debug: boolean;
  start_version?: number;
  start_product?: number;
  limit?: number;
  audio_dir?: string;
  delete_scripts?: boolean;
  replace_products?: boolean;
}

export interface JobStartRequest {
  automation_type: AutomationType;
  config_path: string;
  csv_path?: string;
  options: AutomationOptions;
}

export interface JobProgress {
  current: number;
  total: number;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress: JobProgress;
  started_at: string;
  finished_at?: string;
  error?: string;
}

// ----- WebSocket Message Types -----

export type LogLevel = "INFO" | "WARN" | "ERROR" | "DEBUG";

export interface LogMessage {
  type: "log";
  level: LogLevel;
  message: string;
  timestamp: string;
  version?: string;
}

export interface ProgressMessage {
  type: "progress";
  current: number;
  total: number;
  version_name: string;
}

export interface StatusMessage {
  type: "status";
  job_id: string;
  status: JobStatus;
}

export type WSMessage = LogMessage | ProgressMessage | StatusMessage;

// ----- Config Types -----

export interface CSVColumns {
  product_number: string;
  product_name: string;
  question?: string;
  script_content: string;
  audio_code: string;
}

export interface TTSConfig {
  base_url: string;
  version_template: string;
  voice_name: string;
  max_scripts_per_version: number;
  enable_voice_selection?: boolean;
  enable_product_info?: boolean;
  csv_columns: CSVColumns;
}

export interface LiveConfig {
  base_url?: string;
  audio_dir?: string;
  audio_extensions?: string[];
  csv_columns?: Partial<CSVColumns>;
}

export interface ClientConfig {
  name: string;
  tts?: TTSConfig;
  live?: LiveConfig;
}

export interface SessionStatus {
  valid: boolean;
  site: "tts" | "live";
  client: string;
  checked_at: string;
  display_name: string | null;
  email: string | null;
}

// ----- CSV Preview Types -----

export interface CSVPreviewRow {
  no: string;
  product_name: string;
  script: string;
  audio_code: string;
}

export interface CSVPreviewResponse {
  rows: number;
  products: number;
  estimated_versions: number;
  version_names?: string[];
  preview: CSVPreviewRow[];
  errors: string[];
}

// ----- History Types -----

export interface HistoryRun {
  id: string;
  automation_type: AutomationType;
  client: string;
  status: JobStatus;
  started_at: string;
  finished_at?: string;
  versions_total: number;
  versions_success: number;
  versions_failed: number;
  error?: string;
  csv_file?: string;
}
