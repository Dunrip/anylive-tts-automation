import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "../App";

vi.mock("../hooks/useSidecar", () => ({
  useSidecar: () => ({
    port: 8765,
    sidecarUrl: "http://127.0.0.1:8765",
    isReady: true,
    error: null,
  }),
}));

vi.mock("../hooks/useKeyboardShortcuts", () => ({
  useKeyboardShortcuts: vi.fn(),
}));

describe("App - SetupWizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  it("shows SetupWizard when Chromium not installed", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: false, path: null }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("onboarding")).toBeTruthy();
    });
  });

  it("shows onboarding login step when chromium installed but session invalid", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("onboarding")).toBeTruthy();
    });
  });
});

describe("App - Re-login", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  it("passes onRelogin to Sidebar when session expired", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("relogin-button")).toBeTruthy();
    });
  });

  it("re-login button triggers POST to /api/session/login", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session/login") && options?.method === "POST") {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: "ok",
              display_name: "Test User",
              email: "test@example.com",
            }),
        });
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("relogin-button")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("relogin-button"));

    await waitFor(() => {
      const loginCalls = mockFetch.mock.calls.filter(
        (call) =>
          typeof call[0] === "string" &&
          call[0].includes("/api/session/login") &&
          call[1]?.method === "POST"
      );
      expect(loginCalls.length).toBeGreaterThan(0);
    });
  });

  it("session re-fetched and sidebar updated after login success", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    let sessionValid = false;

    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session/login") && options?.method === "POST") {
        sessionValid = true;
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: "ok",
              display_name: "Test User",
              email: "test@example.com",
            }),
        });
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: sessionValid,
              display_name: sessionValid ? "Test User" : null,
              email: sessionValid ? "test@example.com" : null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("relogin-button")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("relogin-button"));

    await waitFor(() => {
      expect(screen.getByText("Test User")).toBeTruthy();
    });
  });

  it("does not pass onRelogin when login is in progress", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session/login")) {
        return new Promise(() => {});
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("relogin-button")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("relogin-button"));

    await waitFor(() => {
      const reloginBtn = screen.queryByTestId("relogin-button");
      if (reloginBtn) {
        expect((reloginBtn as HTMLButtonElement).disabled).toBe(true);
      }
    });
  });

  it("shows inline error message after login failure", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session/login") && options?.method === "POST") {
        return Promise.reject(new Error("Network error"));
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("relogin-button")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("relogin-button"));

    await waitFor(() => {
      expect(screen.getByTestId("login-error")).toBeTruthy();
    });
  });

  it("clears login error on retry attempt", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    let loginCallCount = 0;

    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session/login") && options?.method === "POST") {
        loginCallCount += 1;
        if (loginCallCount === 1) {
          return Promise.reject(new Error("Network error"));
        }
        return new Promise(() => {}); // second attempt: never resolves (stays in progress)
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("relogin-button")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("relogin-button"));

    await waitFor(() => {
      expect(screen.getByTestId("login-error")).toBeTruthy();
    });

    await waitFor(() => {
      expect(screen.getByTestId("relogin-button")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("relogin-button"));

    await waitFor(() => {
      expect(screen.queryByTestId("login-error")).toBeNull();
    });
  });

  it("handles login error gracefully", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session/login") && options?.method === "POST") {
        return Promise.reject(new Error("Network error"));
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("relogin-button")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("relogin-button"));

    await waitFor(() => {
      const reloginBtn = screen.getByTestId("relogin-button");
      expect((reloginBtn as HTMLButtonElement).disabled).toBe(false);
    });
  });
});

describe("App - Session Management", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  it("fetches configs on mount", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default", "client1", "client2"]),
        });
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      const configsCalls = mockFetch.mock.calls.filter(
        (call) => typeof call[0] === "string" && call[0].includes("/api/configs")
      );
      expect(configsCalls.length).toBeGreaterThan(0);
    });
  });

  it("fetches session status for selected client", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session/default/tts")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: true,
              display_name: "Test User",
              email: "test@example.com",
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      const sessionCalls = mockFetch.mock.calls.filter(
        (call) => typeof call[0] === "string" && call[0].includes("/api/session/default/tts")
      );
      expect(sessionCalls.length).toBeGreaterThan(0);
    });
  });

  it("retains default client list when configs fetch fails", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.reject(new TypeError("Failed to fetch"));
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(mockFetch.mock.calls.some((call) => String(call[0]).includes("/api/configs"))).toBe(true);
    });
    expect(screen.getByTestId("onboarding")).toBeTruthy();
  });

  it("retains invalid session state when session fetch fails", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session")) {
        return Promise.reject(new TypeError("Failed to fetch"));
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(mockFetch.mock.calls.some((call) => String(call[0]).includes("/api/session"))).toBe(true);
    });
    await waitFor(() => {
      expect(screen.getByTestId("onboarding")).toBeTruthy();
    });
  });

  it("shows sidecar config error banner when configs fetch fails", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.reject(new TypeError("Failed to fetch"));
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("sidecar-config-error")).toBeInTheDocument();
    });
  });

  it("does not force chromiumInstalled to true when chromium-status fetch fails (leaves null)", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.reject(new TypeError("Failed to fetch"));
      }
      if (url.includes("/api/configs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["default"]),
        });
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
      expect(calls.some((c) => String(c[0]).includes("/api/setup/chromium-status"))).toBe(true);
      expect(calls.some((c) => String(c[0]).includes("/api/session"))).toBe(true);
    });

    expect(screen.queryByTestId("onboarding")).not.toBeInTheDocument();
  });

  it("does not show sidecar config error when configs fetch is aborted (AbortError)", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/setup/chromium-status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ installed: true, path: "/usr/bin/chromium" }),
        });
      }
      if (url.includes("/api/configs")) {
        return Promise.reject(new DOMException("aborted", "AbortError"));
      }
      if (url.includes("/api/session")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              valid: false,
              display_name: null,
              email: null,
              site: "tts",
              client: "default",
              checked_at: new Date().toISOString(),
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<App />);

    await waitFor(() => {
      expect(mockFetch.mock.calls.some((call) => String(call[0]).includes("/api/configs"))).toBe(true);
    });
    expect(screen.queryByTestId("sidecar-config-error")).not.toBeInTheDocument();
  });
});
