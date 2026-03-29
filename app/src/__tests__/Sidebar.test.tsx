import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Sidebar } from "../components/layout/Sidebar";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";

const defaultProps = {
  activePanel: "tts" as const,
  onPanelChange: vi.fn(),
  clients: ["default", "mybrand"],
  selectedClient: "default",
  onClientChange: vi.fn(),
  sessionValid: true,
};

describe("Sidebar", () => {
  it("renders all 5 navigation items", () => {
    render(<Sidebar {...defaultProps} />);
    expect(screen.getByTestId("nav-tts")).toBeTruthy();
    expect(screen.getByTestId("nav-faq")).toBeTruthy();
    expect(screen.getByTestId("nav-scripts")).toBeTruthy();
    expect(screen.getByTestId("nav-history")).toBeTruthy();
    expect(screen.getByTestId("nav-settings")).toBeTruthy();
  });

  it("renders client switcher with client list", () => {
    render(<Sidebar {...defaultProps} />);
    const switcher = screen.getByTestId("client-switcher");
    expect(switcher).toBeTruthy();
    expect(screen.getByText("default")).toBeTruthy();
    fireEvent.click(switcher);
    expect(screen.getByText("mybrand")).toBeTruthy();
  });

  it("calls onPanelChange when nav item clicked", () => {
    const onPanelChange = vi.fn();
    render(<Sidebar {...defaultProps} onPanelChange={onPanelChange} />);
    fireEvent.click(screen.getByTestId("nav-faq"));
    expect(onPanelChange).toHaveBeenCalledWith("faq");
  });

  it("shows ready status when sidecar and session are active", () => {
    render(<Sidebar {...defaultProps} sessionValid={true} sidecarUrl="http://127.0.0.1:8765" />);
    expect(screen.getByText("Ready")).toBeTruthy();
    const dot = screen.getByTestId("status-dot");
    expect(dot.className).toContain("bg-[var(--success)]");
  });

  it("shows expired status when sidecar connected but session is invalid", () => {
    render(<Sidebar {...defaultProps} sessionValid={false} sidecarUrl="http://127.0.0.1:8765" />);
    expect(screen.getByText("Session Expired")).toBeTruthy();
    const dot = screen.getByTestId("status-dot");
    expect(dot.className).toContain("bg-[var(--error)]");
  });

  it("shows re-login button when session expired", () => {
    const onRelogin = vi.fn();
    render(
      <Sidebar
        {...defaultProps}
        sessionValid={false}
        sidecarUrl="http://127.0.0.1:8765"
        onRelogin={onRelogin}
      />,
    );
    const reloginBtn = screen.getByTestId("relogin-button");
    expect(reloginBtn).toBeTruthy();
    fireEvent.click(reloginBtn);
    expect(onRelogin).toHaveBeenCalled();
  });

  it("hides re-login button when sidecar is not connected", () => {
    const onRelogin = vi.fn();
    render(<Sidebar {...defaultProps} sessionValid={false} onRelogin={onRelogin} />);
    expect(screen.queryByTestId("relogin-button")).toBeNull();
  });

  it("calls onClientChange when client selected", () => {
    const onClientChange = vi.fn();
    render(<Sidebar {...defaultProps} onClientChange={onClientChange} />);
    const switcher = screen.getByTestId("client-switcher");
    fireEvent.click(switcher);
    const option = screen.getByText("mybrand");
    fireEvent.click(option);
    expect(onClientChange).toHaveBeenCalledWith("mybrand");
  });

  it("shows display name when userDisplayName prop provided and session valid", () => {
    render(
      <Sidebar
        {...defaultProps}
        sessionValid={true}
        sidecarUrl="http://127.0.0.1:8765"
        userDisplayName="Pattanun Chutisavang"
      />,
    );
    expect(screen.getByText("Pattanun Chutisavang")).toBeTruthy();
  });

  it("shows email as detail text when userEmail prop provided and session valid", () => {
    render(
      <Sidebar
        {...defaultProps}
        sessionValid={true}
        sidecarUrl="http://127.0.0.1:8765"
        userEmail="pattanun@anymindgroup.com"
      />,
    );
    expect(screen.getByText("pattanun@anymindgroup.com")).toBeTruthy();
  });

  it("falls back to Ready when neither userDisplayName nor userEmail provided", () => {
    render(
      <Sidebar
        {...defaultProps}
        sessionValid={true}
        sidecarUrl="http://127.0.0.1:8765"
      />,
    );
    expect(screen.getByText("Ready")).toBeTruthy();
  });

  it("does not show email when sidecar is disconnected even if userDisplayName prop is set", () => {
    render(
      <Sidebar
        {...defaultProps}
        sessionValid={true}
        userDisplayName="Pattanun Chutisavang"
        userEmail="pattanun@anymindgroup.com"
      />,
    );
    expect(screen.getByText("Sidecar Connecting")).toBeTruthy();
    expect(screen.queryByText("pattanun@anymindgroup.com")).toBeNull();
  });

  it("renders app version when appVersion prop provided", () => {
    render(<Sidebar {...defaultProps} appVersion="1.2.3" />);
    const versionElement = screen.getByTestId("app-version");
    expect(versionElement).toBeTruthy();
    expect(screen.getByText("v1.2.3")).toBeTruthy();
  });

  it("does not render app version when appVersion prop is undefined", () => {
    render(<Sidebar {...defaultProps} />);
    expect(screen.queryByTestId("app-version")).toBeNull();
  });
});

