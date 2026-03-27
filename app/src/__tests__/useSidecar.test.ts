import { beforeEach, describe, expect, it, vi } from "vitest";
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
});
