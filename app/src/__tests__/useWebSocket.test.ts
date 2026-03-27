import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWebSocket } from "../hooks/useWebSocket";

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 0;

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }

  send = vi.fn();

  close = vi.fn(() => {
    this.readyState = 3;
    this.onclose?.();
  });

  open(): void {
    this.readyState = 1;
    this.onopen?.();
  }

  simulateMessage(data: unknown): void {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  simulateRawMessage(raw: string): void {
    this.onmessage?.({ data: raw });
  }
}

describe("useWebSocket", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("starts disconnected when URL is null", () => {
    const { result } = renderHook(() => useWebSocket(null));

    expect(result.current.isConnected).toBe(false);
    expect(result.current.messages).toHaveLength(0);
  });

  it("connects and receives messages", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost:8080/ws"));

    act(() => {
      MockWebSocket.instances[0].open();
    });

    expect(result.current.isConnected).toBe(true);

    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: "log",
        level: "INFO",
        message: "Connected",
        timestamp: "2026-01-01T00:00:00Z",
      });
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({ type: "log", message: "Connected" });
  });

  it("ignores ping and malformed payloads", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost:8080/ws"));

    act(() => {
      MockWebSocket.instances[0].simulateMessage({ type: "ping" });
      MockWebSocket.instances[0].simulateRawMessage("not-json");
    });

    expect(result.current.messages).toHaveLength(0);
  });

  it("caps message buffer at 5000", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost:8080/ws"));

    act(() => {
      for (let index = 0; index < 5002; index += 1) {
        MockWebSocket.instances[0].simulateMessage({
          type: "log",
          level: "INFO",
          message: `m-${index}`,
          timestamp: `2026-01-01T00:00:${String(index).padStart(2, "0")}Z`,
        });
      }
    });

    expect(result.current.messages).toHaveLength(5000);
    expect(result.current.messages[0]).toMatchObject({ message: "m-2" });
    expect(result.current.messages[4999]).toMatchObject({ message: "m-5001" });
  });

  it("clears messages", () => {
    const { result } = renderHook(() => useWebSocket("ws://localhost:8080/ws"));

    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: "log",
        level: "WARN",
        message: "Will clear",
        timestamp: "2026-01-01T00:00:00Z",
      });
    });

    expect(result.current.messages).toHaveLength(1);

    act(() => {
      result.current.clearMessages();
    });

    expect(result.current.messages).toHaveLength(0);
  });

  it("reconnects after close", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useWebSocket("ws://localhost:8080/ws"));

    act(() => {
      MockWebSocket.instances[0].open();
    });

    expect(result.current.isConnected).toBe(true);

    act(() => {
      MockWebSocket.instances[0].close();
    });

    expect(result.current.isConnected).toBe(false);

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it("uses exponential backoff delays on reconnect", () => {
    vi.useFakeTimers();
    renderHook(() => useWebSocket("ws://localhost:8080/ws"));

    const expectedDelays = [1000, 2000, 4000, 8000, 16000, 30000];

    for (let i = 0; i < expectedDelays.length; i++) {
      act(() => {
        MockWebSocket.instances[i].close();
      });

      act(() => {
        vi.advanceTimersByTime(expectedDelays[i] - 1);
      });
      expect(MockWebSocket.instances).toHaveLength(i + 1);

      act(() => {
        vi.advanceTimersByTime(1);
      });
      expect(MockWebSocket.instances).toHaveLength(i + 2);
    }
  });

  it("stops reconnecting after 10 failed attempts", () => {
    vi.useFakeTimers();
    renderHook(() => useWebSocket("ws://localhost:8080/ws"));

    for (let i = 0; i <= 10; i++) {
      act(() => {
        MockWebSocket.instances[i].close();
      });
      act(() => {
        vi.advanceTimersByTime(30001);
      });
    }

    expect(MockWebSocket.instances).toHaveLength(11);

    act(() => {
      vi.advanceTimersByTime(60000);
    });
    expect(MockWebSocket.instances).toHaveLength(11);
  });

  it("resets backoff counter after successful connection", () => {
    vi.useFakeTimers();
    renderHook(() => useWebSocket("ws://localhost:8080/ws"));

    act(() => {
      MockWebSocket.instances[0].close();
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    act(() => {
      MockWebSocket.instances[1].close();
    });
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(MockWebSocket.instances).toHaveLength(3);

    act(() => {
      MockWebSocket.instances[2].open();
    });

    act(() => {
      MockWebSocket.instances[2].close();
    });

    act(() => {
      vi.advanceTimersByTime(999);
    });
    expect(MockWebSocket.instances).toHaveLength(3);

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(MockWebSocket.instances).toHaveLength(4);
  });
});
