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

  it("shows green session indicator when session is active", () => {
    render(<Sidebar {...defaultProps} sessionValid={true} />);
    expect(screen.getByText("Session Active")).toBeTruthy();
    const dot = screen.getByTestId("session-dot");
    expect(dot.className).toContain("bg-[var(--success)]");
  });

  it("shows red session indicator when session is expired", () => {
    render(<Sidebar {...defaultProps} sessionValid={false} />);
    expect(screen.getByText("Session Expired")).toBeTruthy();
    const dot = screen.getByTestId("session-dot");
    expect(dot.className).toContain("bg-[var(--error)]");
  });

  it("shows re-login button when session expired", () => {
    const onRelogin = vi.fn();
    render(<Sidebar {...defaultProps} sessionValid={false} onRelogin={onRelogin} />);
    const reloginBtn = screen.getByTestId("relogin-button");
    expect(reloginBtn).toBeTruthy();
    fireEvent.click(reloginBtn);
    expect(onRelogin).toHaveBeenCalled();
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
});
