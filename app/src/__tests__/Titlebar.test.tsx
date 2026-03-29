import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockMinimize = vi.fn().mockResolvedValue(undefined);
const mockToggleMaximize = vi.fn().mockResolvedValue(undefined);
const mockHide = vi.fn().mockResolvedValue(undefined);

vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: () => ({
    minimize: mockMinimize,
    toggleMaximize: mockToggleMaximize,
    hide: mockHide,
  }),
}));

describe("Titlebar — non-Windows", () => {
  it("returns null when not on Windows (default jsdom UA)", async () => {
    vi.resetModules();
    const { Titlebar } = await import("../components/layout/Titlebar");
    const { container } = render(<Titlebar />);
    expect(container.firstChild).toBeNull();
  });
});

describe("Titlebar — Windows", () => {
  const WIN_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36";
  let savedUA: string;

  beforeEach(() => {
    vi.clearAllMocks();
    savedUA = navigator.userAgent;
    Object.defineProperty(navigator, "userAgent", {
      value: WIN_UA,
      configurable: true,
      writable: true,
    });
    vi.resetModules();
  });

  afterEach(() => {
    Object.defineProperty(navigator, "userAgent", {
      value: savedUA,
      configurable: true,
      writable: true,
    });
  });

  it("renders titlebar container with drag region attribute", async () => {
    const { Titlebar } = await import("../components/layout/Titlebar");
    render(<Titlebar />);
    const titlebar = screen.getByTestId("titlebar");
    expect(titlebar).toBeTruthy();
    expect(titlebar.hasAttribute("data-tauri-drag-region")).toBe(true);
  });

  it("renders minimize, maximize, and close buttons", async () => {
    const { Titlebar } = await import("../components/layout/Titlebar");
    render(<Titlebar />);
    expect(screen.getByTestId("titlebar-minimize")).toBeTruthy();
    expect(screen.getByTestId("titlebar-maximize")).toBeTruthy();
    expect(screen.getByTestId("titlebar-close")).toBeTruthy();
  });

  it("buttons have accessible aria-label attributes", async () => {
    const { Titlebar } = await import("../components/layout/Titlebar");
    render(<Titlebar />);
    expect(screen.getByLabelText("Minimize")).toBeTruthy();
    expect(screen.getByLabelText("Maximize")).toBeTruthy();
    expect(screen.getByLabelText("Close")).toBeTruthy();
  });

  it("calls getCurrentWindow().minimize() when minimize button clicked", async () => {
    const { Titlebar } = await import("../components/layout/Titlebar");
    render(<Titlebar />);
    fireEvent.click(screen.getByTestId("titlebar-minimize"));
    await waitFor(() => expect(mockMinimize).toHaveBeenCalledTimes(1));
  });

  it("calls getCurrentWindow().toggleMaximize() when maximize button clicked", async () => {
    const { Titlebar } = await import("../components/layout/Titlebar");
    render(<Titlebar />);
    fireEvent.click(screen.getByTestId("titlebar-maximize"));
    await waitFor(() => expect(mockToggleMaximize).toHaveBeenCalledTimes(1));
  });

  it("calls getCurrentWindow().hide() when close button clicked", async () => {
    const { Titlebar } = await import("../components/layout/Titlebar");
    render(<Titlebar />);
    fireEvent.click(screen.getByTestId("titlebar-close"));
    await waitFor(() => expect(mockHide).toHaveBeenCalledTimes(1));
  });

  it("renders minimize symbol in minimize button", async () => {
    const { Titlebar } = await import("../components/layout/Titlebar");
    render(<Titlebar />);
    expect(screen.getByTestId("titlebar-minimize").textContent?.trim()).toBeTruthy();
  });

  it("renders maximize symbol in maximize button", async () => {
    const { Titlebar } = await import("../components/layout/Titlebar");
    render(<Titlebar />);
    expect(screen.getByTestId("titlebar-maximize").textContent?.trim()).toBeTruthy();
  });

  it("renders close symbol in close button", async () => {
    const { Titlebar } = await import("../components/layout/Titlebar");
    render(<Titlebar />);
    expect(screen.getByTestId("titlebar-close").textContent?.trim()).toBeTruthy();
  });
});
