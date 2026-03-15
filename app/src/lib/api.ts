import type {
  CSVPreviewResponse,
  ClientConfig,
  HealthResponse,
  HistoryRun,
  JobStartRequest,
  JobStatusResponse,
  SessionStatus,
} from "./types";

export function createApiClient(port: number) {
  const base = `http://127.0.0.1:${port}`;

  async function get<T>(path: string): Promise<T> {
    const response = await fetch(`${base}${path}`);
    if (!response.ok) {
      throw new Error(`GET ${path} failed: ${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<T>;
  }

  async function post<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${base}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      throw new Error(`POST ${path} failed: ${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<T>;
  }

  async function put<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${base}${path}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error(`PUT ${path} failed: ${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<T>;
  }

  return {
    health: () => get<HealthResponse>("/health"),
    listConfigs: () => get<string[]>("/api/configs"),
    getConfig: (client: string) => get<ClientConfig>(`/api/configs/${client}`),
    updateConfig: (client: string, config: Partial<ClientConfig>) =>
      put<{ status: string }>(`/api/configs/${client}`, config),
    checkSession: (client: string, site: "tts" | "live") =>
      get<SessionStatus>(`/api/session/${client}/${site}`),
    previewCsv: (csvPath: string, configPath: string) =>
      post<CSVPreviewResponse>("/api/csv/preview", {
        csv_path: csvPath,
        config_path: configPath,
      }),
    startJob: (request: JobStartRequest) => post<{ job_id: string }>("/api/jobs", request),
    getJobStatus: (jobId: string) => get<JobStatusResponse>(`/api/jobs/${jobId}`),
    getHistory: () => get<HistoryRun[]>("/api/history"),
    getHistoryRun: (id: string) => get<HistoryRun>(`/api/history/${id}`),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