describe("Sidebar — navigation active state", () => {
  it("marks active nav item with aria-current=page", () => {
    render(<Sidebar {...defaultProps} activePanel="faq" />);
    expect(screen.getByTestId("nav-faq").getAttribute("aria-current")).toBe("page");
    expect(screen.getByTestId("nav-tts").getAttribute("aria-current")).toBeNull();
  });

  it("calls onPanelChange for scripts, history, and settings nav items", () => {
    const onPanelChange = vi.fn();
    render(<Sidebar {...defaultProps} onPanelChange={onPanelChange} />);
    fireEvent.click(screen.getByTestId("nav-scripts"));
    expect(onPanelChange).toHaveBeenCalledWith("scripts");
    fireEvent.click(screen.getByTestId("nav-history"));
    expect(onPanelChange).toHaveBeenCalledWith("history");
    fireEvent.click(screen.getByTestId("nav-settings"));
    expect(onPanelChange).toHaveBeenCalledWith("settings");
  });

  it("calls onPanelChange with tts when tts nav item clicked from another panel", () => {
    const onPanelChange = vi.fn();
    render(<Sidebar {...defaultProps} activePanel="faq" onPanelChange={onPanelChange} />);
    fireEvent.click(screen.getByTestId("nav-tts"));
    expect(onPanelChange).toHaveBeenCalledWith("tts");
  });
});

describe("Sidebar — session indicators", () => {
  it("shows sidecar connecting status and warning dot when sidecarUrl is null", () => {
    render(<Sidebar {...defaultProps} sidecarUrl={null} />);
    expect(screen.getByText("Sidecar Connecting")).toBeTruthy();
    expect(screen.getByTestId("status-dot").className).toContain("bg-[var(--warning)]");
  });

  it("shows login error message when sidecar connected, session expired, and loginError set", () => {
    render(
      <Sidebar
        {...defaultProps}
        sessionValid={false}
        sidecarUrl="http://127.0.0.1:8765"
        loginError="Invalid credentials"
      />,
    );
    expect(screen.getByTestId("login-error")).toBeTruthy();
    expect(screen.getByText("Invalid credentials")).toBeTruthy();
  });

  it("does not show login error when sidecar is not connected", () => {
    render(
      <Sidebar
        {...defaultProps}
        sessionValid={false}
        loginError="Invalid credentials"
      />,
    );
    expect(screen.queryByTestId("login-error")).toBeNull();
  });
});

