import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { Onboarding } from "../components/common/Onboarding";

const SIDECAR = "http://127.0.0.1:8080";

describe("Onboarding", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  async function renderAtChromiumStep(onComplete = vi.fn()) {
    vi.useFakeTimers();
    render(
      <Onboarding
        sidecarUrl={SIDECAR}
        chromiumInstalled={false}
        sessionValid={false}
        onComplete={onComplete}
      />
    );
    await act(async () => { vi.advanceTimersByTime(1200); });
    vi.useRealTimers();
    return onComplete;
  }

  async function renderAtLoginStep(onComplete = vi.fn()) {
    vi.useFakeTimers();
    render(
      <Onboarding
        sidecarUrl={SIDECAR}
        chromiumInstalled={true}
        sessionValid={false}
        onComplete={onComplete}
      />
    );
    await act(async () => { vi.advanceTimersByTime(1200); });
    vi.useRealTimers();
    return onComplete;
  }

  describe("check step - initial render", () => {
    it("renders the onboarding overlay", () => {
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={false} sessionValid={false} onComplete={vi.fn()} />);
      expect(screen.getByTestId("onboarding")).toBeTruthy();
    });

    it("shows all three step labels", () => {
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={false} sessionValid={false} onComplete={vi.fn()} />);
      expect(screen.getByText("Environment")).toBeTruthy();
      expect(screen.getByText("Browser")).toBeTruthy();
      expect(screen.getByText("Login")).toBeTruthy();
    });

    it("shows sidecar connected row", () => {
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={false} sessionValid={false} onComplete={vi.fn()} />);
      expect(screen.getByText("Sidecar connected")).toBeTruthy();
    });

    it("shows Checking Chromium when not installed", () => {
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={false} sessionValid={false} onComplete={vi.fn()} />);
      expect(screen.getByText("Checking Chromium...")).toBeTruthy();
    });

    it("shows Chromium browser ready when installed", () => {
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={true} sessionValid={false} onComplete={vi.fn()} />);
      expect(screen.getByText("Chromium browser ready")).toBeTruthy();
    });

    it("shows Login required when session invalid", () => {
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={false} sessionValid={false} onComplete={vi.fn()} />);
      expect(screen.getByText("Login required")).toBeTruthy();
    });

    it("shows Session active when session valid", () => {
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={true} sessionValid={true} onComplete={vi.fn()} />);
      expect(screen.getByText("Session active")).toBeTruthy();
    });
  });

  describe("step auto-advance", () => {
    it("advances to chromium step when chromium not installed", async () => {
      vi.useFakeTimers();
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={false} sessionValid={false} onComplete={vi.fn()} />);
      await act(async () => { vi.advanceTimersByTime(1200); });
      expect(screen.getByTestId("install-chromium-button")).toBeTruthy();
    });

    it("advances to login step when chromium installed but session invalid", async () => {
      vi.useFakeTimers();
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={true} sessionValid={false} onComplete={vi.fn()} />);
      await act(async () => { vi.advanceTimersByTime(1200); });
      expect(screen.getByTestId("login-button")).toBeTruthy();
    });

    it("calls onComplete when chromium installed and session valid", async () => {
      vi.useFakeTimers();
      const onComplete = vi.fn();
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={true} sessionValid={true} onComplete={onComplete} />);
      await act(async () => { vi.advanceTimersByTime(1200); });
      expect(onComplete).toHaveBeenCalledWith({ sessionValid: true, displayName: null, email: null });
    });
  });

  describe("chromium install step", () => {
    it("shows install button", async () => {
      await renderAtChromiumStep();
      expect(screen.getByTestId("install-chromium-button")).toBeTruthy();
    });

    it("shows loading text and disables button while installing", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => new Promise(() => {}),
      });
      await renderAtChromiumStep();
      fireEvent.click(screen.getByTestId("install-chromium-button"));
      await waitFor(() => expect(screen.getByText("Installing...")).toBeTruthy());
      expect((screen.getByTestId("install-chromium-button") as HTMLButtonElement).disabled).toBe(true);
    });

    it("shows success message when status=installed", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "installed" }),
      });
      await renderAtChromiumStep();
      fireEvent.click(screen.getByTestId("install-chromium-button"));
      await waitFor(() => expect(screen.getByText("Chromium installed successfully.")).toBeTruthy());
    });

    it("shows success message when status=already_installed", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "already_installed" }),
      });
      await renderAtChromiumStep();
      fireEvent.click(screen.getByTestId("install-chromium-button"));
      await waitFor(() => expect(screen.getByText("Chromium installed successfully.")).toBeTruthy());
    });

    it("shows server error message on failure", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "error", error: "Disk full" }),
      });
      await renderAtChromiumStep();
      fireEvent.click(screen.getByTestId("install-chromium-button"));
      await waitFor(() => expect(screen.getByText("Disk full")).toBeTruthy());
    });

    it("shows fallback error when status is unknown and no error field", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "unknown" }),
      });
      await renderAtChromiumStep();
      fireEvent.click(screen.getByTestId("install-chromium-button"));
      await waitFor(() => expect(screen.getByText("Installation failed. Try again.")).toBeTruthy());
    });

    it("shows connection error when fetch throws", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("Network error"));
      await renderAtChromiumStep();
      fireEvent.click(screen.getByTestId("install-chromium-button"));
      await waitFor(() => expect(screen.getByText("Could not connect to sidecar.")).toBeTruthy());
    });

    it("shows Retry Install button after error", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("Network error"));
      await renderAtChromiumStep();
      fireEvent.click(screen.getByTestId("install-chromium-button"));
      await waitFor(() => expect(screen.getByText("Retry Install")).toBeTruthy());
    });

    it("advances to login step 800ms after successful install", async () => {
      vi.useFakeTimers();
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "installed" }),
      });
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={false} sessionValid={false} onComplete={vi.fn()} />);
      await act(async () => { vi.advanceTimersByTime(1200); });
      fireEvent.click(screen.getByTestId("install-chromium-button"));
      await act(async () => { await vi.runAllTimersAsync(); });
      expect(screen.getByTestId("login-button")).toBeTruthy();
    });
  });

  describe("login step", () => {
    it("shows login button", async () => {
      await renderAtLoginStep();
      expect(screen.getByTestId("login-button")).toBeTruthy();
    });

    it("shows loading text and disables button while waiting", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => new Promise(() => {}),
      });
      await renderAtLoginStep();
      fireEvent.click(screen.getByTestId("login-button"));
      await waitFor(() => expect(screen.getByText("Waiting for login...")).toBeTruthy());
      expect((screen.getByTestId("login-button") as HTMLButtonElement).disabled).toBe(true);
    });

    it("shows welcome message with display name on success", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "ok", display_name: "Alice", email: "alice@example.com" }),
      });
      await renderAtLoginStep();
      fireEvent.click(screen.getByTestId("login-button"));
      await waitFor(() => expect(screen.getByText("Welcome, Alice!")).toBeTruthy());
    });

    it("shows Welcome! without name when display_name is null", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "ok", display_name: null }),
      });
      await renderAtLoginStep();
      fireEvent.click(screen.getByTestId("login-button"));
      await waitFor(() => expect(screen.getByText("Welcome!")).toBeTruthy());
    });

    it("calls onComplete with correct args after 900ms delay", async () => {
      vi.useFakeTimers();
      const onComplete = vi.fn();
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "ok", display_name: "Bob", email: "bob@example.com" }),
      });
      render(<Onboarding sidecarUrl={SIDECAR} chromiumInstalled={true} sessionValid={false} onComplete={onComplete} />);
      await act(async () => { vi.advanceTimersByTime(1200); });
      fireEvent.click(screen.getByTestId("login-button"));
      await act(async () => { await vi.runAllTimersAsync(); });
      expect(onComplete).toHaveBeenCalledWith({
        sessionValid: true,
        displayName: "Bob",
        email: "bob@example.com",
      });
    });

    it("shows login timeout error message", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "timeout" }),
      });
      await renderAtLoginStep();
      fireEvent.click(screen.getByTestId("login-button"));
      await waitFor(() => expect(screen.getByText("Login timed out. Please try again.")).toBeTruthy());
    });

    it("shows server error message", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "error", error: "Account suspended" }),
      });
      await renderAtLoginStep();
      fireEvent.click(screen.getByTestId("login-button"));
      await waitFor(() => expect(screen.getByText("Account suspended")).toBeTruthy());
    });

    it("shows fallback error when no error field present", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "error" }),
      });
      await renderAtLoginStep();
      fireEvent.click(screen.getByTestId("login-button"));
      await waitFor(() => expect(screen.getByText("Login failed. Please try again.")).toBeTruthy());
    });

    it("shows connection error when fetch throws", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("Network error"));
      await renderAtLoginStep();
      fireEvent.click(screen.getByTestId("login-button"));
      await waitFor(() => expect(screen.getByText("Could not connect to sidecar.")).toBeTruthy());
    });

    it("shows Try Again button after login failure", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("Network error"));
      await renderAtLoginStep();
      fireEvent.click(screen.getByTestId("login-button"));
      await waitFor(() => expect(screen.getByText("Try Again")).toBeTruthy());
    });
  });
});
