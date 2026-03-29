import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MainContent } from "../components/layout/MainContent";
import type { WSMessage } from "../lib/types";

type LogState = { messages: WSMessage[]; isConnected: boolean; clearMessages: () => void };

let capturedTtsSave: ((url: string) => void) | undefined;
let capturedLiveSave: ((url: string) => void) | undefined;
let capturedTtsLog: ((logState: LogState) => void) | undefined;
let capturedFaqLog: ((logState: LogState) => void) | undefined;
let capturedScriptsLog: ((logState: LogState) => void) | undefined;

vi.mock("../components/tts/TTSPanel", () => ({
  TTSPanel: ({
    onBaseUrlChange,
    onLogStateChange,
  }: {
    onBaseUrlChange?: (url: string) => void;
    onLogStateChange?: (logState: LogState) => void;
  }) => {
    capturedTtsSave = onBaseUrlChange;
    capturedTtsLog = onLogStateChange;
    return <div data-testid="tts-panel" />;
  },
}));

vi.mock("../components/faq/FAQPanel", () => ({
  FAQPanel: ({
    onBaseUrlChange,
    onLogStateChange,
  }: {
    onBaseUrlChange?: (url: string) => void;
    onLogStateChange?: (logState: LogState) => void;
  }) => {
    capturedLiveSave = onBaseUrlChange;
    capturedFaqLog = onLogStateChange;
    return <div data-testid="faq-panel" />;
  },
}));

vi.mock("../components/scripts/ScriptsPanel", () => ({
  ScriptsPanel: ({
    onLogStateChange,
  }: {
    onLogStateChange?: (logState: LogState) => void;
  }) => {
    capturedScriptsLog = onLogStateChange;
    return <div data-testid="scripts-panel" />;
  },
}));

vi.mock("../components/history/HistoryPanel", () => ({
  HistoryPanel: () => <div data-testid="history-panel" />,
}));

vi.mock("../components/settings/SettingsPanel", () => ({
  SettingsPanel: () => <div data-testid="settings-panel" />,
}));

vi.mock("../components/layout/LogViewer", () => ({
  LogViewer: ({
    messages,
    isConnected,
  }: {
    messages: WSMessage[];
    isConnected: boolean;
    onClear: () => void;
  }) => (
    <div
      data-testid="log-viewer"
      data-messages-count={String(messages.length)}
      data-connected={String(isConnected)}
    />
  ),
}));

const SIDECAR_URL = "http://127.0.0.1:8765";
const CLIENT = "default";

const makeFakeMsg = (message: string): WSMessage => ({
  type: "log",
  level: "INFO",
  message,
  timestamp: "2026-01-01T00:00:00Z",
});

const noopClear = () => undefined;

function resetCaptures() {
  capturedTtsSave = undefined;
  capturedLiveSave = undefined;
  capturedTtsLog = undefined;
  capturedFaqLog = undefined;
  capturedScriptsLog = undefined;
}

describe("MainContent — error state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetCaptures();
    globalThis.fetch = vi.fn();
  });

  it("shows error banner when initial config load fails", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(
      new TypeError("Failed to fetch")
    );

    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    await waitFor(() => {
      expect(screen.getByTestId("main-content-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("main-content-error").textContent).toContain(
      "Failed to load configuration"
    );
  });

  it("error banner is absent when config loads successfully", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          tts: { base_url: "https://example.com/tts" },
          live: { base_url: "https://example.com/live" },
        }),
    });

    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    await waitFor(() => {
      expect(screen.getByTestId("tts-panel")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("main-content-error")).not.toBeInTheDocument();
  });

  it("does not show error when config fetch is aborted (AbortError)", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(
      new DOMException("aborted", "AbortError")
    );

    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    await new Promise((resolve) => setTimeout(resolve, 10));

    expect(screen.queryByTestId("main-content-error")).not.toBeInTheDocument();
  });

  it("clears error banner when client changes and next load succeeds", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            tts: { base_url: "https://example.com/tts" },
            live: {},
          }),
      });

    const { rerender } = render(
      <MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />
    );

    await waitFor(() => {
      expect(screen.getByTestId("main-content-error")).toBeInTheDocument();
    });

    rerender(<MainContent activePanel="tts" client="client2" sidecarUrl={SIDECAR_URL} />);

    await waitFor(() => {
      expect(screen.queryByTestId("main-content-error")).not.toBeInTheDocument();
    });
  });
});