describe("Sidebar — client create form", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  it("toggles create form open when + New clicked", () => {
    render(<Sidebar {...defaultProps} />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    expect(screen.getByTestId("new-client-input")).toBeTruthy();
    expect(screen.getByTestId("create-client-button")).toBeTruthy();
  });

  it("closes create form when button clicked again (shows Cancel when open)", () => {
    render(<Sidebar {...defaultProps} />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    expect(screen.getByTestId("new-client-input")).toBeTruthy();
    fireEvent.click(screen.getByTestId("new-client-button"));
    expect(screen.queryByTestId("new-client-input")).toBeNull();
  });

  it("create button is disabled when name input is empty", () => {
    render(<Sidebar {...defaultProps} />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    const createBtn = screen.getByTestId("create-client-button") as HTMLButtonElement;
    expect(createBtn.disabled).toBe(true);
  });

  it("create button is enabled after typing a valid name", () => {
    render(<Sidebar {...defaultProps} />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.change(screen.getByTestId("new-client-input"), { target: { value: "newclient" } });
    const createBtn = screen.getByTestId("create-client-button") as HTMLButtonElement;
    expect(createBtn.disabled).toBe(false);
  });

  it("shows validation error for name with invalid characters", async () => {
    render(<Sidebar {...defaultProps} />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.change(screen.getByTestId("new-client-input"), { target: { value: "invalid name!" } });
    fireEvent.click(screen.getByTestId("create-client-button"));
    await waitFor(() =>
      expect(screen.getByText("Use only letters, numbers, hyphens, underscores")).toBeTruthy(),
    );
  });

  it("does nothing when Enter pressed with empty input", () => {
    const onClientCreated = vi.fn();
    render(<Sidebar {...defaultProps} onClientCreated={onClientCreated} />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.keyDown(screen.getByTestId("new-client-input"), { key: "Enter" });
    expect(onClientCreated).not.toHaveBeenCalled();
  });

  it("creates client via sidecar API and calls onClientCreated", async () => {
    const onClientCreated = vi.fn();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({}),
    });
    render(
      <Sidebar
        {...defaultProps}
        sidecarUrl="http://127.0.0.1:8765"
        onClientCreated={onClientCreated}
      />,
    );
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.change(screen.getByTestId("new-client-input"), { target: { value: "newclient" } });
    fireEvent.click(screen.getByTestId("create-client-button"));
    await waitFor(() => expect(onClientCreated).toHaveBeenCalledWith("newclient"));
    expect(screen.queryByTestId("new-client-input")).toBeNull();
  });

  it("creates client via Enter key on input using sidecar API", async () => {
    const onClientCreated = vi.fn();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({}),
    });
    render(
      <Sidebar
        {...defaultProps}
        sidecarUrl="http://127.0.0.1:8765"
        onClientCreated={onClientCreated}
      />,
    );
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.change(screen.getByTestId("new-client-input"), { target: { value: "quickclient" } });
    fireEvent.keyDown(screen.getByTestId("new-client-input"), { key: "Enter" });
    await waitFor(() => expect(onClientCreated).toHaveBeenCalledWith("quickclient"));
  });

  it("creates client via Tauri invoke when no sidecarUrl and calls onClientCreated", async () => {
    const onClientCreated = vi.fn();
    vi.mocked(invoke).mockResolvedValue(undefined);
    render(<Sidebar {...defaultProps} onClientCreated={onClientCreated} />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.change(screen.getByTestId("new-client-input"), { target: { value: "tauriclient" } });
    fireEvent.click(screen.getByTestId("create-client-button"));
    await waitFor(() => expect(onClientCreated).toHaveBeenCalledWith("tauriclient"));
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("create_client_config", { name: "tauriclient" }),
    );
  });

  it("shows error when sidecar API returns non-ok response with detail", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      json: vi.fn().mockResolvedValue({ detail: "Already exists" }),
    });
    render(<Sidebar {...defaultProps} sidecarUrl="http://127.0.0.1:8765" />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.change(screen.getByTestId("new-client-input"), { target: { value: "newclient" } });
    fireEvent.click(screen.getByTestId("create-client-button"));
    await waitFor(() => expect(screen.getByText("Already exists")).toBeTruthy());
  });

  it("shows fallback error when sidecar API returns non-ok with no detail", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      json: vi.fn().mockResolvedValue({}),
    });
    render(<Sidebar {...defaultProps} sidecarUrl="http://127.0.0.1:8765" />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.change(screen.getByTestId("new-client-input"), { target: { value: "newclient" } });
    fireEvent.click(screen.getByTestId("create-client-button"));
    await waitFor(() => expect(screen.getByText("Failed")).toBeTruthy());
  });

  it("shows error when sidecar API fetch throws", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("network error"));
    render(<Sidebar {...defaultProps} sidecarUrl="http://127.0.0.1:8765" />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.change(screen.getByTestId("new-client-input"), { target: { value: "newclient" } });
    fireEvent.click(screen.getByTestId("create-client-button"));
    await waitFor(() => expect(screen.getByText("Could not connect to sidecar")).toBeTruthy());
  });

  it("shows error when Tauri invoke throws during create", async () => {
    vi.mocked(invoke).mockRejectedValue("Failed to create config directory");
    render(<Sidebar {...defaultProps} />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.change(screen.getByTestId("new-client-input"), { target: { value: "newclient" } });
    fireEvent.click(screen.getByTestId("create-client-button"));
    await waitFor(() =>
      expect(screen.getByText("Failed to create config directory")).toBeTruthy(),
    );
  });
});

