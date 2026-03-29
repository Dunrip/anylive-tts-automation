import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAutomationPanel } from "../hooks/useAutomationPanel";
import type { WSMessage } from "../lib/types";

function createWs(overrides: Partial<{
  messages: WSMessage[];
  isConnected: boolean;
  reconnectExhausted: boolean;
  clearMessages: () => void;
}> = {}) {
  return {
    messages: [],
    isConnected: false,
    reconnectExhausted: false,
    clearMessages: vi.fn(),
    ...overrides,
  };
}

function createAutomation(
  overrides: Partial<{
    isRunning: boolean;
    jobId: string | null;
    progress: { current: number; total: number };
    versions: Array<{ name: string; status: "pending" | "running" | "success" | "failed" | "cancelled" }>;
    error: string | null;
    wsUrl: string | null;
    polledMessages: WSMessage[];
    startRun: () => Promise<void>;
    handleMessage: (message: WSMessage) => void;
    pollJobStatus: (sidecarUrl: string, jobId: string) => Promise<void>;
    reset: () => void;
    cancelJob: (sidecarUrl: string) => Promise<void>;
  }> = {}
) {
  return {
    isRunning: false,
    jobId: null,
    progress: { current: 0, total: 0 },
    versions: [],
    error: null,
    wsUrl: null,
    polledMessages: [],
    startRun: vi.fn(async () => undefined),
    handleMessage: vi.fn(),
    pollJobStatus: vi.fn(async () => undefined),
    reset: vi.fn(),
    cancelJob: vi.fn(async () => undefined),
    ...overrides,
  };
}

describe("useAutomationPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("processes only new websocket messages and supports onMessage callback", () => {
    const first: WSMessage = { type: "status", job_id: "job-1", status: "running" };
    const second: WSMessage = { type: "progress", current: 1, total: 2, version_name: "A" };
    const third: WSMessage = { type: "status", job_id: "job-1", status: "success" };

    let ws = createWs({ messages: [first, second] });
    const automation = createAutomation();
    const onMessage = vi.fn();

    const { rerender } = renderHook(() =>
      useAutomationPanel({
        ws,
        automation,
        sidecarUrl: null,
        onMessage,
      })
    );

    expect(automation.handleMessage).toHaveBeenCalledTimes(2);
    expect(onMessage).toHaveBeenCalledTimes(2);

    ws = createWs({ ...ws, messages: [first, second, third] });
    rerender();

    expect(automation.handleMessage).toHaveBeenCalledTimes(3);
    expect(automation.handleMessage).toHaveBeenLastCalledWith(third);
    expect(onMessage).toHaveBeenCalledTimes(3);
    expect(onMessage).toHaveBeenLastCalledWith(third);
  });

  it("polls every 2 seconds while running and stops on cleanup", () => {
    vi.useFakeTimers();
    const ws = createWs();
    const automation = createAutomation({
      isRunning: true,
      jobId: "job-123",
      pollJobStatus: vi.fn(async () => undefined),
    });

    const { unmount } = renderHook(() =>
      useAutomationPanel({
        ws,
        automation,
        sidecarUrl: "http://127.0.0.1:8080",
      })
    );

    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(automation.pollJobStatus).toHaveBeenCalledTimes(2);
    expect(automation.pollJobStatus).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8080", "job-123");
    expect(automation.pollJobStatus).toHaveBeenNthCalledWith(2, "http://127.0.0.1:8080", "job-123");

    unmount();

    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(automation.pollJobStatus).toHaveBeenCalledTimes(2);
  });

  it("merges polled messages only when configured and websocket has no log entries", () => {
    const statusOnly: WSMessage = { type: "status", job_id: "job-2", status: "running" };
    const wsLog: WSMessage = { type: "log", level: "INFO", message: "ws", timestamp: "t1" };
    const polledLog: WSMessage = { type: "log", level: "INFO", message: "polled", timestamp: "t2" };

    let ws = createWs({ messages: [statusOnly], isConnected: true });
    const automation = createAutomation({ polledMessages: [polledLog] });
    const onLogStateChange = vi.fn();

    const { rerender } = renderHook(() =>
      useAutomationPanel({
        ws,
        automation,
        sidecarUrl: null,
        onLogStateChange,
        includePolledMessagesWhenNoWsLogs: true,
      })
    );

    expect(onLogStateChange).toHaveBeenLastCalledWith({
      messages: [statusOnly, polledLog],
      isConnected: true,
      clearMessages: ws.clearMessages,
    });

    ws = createWs({ ...ws, messages: [wsLog] });
    rerender();

    expect(onLogStateChange).toHaveBeenLastCalledWith({
      messages: [wsLog],
      isConnected: true,
      clearMessages: ws.clearMessages,
    });
  });

  it("tracks connection history and exposes reset helpers", () => {
    const first: WSMessage = { type: "status", job_id: "job-3", status: "running" };
    let ws = createWs({ messages: [first], isConnected: false });
    const automation = createAutomation();

    const { result, rerender } = renderHook(() =>
      useAutomationPanel({
        ws,
        automation,
        sidecarUrl: null,
      })
    );

    expect(result.current.hasConnectedRef.current).toBe(false);
    expect(automation.handleMessage).toHaveBeenCalledTimes(1);

    ws = createWs({ ...ws, isConnected: true });
    rerender();
    expect(result.current.hasConnectedRef.current).toBe(true);

    act(() => {
      result.current.resetProcessedCount();
    });

    ws = createWs({ ...ws, messages: [...ws.messages] });
    rerender();
    expect(automation.handleMessage).toHaveBeenCalledTimes(2);

    act(() => {
      result.current.resetTracking();
    });
    expect(result.current.hasConnectedRef.current).toBe(false);
  });
});
