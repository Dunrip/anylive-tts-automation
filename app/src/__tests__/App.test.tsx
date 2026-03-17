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
      expect(screen.getByTestId("setup-wizard")).toBeTruthy();
    });
  });

  it("does not show SetupWizard when Chromium is installed", async () => {
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
      expect(screen.queryByTestId("setup-wizard")).toBeNull();
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
});