describe("Sidebar — client delete flow", () => {
  const nonDefaultProps = {
    ...defaultProps,
    selectedClient: "mybrand",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  it("does not show delete button when selectedClient is default", () => {
    render(<Sidebar {...defaultProps} selectedClient="default" />);
    expect(screen.queryByTestId("delete-client-button")).toBeNull();
  });

  it("shows delete button when selectedClient is not default", () => {
    render(<Sidebar {...nonDefaultProps} />);
    expect(screen.getByTestId("delete-client-button")).toBeTruthy();
  });

  it("shows confirm and cancel buttons after first delete click", () => {
    render(<Sidebar {...nonDefaultProps} />);
    fireEvent.click(screen.getByTestId("delete-client-button"));
    expect(screen.getByTestId("confirm-delete-client")).toBeTruthy();
    expect(screen.getByText("Cancel")).toBeTruthy();
  });

  it("cancels delete and restores delete button when Cancel clicked", () => {
    render(<Sidebar {...nonDefaultProps} />);
    fireEvent.click(screen.getByTestId("delete-client-button"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.getByTestId("delete-client-button")).toBeTruthy();
    expect(screen.queryByTestId("confirm-delete-client")).toBeNull();
  });

  it("deletes client via sidecar API and calls onClientDeleted", async () => {
    const onClientDeleted = vi.fn();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({}),
    });
    render(
      <Sidebar
        {...nonDefaultProps}
        sidecarUrl="http://127.0.0.1:8765"
        onClientDeleted={onClientDeleted}
      />,
    );
    fireEvent.click(screen.getByTestId("delete-client-button"));
    fireEvent.click(screen.getByTestId("confirm-delete-client"));
    await waitFor(() => expect(onClientDeleted).toHaveBeenCalledWith("mybrand"));
  });

  it("deletes client via Tauri invoke when no sidecarUrl and calls onClientDeleted", async () => {
    const onClientDeleted = vi.fn();
    vi.mocked(invoke).mockResolvedValue(undefined);
    render(<Sidebar {...nonDefaultProps} onClientDeleted={onClientDeleted} />);
    fireEvent.click(screen.getByTestId("delete-client-button"));
    fireEvent.click(screen.getByTestId("confirm-delete-client"));
    await waitFor(() => expect(onClientDeleted).toHaveBeenCalledWith("mybrand"));
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("delete_client_config", { name: "mybrand" }),
    );
  });

  it("does not call onClientDeleted when sidecar delete returns non-ok", async () => {
    const onClientDeleted = vi.fn();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      json: vi.fn().mockResolvedValue({ detail: "Delete failed" }),
    });
    render(
      <Sidebar
        {...nonDefaultProps}
        sidecarUrl="http://127.0.0.1:8765"
        onClientDeleted={onClientDeleted}
      />,
    );
    fireEvent.click(screen.getByTestId("delete-client-button"));
    fireEvent.click(screen.getByTestId("confirm-delete-client"));
    await waitFor(() =>
      expect(globalThis.fetch as ReturnType<typeof vi.fn>).toHaveBeenCalled(),
    );
    expect(onClientDeleted).not.toHaveBeenCalled();
  });

  it("does not call onClientDeleted when sidecar delete fetch throws", async () => {
    const onClientDeleted = vi.fn();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("network error"));
    render(
      <Sidebar
        {...nonDefaultProps}
        sidecarUrl="http://127.0.0.1:8765"
        onClientDeleted={onClientDeleted}
      />,
    );
    fireEvent.click(screen.getByTestId("delete-client-button"));
    fireEvent.click(screen.getByTestId("confirm-delete-client"));
    await waitFor(() =>
      expect(globalThis.fetch as ReturnType<typeof vi.fn>).toHaveBeenCalled(),
    );
    expect(onClientDeleted).not.toHaveBeenCalled();
  });

  it("does not call onClientDeleted when Tauri delete invoke throws", async () => {
    const onClientDeleted = vi.fn();
    vi.mocked(invoke).mockRejectedValue("Permission denied");
    render(<Sidebar {...nonDefaultProps} onClientDeleted={onClientDeleted} />);
    fireEvent.click(screen.getByTestId("delete-client-button"));
    fireEvent.click(screen.getByTestId("confirm-delete-client"));
    await waitFor(() => expect(invoke).toHaveBeenCalled());
    expect(onClientDeleted).not.toHaveBeenCalled();
  });

  it("shows delete error in create form area when form is open and sidecar delete fails", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      json: vi.fn().mockResolvedValue({ detail: "Delete failed" }),
    });
    render(<Sidebar {...nonDefaultProps} sidecarUrl="http://127.0.0.1:8765" />);
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.click(screen.getByTestId("delete-client-button"));
    fireEvent.click(screen.getByTestId("confirm-delete-client"));
    await waitFor(() => expect(screen.getByText("Delete failed")).toBeTruthy());
  });
});

