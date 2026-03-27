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
    vi.mocked(globalThis.fetch).mockResolvedValue({
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
    vi.mocked(globalThis.fetch).mockResolvedValue({
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
    vi.mocked(globalThis.fetch).mockResolvedValue({
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

  it("handles status message - success", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue({
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
    vi.mocked(globalThis.fetch).mockResolvedValue({
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
    vi.mocked(globalThis.fetch).mockResolvedValue({
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

    vi.mocked(globalThis.fetch).mockResolvedValue({ ok: true, json: () => Promise.resolve({}) } as Response);

    await act(async () => {
      await result.current.cancelJob("http://127.0.0.1:8080");
    });

    expect(vi.mocked(globalThis.fetch)).toHaveBeenCalledWith(
      "http://127.0.0.1:8080/api/jobs/test-job/cancel",
      { method: "POST" }
    );
  });

  it("pollJobStatus logs error on fetch failure", async () => {
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    vi.mocked(globalThis.fetch).mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useAutomation());

    await act(async () => {
      await result.current.pollJobStatus("http://127.0.0.1:8080", "test-job");
    });

    expect(consoleErrorSpy).toHaveBeenCalledWith("Job poll failed:", expect.any(Error));
    consoleErrorSpy.mockRestore();
  });

  it("cancelJob logs error and sets error state on fetch failure", async () => {
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    vi.mocked(globalThis.fetch).mockResolvedValue({
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

    vi.mocked(globalThis.fetch).mockRejectedValue(new Error("Cancel failed"));

    await act(async () => {
      await result.current.cancelJob("http://127.0.0.1:8080");
    });

    expect(consoleErrorSpy).toHaveBeenCalledWith("Job cancel failed:", expect.any(Error));
    expect(result.current.error).toBe("Error: Cancel failed");
    consoleErrorSpy.mockRestore();
  });
});
