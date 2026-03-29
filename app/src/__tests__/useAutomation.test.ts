import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAutomation } from "../hooks/useAutomation";

describe("useAutomation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  it("starts in idle state", () => {
    const { result } = renderHook(() => useAutomation());

    expect(result.current.isRunning).toBe(false);
    expect(result.current.jobId).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("starts run and sets jobId on success", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ job_id: "test-job-123" }),
      } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "configs/default/tts.json",
        csvPath: "/test.csv",
        options: { headless: true, dry_run: true },
        estimatedVersions: 3,
      });
    });

    expect(result.current.jobId).toBe("test-job-123");
    expect(result.current.wsUrl).toBe("ws://127.0.0.1:8080/api/jobs/test-job-123/ws");
    expect(result.current.isRunning).toBe(true);
    expect(result.current.versions).toHaveLength(3);
  });

  it("sets error on failed request", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: () => Promise.resolve({ detail: "Job already running" }),
      } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "configs/default/tts.json",
        csvPath: "/test.csv",
        options: {},
      });
    });

    expect(result.current.isRunning).toBe(false);
    expect(result.current.error).toBe("Job already running");
  });

  it("handles progress message", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ job_id: "test-job" }),
      } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "configs/default/tts.json",
        csvPath: "/test.csv",
        options: {},
        estimatedVersions: 5,
      });
    });

    act(() => {
      result.current.handleMessage({
        type: "progress",
        current: 2,
        total: 5,
        version_name: "1_ProductA",
      });
    });

    expect(result.current.progress.current).toBe(2);
    expect(result.current.progress.total).toBe(5);
    expect(result.current.versions[1]?.name).toBe("1_ProductA");
    expect(result.current.versions[1]?.status).toBe("running");
  });

  it("preserves failed version status on later handleMessage progress updates", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ job_id: "test-job" }),
      } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "configs/default/tts.json",
        csvPath: "/test.csv",
        options: {},
        estimatedVersions: 3,
      });
    });

    act(() => {
      result.current.handleMessage({
        type: "progress",
        current: 1,
        total: 3,
        version_name: "1_ProductA",
      });
      result.current.handleMessage({
        type: "status",
        job_id: "test-job",
        status: "failed",
      });
      result.current.handleMessage({
        type: "progress",
        current: 3,
        total: 3,
        version_name: "3_ProductC",
      });
    });

    expect(result.current.versions[0]?.status).toBe("failed");
  });

  it("preserves failed version status on pollJobStatus progress updates", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ job_id: "test-job" }),
      } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "configs/default/tts.json",
        csvPath: "/test.csv",
        options: {},
        estimatedVersions: 3,
      });
    });

    act(() => {
      result.current.handleMessage({
        type: "progress",
        current: 1,
        total: 3,
        version_name: "1_ProductA",
      });
      result.current.handleMessage({
        type: "status",
        job_id: "test-job",
        status: "failed",
      });
    });

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "running",
          progress: { current: 2, total: 3 },
          error: null,
          messages: [],
        }),
    } as Response);

    await act(async () => {
      await result.current.pollJobStatus("http://127.0.0.1:8080", "test-job");
    });

    expect(result.current.versions[0]?.status).toBe("failed");
  });

  it("handles status message - success", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ job_id: "test-job" }),
      } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "configs/default/tts.json",
        csvPath: "/test.csv",
        options: {},
        estimatedVersions: 2,
      });
    });

    act(() => {
      result.current.handleMessage({
        type: "progress",
        current: 1,
        total: 2,
        version_name: "1_ProductA",
      });
      result.current.handleMessage({
        type: "status",
        job_id: "test-job",
        status: "success",
      });
    });

    expect(result.current.isRunning).toBe(false);
    expect(result.current.versions[0]?.status).toBe("success");
  });

  it("resets state", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ job_id: "test-job" }),
      } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "test.json",
        csvPath: "test.csv",
        options: {},
      });
    });

    act(() => {
      result.current.reset();
    });

    expect(result.current.isRunning).toBe(false);
    expect(result.current.jobId).toBeNull();
    expect(result.current.versions).toHaveLength(0);
    expect(result.current.wsUrl).toBeNull();
  });

  it("cancelJob calls cancel endpoint", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ job_id: "test-job" }),
      } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "configs/default/tts.json",
        csvPath: "/test.csv",
        options: {},
      });
    });

    fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve({}) } as Response);

    await act(async () => {
      await result.current.cancelJob("http://127.0.0.1:8080");
    });

    expect(vi.mocked(globalThis.fetch)).toHaveBeenCalledWith(
      "http://127.0.0.1:8080/api/jobs/test-job/cancel",
      { method: "POST" }
    );
  });

  it("pollJobStatus sets error state on fetch failure (no console.error)", async () => {
    vi.mocked(globalThis.fetch).mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.pollJobStatus("http://127.0.0.1:8080", "test-job");
    });

    expect(result.current.error).toBe("Network error");
    expect(result.current.isRunning).toBe(false);
  });

  it("pollJobStatus returns early for malformed API response (missing progress)", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ status: "running" }),
    } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.pollJobStatus("http://127.0.0.1:8080", "test-job");
    });

    expect(result.current.error).toBeNull();
    expect(result.current.isRunning).toBe(false);
  });

  it("cancelJob sets error state on fetch failure (no console.error)", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ job_id: "test-job" }),
      } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "configs/default/tts.json",
        csvPath: "/test.csv",
        options: {},
      });
    });

    fetchMock.mockRejectedValue(new Error("Cancel failed"));

    await act(async () => {
      await result.current.cancelJob("http://127.0.0.1:8080");
    });

    expect(result.current.error).toBe("Cancel failed");
  });

  it("startRun sets error when server response has no job_id", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock
      .mockResolvedValueOnce({ ok: true } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ unexpected: "field" }),
      } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "configs/default/tts.json",
        csvPath: "/test.csv",
        options: {},
      });
    });

    expect(result.current.isRunning).toBe(false);
    expect(result.current.error).toBe("Invalid response from server");
    expect(result.current.jobId).toBeNull();
  });

  it("health check guard prevents job start when sidecar is not ready", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock.mockResolvedValue({
      ok: false,
      status: 503,
    } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "configs/default/tts.json",
        csvPath: "/test.csv",
        options: {},
      });
    });

    expect(result.current.isRunning).toBe(false);
    expect(result.current.error).toBe("Sidecar is not ready. Please wait a moment and try again.");
    expect(result.current.jobId).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8080/health");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("health check guard allows job start when sidecar is ready", async () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ job_id: "test-job-456" }),
      } as Response);

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.startRun({
        sidecarUrl: "http://127.0.0.1:8080",
        endpoint: "/api/tts/run",
        configPath: "configs/default/tts.json",
        csvPath: "/test.csv",
        options: {},
      });
    });

    expect(result.current.isRunning).toBe(true);
    expect(result.current.jobId).toBe("test-job-456");
    expect(result.current.error).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8080/health");
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8080/api/tts/run", expect.any(Object));
  });

  it("sets error state when status WS message contains error field", () => {
    const { result } = renderHook(() => useAutomation());

    act(() => {
      result.current.handleMessage({
        type: "status",
        job_id: "x",
        status: "failed",
        error: "Timeout",
      });
    });

    expect(result.current.error).toBe("Timeout");
    expect(result.current.isRunning).toBe(false);
  });

  it("does not set error state when status WS message has no error field", () => {
    const { result } = renderHook(() => useAutomation());

    act(() => {
      result.current.handleMessage({
        type: "status",
        job_id: "x",
        status: "success",
      });
    });

    expect(result.current.error).toBeNull();
  });
});