describe("MainContent — TTS URL optimistic revert", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetCaptures();
    globalThis.fetch = vi.fn();
  });

  it("shows error when TTS URL save fails", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ tts: { base_url: "https://initial.com/tts" }, live: {} }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tts: { base_url: "https://initial.com/tts" }, live: {} }),
      })
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));

    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    await waitFor(() => {
      expect(capturedTtsSave).toBeDefined();
    });

    capturedTtsSave!("https://new.com/tts");

    await waitFor(() => {
      expect(screen.getByTestId("main-content-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("main-content-error").textContent).toContain(
      "Failed to save TTS URL"
    );
  });
});

describe("MainContent — URL save race condition", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetCaptures();
    globalThis.fetch = vi.fn();
  });

  it("rapid second TTS URL save aborts in-flight first save (last-write-wins)", async () => {
    let putASignal: AbortSignal | null | undefined;

    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tts: { base_url: "" }, live: {} }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tts: {}, live: {} }),
      })
      .mockImplementationOnce((_url: string, options?: RequestInit) => {
        putASignal = options?.signal;
        return new Promise<Response>((_, reject) => {
          if (options?.signal?.aborted) {
            reject(new DOMException("aborted", "AbortError"));
            return;
          }
          options?.signal?.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        });
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tts: {}, live: {} }),
      })
      .mockResolvedValueOnce({ ok: true });

    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);
    await waitFor(() => expect(capturedTtsSave).toBeDefined());

    capturedTtsSave!("https://url-a.example.com");
    await waitFor(() =>
      expect((globalThis.fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(3)
    );

    capturedTtsSave!("https://url-b.example.com");
    await waitFor(() => expect(putASignal?.aborted).toBe(true));

    await waitFor(() =>
      expect((globalThis.fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(5)
    );
    expect(screen.queryByTestId("main-content-error")).not.toBeInTheDocument();
  });

  it("rapid second live URL save aborts in-flight first save (last-write-wins)", async () => {
    let putASignal: AbortSignal | null | undefined;

    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tts: {}, live: { base_url: "" } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tts: {}, live: {} }),
      })
      .mockImplementationOnce((_url: string, options?: RequestInit) => {
        putASignal = options?.signal;
        return new Promise<Response>((_, reject) => {
          if (options?.signal?.aborted) {
            reject(new DOMException("aborted", "AbortError"));
            return;
          }
          options?.signal?.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        });
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tts: {}, live: {} }),
      })
      .mockResolvedValueOnce({ ok: true });

    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);
    await waitFor(() => expect(capturedLiveSave).toBeDefined());

    capturedLiveSave!("https://live-url-a.example.com");
    await waitFor(() =>
      expect((globalThis.fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(3)
    );

    capturedLiveSave!("https://live-url-b.example.com");
    await waitFor(() => expect(putASignal?.aborted).toBe(true));

    await waitFor(() =>
      expect((globalThis.fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(5)
    );
    expect(screen.queryByTestId("main-content-error")).not.toBeInTheDocument();
  });
});

