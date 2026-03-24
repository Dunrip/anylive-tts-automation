import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({
  save: vi.fn(),
}));

vi.mock("@tauri-apps/plugin-fs", () => ({
  writeTextFile: vi.fn(),
}));
import { LogViewer } from "../components/layout/LogViewer";
import type { WSMessage } from "../lib/types";

const mockMessages: WSMessage[] = [
  { type: "log", level: "INFO", message: "Starting automation", timestamp: "2026-01-01T00:00:00Z" },
  { type: "log", level: "WARN", message: "Slow response", timestamp: "2026-01-01T00:00:01Z" },
  { type: "log", level: "ERROR", message: "Failed to click", timestamp: "2026-01-01T00:00:02Z" },
  { type: "log", level: "DEBUG", message: "Debug info", timestamp: "2026-01-01T00:00:03Z" },
];

describe("LogViewer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders log viewer", () => {
    render(<LogViewer messages={[]} isConnected={false} />);
    expect(screen.getByTestId("log-viewer")).toBeInTheDocument();
  });

  it("shows waiting message when no logs", () => {
    render(<LogViewer messages={[]} isConnected={false} />);
    expect(screen.getByText("Waiting for logs...")).toBeInTheDocument();
  });

  it("renders log messages and count", () => {
    render(<LogViewer messages={mockMessages} isConnected={true} />);

    expect(screen.getByText("Starting automation")).toBeInTheDocument();
    expect(screen.getByText("Slow response")).toBeInTheDocument();
    expect(screen.getByText("Failed to click")).toBeInTheDocument();
    expect(screen.getByText("4 messages")).toBeInTheDocument();
  });

  it("applies color mapping by log level", () => {
    render(<LogViewer messages={mockMessages} isConnected={true} />);

    expect(screen.getByTestId("log-line-0")).toHaveStyle({ color: "var(--text-primary)" });
    expect(screen.getByTestId("log-line-1")).toHaveStyle({ color: "var(--warning)" });
    expect(screen.getByTestId("log-line-2")).toHaveStyle({ color: "var(--error)" });
    expect(screen.getByTestId("log-line-3")).toHaveStyle({ color: "var(--text-muted)" });
  });

  it("filters messages by search input", () => {
    render(<LogViewer messages={mockMessages} isConnected={true} />);

    fireEvent.change(screen.getByTestId("log-filter"), { target: { value: "slow" } });

    expect(screen.getByText("Slow response")).toBeInTheDocument();
    expect(screen.queryByText("Starting automation")).not.toBeInTheDocument();
    expect(screen.getByText("1 messages")).toBeInTheDocument();
  });

  it("pauses auto-scroll when user scrolls up and can resume", () => {
    render(<LogViewer messages={mockMessages} isConnected={true} />);

    const content = screen.getByTestId("log-content");
    Object.defineProperty(content, "scrollHeight", { configurable: true, value: 1000 });
    Object.defineProperty(content, "clientHeight", { configurable: true, value: 200 });
    Object.defineProperty(content, "scrollTop", { configurable: true, value: 0, writable: true });

    fireEvent.scroll(content);
    expect(screen.getByTestId("resume-scroll-button")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("resume-scroll-button"));
    expect(screen.queryByTestId("resume-scroll-button")).not.toBeInTheDocument();
  });

  it("copies filtered logs", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    render(<LogViewer messages={mockMessages} isConnected={true} />);
    fireEvent.change(screen.getByTestId("log-filter"), { target: { value: "failed" } });
    fireEvent.click(screen.getByTestId("copy-logs-button"));

    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("[ERROR] Failed to click"));
    expect(writeText).toHaveBeenCalledWith(expect.stringMatching(/\d{2}:\d{2}:\d{2}/));
  });

  it("renders level toggle buttons for all 4 levels", () => {
    render(<LogViewer messages={mockMessages} isConnected={true} />);
    expect(screen.getByTestId("level-toggle-INFO")).toBeInTheDocument();
    expect(screen.getByTestId("level-toggle-WARN")).toBeInTheDocument();
    expect(screen.getByTestId("level-toggle-ERROR")).toBeInTheDocument();
    expect(screen.getByTestId("level-toggle-DEBUG")).toBeInTheDocument();
  });

  it("toggling off a level hides messages of that level", () => {
    render(<LogViewer messages={mockMessages} isConnected={true} />);
    expect(screen.getByText("Starting automation")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("level-toggle-INFO"));
    expect(screen.queryByText("Starting automation")).not.toBeInTheDocument();
    expect(screen.getByText("3 messages")).toBeInTheDocument();
  });

  it("toggling a level back on restores its messages", () => {
    render(<LogViewer messages={mockMessages} isConnected={true} />);
    fireEvent.click(screen.getByTestId("level-toggle-INFO"));
    expect(screen.queryByText("Starting automation")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("level-toggle-INFO"));
    expect(screen.getByText("Starting automation")).toBeInTheDocument();
  });

  it("displays timestamps on each log line", () => {
    render(<LogViewer messages={mockMessages} isConnected={true} />);
    const logContent = screen.getByTestId("log-content");
    expect(logContent.textContent).toMatch(/\d{2}:\d{2}:\d{2}/);
  });

  it("level and text filters compose with AND logic", () => {
    render(<LogViewer messages={mockMessages} isConnected={true} />);
    fireEvent.click(screen.getByTestId("level-toggle-WARN"));
    fireEvent.change(screen.getByTestId("log-filter"), { target: { value: "start" } });
    expect(screen.getByText("Starting automation")).toBeInTheDocument();
    expect(screen.queryByText("Slow response")).not.toBeInTheDocument();
    expect(screen.getByText("1 messages")).toBeInTheDocument();
  });

  it("export button is disabled when no messages", () => {
    render(<LogViewer messages={[]} isConnected={false} />);
    const exportBtn = screen.getByTestId("export-logs-button");
    expect(exportBtn).toBeDisabled();
  });

  it("export writes filtered logs to file", async () => {
    const { save } = await import("@tauri-apps/plugin-dialog");
    const { writeTextFile } = await import("@tauri-apps/plugin-fs");
    (save as ReturnType<typeof vi.fn>).mockResolvedValue("/tmp/logs.txt");
    (writeTextFile as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);

    render(<LogViewer messages={mockMessages} isConnected={true} />);
    fireEvent.change(screen.getByTestId("log-filter"), { target: { value: "failed" } });
    fireEvent.click(screen.getByTestId("export-logs-button"));

    await waitFor(() => {
      expect(writeTextFile).toHaveBeenCalledTimes(1);
    });
    expect(writeTextFile).toHaveBeenCalledWith(
      "/tmp/logs.txt",
      expect.stringContaining("[ERROR] Failed to click")
    );
    expect(writeTextFile).toHaveBeenCalledWith(
      "/tmp/logs.txt",
      expect.stringMatching(/\d{2}:\d{2}:\d{2}/)
    );
  });

  it("export is a no-op when user cancels save dialog", async () => {
    const { save } = await import("@tauri-apps/plugin-dialog");
    const { writeTextFile } = await import("@tauri-apps/plugin-fs");
    (save as ReturnType<typeof vi.fn>).mockResolvedValue(null);
    (writeTextFile as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);

    render(<LogViewer messages={mockMessages} isConnected={true} />);
    fireEvent.click(screen.getByTestId("export-logs-button"));

    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(1);
    });
    expect(writeTextFile).not.toHaveBeenCalled();
  });
});
