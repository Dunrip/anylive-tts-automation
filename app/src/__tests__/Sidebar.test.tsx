import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Sidebar } from "../components/layout/Sidebar";

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