describe("MainContent — URL save debounce", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetCaptures();
    globalThis.fetch = vi.fn();
  });

  it("rapid TTS URL saves within debounce window fire only one GET+PUT, not one per call", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tts: { base_url: "" }, live: {} }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tts: {}, live: {} }),
      })
      .mockResolvedValueOnce({ ok: true });

    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    await waitFor(() =>
      expect((globalThis.fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(1)
    );

    act(() => {
      capturedTtsSave!("https://url-a.example.com");
      capturedTtsSave!("https://url-b.example.com");
      capturedTtsSave!("https://url-c.example.com");
    });

    expect((globalThis.fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(1);

    await waitFor(
      () => expect((globalThis.fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(3),
      { timeout: 2000 }
    );

    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls as [string, RequestInit?][];
    const putCall = calls.find((c) => c[1]?.method === "PUT");
    expect(putCall).toBeDefined();
    const body = JSON.parse(putCall![1]!.body as string) as Record<string, unknown>;
    expect((body.tts as Record<string, unknown>)?.base_url).toBe("https://url-c.example.com");

    expect(screen.queryByTestId("main-content-error")).not.toBeInTheDocument();
  });

  it("rapid live URL saves within debounce window fire only one GET+PUT, not one per call", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tts: {}, live: { base_url: "" } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tts: {}, live: {} }),
      })
      .mockResolvedValueOnce({ ok: true });

    render(<MainContent activePanel="faq" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    await waitFor(() =>
      expect((globalThis.fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(1)
    );

    act(() => {
      capturedLiveSave!("https://live-a.example.com");
      capturedLiveSave!("https://live-b.example.com");
      capturedLiveSave!("https://live-c.example.com");
    });

    expect((globalThis.fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(1);

    await waitFor(
      () => expect((globalThis.fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalledTimes(3),
      { timeout: 2000 }
    );

    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls as [string, RequestInit?][];
    const putCall = calls.find((c) => c[1]?.method === "PUT");
    expect(putCall).toBeDefined();
    const body = JSON.parse(putCall![1]!.body as string) as Record<string, unknown>;
    expect((body.live as Record<string, unknown>)?.base_url).toBe("https://live-c.example.com");

    expect(screen.queryByTestId("main-content-error")).not.toBeInTheDocument();
  });
});

describe("MainContent — panel-keyed log state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetCaptures();
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ tts: {}, live: {} }),
    });
  });

  it("LogViewer shows 0 messages by default when no panel has fired log state", async () => {
    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);
    await waitFor(() => expect(capturedTtsLog).toBeDefined());

    expect(screen.getByTestId("log-viewer").getAttribute("data-messages-count")).toBe("0");
  });

  it("TTS log state is isolated — switching to FAQ shows 0 messages (not TTS logs)", async () => {
    const { rerender } = render(
      <MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />
    );
    await waitFor(() => expect(capturedTtsLog).toBeDefined());

    act(() => {
      capturedTtsLog!({
        messages: [makeFakeMsg("tts-msg-1"), makeFakeMsg("tts-msg-2")],
        isConnected: true,
        clearMessages: noopClear,
      });
    });

    expect(screen.getByTestId("log-viewer").getAttribute("data-messages-count")).toBe("2");

    rerender(<MainContent activePanel="faq" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    expect(screen.getByTestId("log-viewer").getAttribute("data-messages-count")).toBe("0");
  });

  it("FAQ log state does not overwrite TTS log state", async () => {
    const { rerender } = render(
      <MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />
    );
    await waitFor(() => expect(capturedTtsLog).toBeDefined());
    await waitFor(() => expect(capturedFaqLog).toBeDefined());

    act(() => {
      capturedTtsLog!({
        messages: [makeFakeMsg("tts-only")],
        isConnected: false,
        clearMessages: noopClear,
      });
      capturedFaqLog!({
        messages: [makeFakeMsg("faq-a"), makeFakeMsg("faq-b"), makeFakeMsg("faq-c")],
        isConnected: true,
        clearMessages: noopClear,
      });
    });

    expect(screen.getByTestId("log-viewer").getAttribute("data-messages-count")).toBe("1");

    rerender(<MainContent activePanel="faq" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    expect(screen.getByTestId("log-viewer").getAttribute("data-messages-count")).toBe("3");

    rerender(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    expect(screen.getByTestId("log-viewer").getAttribute("data-messages-count")).toBe("1");
  });

  it("scripts panel log state is isolated from tts and faq", async () => {
    const { rerender } = render(
      <MainContent activePanel="scripts" client={CLIENT} sidecarUrl={SIDECAR_URL} />
    );
    await waitFor(() => expect(capturedScriptsLog).toBeDefined());
    await waitFor(() => expect(capturedTtsLog).toBeDefined());

    act(() => {
      capturedTtsLog!({
        messages: [makeFakeMsg("tts-msg")],
        isConnected: false,
        clearMessages: noopClear,
      });
      capturedScriptsLog!({
        messages: [makeFakeMsg("scripts-a"), makeFakeMsg("scripts-b")],
        isConnected: true,
        clearMessages: noopClear,
      });
    });

    expect(screen.getByTestId("log-viewer").getAttribute("data-messages-count")).toBe("2");

    rerender(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    expect(screen.getByTestId("log-viewer").getAttribute("data-messages-count")).toBe("1");
  });

  it("isConnected reflects active panel connection state, not other panels", async () => {
    const { rerender } = render(
      <MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />
    );
    await waitFor(() => expect(capturedTtsLog).toBeDefined());
    await waitFor(() => expect(capturedFaqLog).toBeDefined());

    act(() => {
      capturedTtsLog!({ messages: [], isConnected: true, clearMessages: noopClear });
      capturedFaqLog!({ messages: [], isConnected: false, clearMessages: noopClear });
    });

    expect(screen.getByTestId("log-viewer").getAttribute("data-connected")).toBe("true");

    rerender(<MainContent activePanel="faq" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    expect(screen.getByTestId("log-viewer").getAttribute("data-connected")).toBe("false");
  });
});

describe("MainContent — config load branches", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetCaptures();
    globalThis.fetch = vi.fn();
  });

  it("shows error banner when config returns non-ok HTTP status", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    });
    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);
    await waitFor(() =>
      expect(screen.getByTestId("main-content-error")).toBeInTheDocument()
    );
    expect(screen.getByTestId("main-content-error").textContent).toContain(
      "Failed to load configuration"
    );
  });

  it("does not set URLs or show error when config data is not an object", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(null),
    });
    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByTestId("main-content-error")).not.toBeInTheDocument();
  });

  it("does not set tts URL when tts.base_url is not a string", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ tts: { base_url: 42 }, live: { base_url: ["bad"] } }),
    });
    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByTestId("main-content-error")).not.toBeInTheDocument();
  });

  it("error dismiss button clears the error banner", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(
      new TypeError("Network error")
    );
    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />);
    await waitFor(() =>
      expect(screen.getByTestId("main-content-error")).toBeInTheDocument()
    );
    const dismissBtn = screen
      .getByTestId("main-content-error")
      .querySelector("button") as HTMLButtonElement;
    fireEvent.click(dismissBtn);
    expect(screen.queryByTestId("main-content-error")).not.toBeInTheDocument();
  });
});