describe("Sidebar — state reset on selectedClient change", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  it("resets confirmDelete when selectedClient changes", () => {
    const { rerender } = render(
      <Sidebar {...defaultProps} selectedClient="mybrand" clients={["default", "mybrand"]} />,
    );
    fireEvent.click(screen.getByTestId("delete-client-button"));
    expect(screen.getByTestId("confirm-delete-client")).toBeTruthy();

    rerender(
      <Sidebar {...defaultProps} selectedClient="default" clients={["default", "mybrand"]} />,
    );
    expect(screen.queryByTestId("confirm-delete-client")).toBeNull();
    expect(screen.queryByTestId("delete-client-button")).toBeNull();
  });

  it("resets createError when selectedClient changes", async () => {
    vi.mocked(invoke).mockRejectedValue("Failed");
    const { rerender } = render(
      <Sidebar {...defaultProps} selectedClient="mybrand" clients={["default", "mybrand"]} />,
    );
    fireEvent.click(screen.getByTestId("new-client-button"));
    fireEvent.change(screen.getByTestId("new-client-input"), { target: { value: "test" } });
    fireEvent.click(screen.getByTestId("create-client-button"));
    await waitFor(() => expect(screen.getByText("Failed")).toBeTruthy());

    rerender(
      <Sidebar {...defaultProps} selectedClient="default" clients={["default", "mybrand"]} />,
    );
    expect(screen.queryByText("Failed")).toBeNull();
  });
});

describe("Sidebar — ClientSelect dropdown", () => {
  it("closes dropdown when clicking outside the switcher", () => {
    render(
      <div>
        <Sidebar {...defaultProps} />
        <div data-testid="outside">outside</div>
      </div>,
    );
    fireEvent.click(screen.getByTestId("client-switcher"));
    expect(screen.getByText("mybrand")).toBeTruthy();
    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(screen.queryByText("mybrand")).toBeNull();
  });

  it("shows selected client name in switcher button", () => {
    render(<Sidebar {...defaultProps} selectedClient="mybrand" />);
    expect(screen.getByTestId("client-switcher").textContent).toContain("mybrand");
  });

  it("highlights the currently selected client in the dropdown", () => {
    render(<Sidebar {...defaultProps} selectedClient="mybrand" />);
    fireEvent.click(screen.getByTestId("client-switcher"));
    const allButtons = screen.getAllByRole("button");
    const mybrandOption = allButtons.find((btn) => btn.textContent === "mybrand");
    expect(mybrandOption?.className).toContain("font-medium");
  });
});
