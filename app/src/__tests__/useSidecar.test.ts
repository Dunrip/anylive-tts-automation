import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { useSidecar } from "../hooks/useSidecar";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

describe("useSidecar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts in loading state", () => {
    const invokeMock = vi.mocked(invoke);
    invokeMock.mockRejectedValue(new Error("not ready"));

    const { result } = renderHook(() => useSidecar());

    expect(result.current.isReady).toBe(false);
    expect(result.current.port).toBeNull();
    expect(result.current.sidecarUrl).toBeNull();
  });

  it("becomes ready when port is returned", async () => {
    const invokeMock = vi.mocked(invoke);
    invokeMock.mockResolvedValue(8080);

    const { result } = renderHook(() => useSidecar());

    await waitFor(() => {
      expect(result.current.isReady).toBe(true);
    });

    expect(result.current.port).toBe(8080);
    expect(result.current.sidecarUrl).toBe("http://127.0.0.1:8080");
  });

  it("retries when sidecar is not ready", async () => {
    const invokeMock = vi.mocked(invoke);
    invokeMock.mockRejectedValueOnce(new Error("not ready")).mockResolvedValue(9090);

    const { result } = renderHook(() => useSidecar());

    await waitFor(
      () => {
        expect(result.current.isReady).toBe(true);
      },
      { timeout: 3000 }
    );

    expect(result.current.port).toBe(9090);
  });

  it("includes error context when sidecar fails to start", async () => {
    vi.useFakeTimers();
    const invokeMock = vi.mocked(invoke);
    invokeMock.mockRejectedValue(new Error("ECONNREFUSED: Connection refused"));

    const { result } = renderHook(() => useSidecar());

    // Advance timers to exhaust all 60 attempts (60 * 500ms = 30s)
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.isReady).toBe(false);
    expect(result.current.error).toContain("Sidecar failed to start after 30s:");
    expect(result.current.error).toContain("ECONNREFUSED");

    vi.useRealTimers();
  });

  describe("health monitoring", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
      vi.unstubAllGlobals();
    });

    const setupReady = async (fetchMock: ReturnType<typeof vi.fn>) => {
      vi.mocked(invoke).mockResolvedValue(8080);
      vi.stubGlobal("fetch", fetchMock);
      const rendered = renderHook(() => useSidecar());
      // Flush the invoke microtask → setState({isReady:true}) → health interval registered
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      return rendered;
    };

    it("starts a /health check every 10s after sidecar is ready", async () => {
      const fetchMock = vi.fn().mockResolvedValue({ ok: true });
      const { result } = await setupReady(fetchMock);

      expect(result.current.isReady).toBe(true);
      expect(fetchMock).not.toHaveBeenCalled();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(10_000);
      });

      expect(fetchMock).toHaveBeenCalledTimes(1);
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8080/health",
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    it("sets isReady=false and error after 3 consecutive health check failures", async () => {
      const fetchMock = vi
        .fn()
        .mockRejectedValue(new Error("net::ERR_CONNECTION_REFUSED"));
      const { result } = await setupReady(fetchMock);

      expect(result.current.isReady).toBe(true);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(30_000);
      });

      expect(result.current.isReady).toBe(false);
      expect(result.current.error).toMatch(/health check failed/i);
    });

    it("does not set isReady=false after only 2 consecutive health check failures", async () => {
      const fetchMock = vi.fn().mockRejectedValue(new Error("timeout"));
      const { result } = await setupReady(fetchMock);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(20_000);
      });

      expect(result.current.isReady).toBe(true);
      expect(result.current.error).toBeNull();
    });

    it("recovers isReady=true after health check succeeds following 3 failures", async () => {
      const fetchMock = vi
        .fn()
        .mockRejectedValueOnce(new Error("timeout"))
        .mockRejectedValueOnce(new Error("timeout"))
        .mockRejectedValueOnce(new Error("timeout"))
        .mockResolvedValue({ ok: true });
      const { result } = await setupReady(fetchMock);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(30_000);
      });
      expect(result.current.isReady).toBe(false);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(10_000);
      });
      expect(result.current.isReady).toBe(true);
      expect(result.current.error).toBeNull();
    });

    it("clears health check interval on unmount", async () => {
      const fetchMock = vi.fn().mockResolvedValue({ ok: true });
      const { unmount } = await setupReady(fetchMock);

      unmount();
      fetchMock.mockClear();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(10_000);
      });

      expect(fetchMock).not.toHaveBeenCalled();
    });
  });
});