describe("MainContent — live URL save", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetCaptures();
    globalThis.fetch = vi.fn();
  });

  it("shows error when live URL save fails", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ tts: {}, live: { base_url: "https://initial.com/live" } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ tts: {}, live: { base_url: "https://initial.com/live" } }),
      })
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));

    render(<MainContent activePanel="faq" client={CLIENT} sidecarUrl={SIDECAR_URL} />);
    await waitFor(() => expect(capturedLiveSave).toBeDefined());

    capturedLiveSave!("https://new.com/live");

    await waitFor(() =>
      expect(screen.getByTestId("main-content-error")).toBeInTheDocument()
    );
    expect(screen.getByTestId("main-content-error").textContent).toContain(
      "Failed to save live URL"
    );
  });
});

describe("MainContent — panel switching and DEFAULT_LOG_STATE", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetCaptures();
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ tts: {}, live: {} }),
    });
  });

  it("history panel active uses DEFAULT_LOG_STATE: 0 messages, not connected", () => {
    render(<MainContent activePanel="history" client={CLIENT} sidecarUrl={SIDECAR_URL} />);
    expect(
      screen.getByTestId("log-viewer").getAttribute("data-messages-count")
    ).toBe("0");
    expect(
      screen.getByTestId("log-viewer").getAttribute("data-connected")
    ).toBe("false");
  });

  it("settings panel active uses DEFAULT_LOG_STATE: 0 messages, not connected", () => {
    render(<MainContent activePanel="settings" client={CLIENT} sidecarUrl={SIDECAR_URL} />);
    expect(
      screen.getByTestId("log-viewer").getAttribute("data-messages-count")
    ).toBe("0");
    expect(
      screen.getByTestId("log-viewer").getAttribute("data-connected")
    ).toBe("false");
  });

  it("switching from tts (with logs) to history shows DEFAULT_LOG_STATE", async () => {
    const { rerender } = render(
      <MainContent activePanel="tts" client={CLIENT} sidecarUrl={SIDECAR_URL} />
    );
    await waitFor(() => expect(capturedTtsLog).toBeDefined());

    act(() => {
      capturedTtsLog!({
        messages: [makeFakeMsg("tts-msg")],
        isConnected: true,
        clearMessages: noopClear,
      });
    });

    expect(
      screen.getByTestId("log-viewer").getAttribute("data-messages-count")
    ).toBe("1");

    rerender(<MainContent activePanel="history" client={CLIENT} sidecarUrl={SIDECAR_URL} />);

    expect(
      screen.getByTestId("log-viewer").getAttribute("data-messages-count")
    ).toBe("0");
    expect(
      screen.getByTestId("log-viewer").getAttribute("data-connected")
    ).toBe("false");
  });
});

describe("MainContent — save guard with no sidecarUrl", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetCaptures();
    globalThis.fetch = vi.fn();
  });

  it("saveTtsBaseUrl without sidecarUrl: optimistic state update, no fetch fired", () => {
    render(<MainContent activePanel="tts" client={CLIENT} sidecarUrl={undefined} />);
    expect(capturedTtsSave).toBeDefined();

    capturedTtsSave!("https://optimistic.example.com");

    expect(
      (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length
    ).toBe(0);
    expect(screen.queryByTestId("main-content-error")).not.toBeInTheDocument();
  });
});
