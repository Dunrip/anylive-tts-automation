import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ScriptsPanel } from "../components/scripts/ScriptsPanel";

vi.mock("../components/common/CSVPicker", () => ({
  CSVPicker: () => <div data-testid="csv-picker-mock" />,
}));
vi.mock("../hooks/useAutomation", () => ({
  useAutomation: () => ({
    isRunning: false, jobId: null, progress: { current: 0, total: 0 },
    versions: [], error: null, wsUrl: null,
    startRun: vi.fn(), handleMessage: vi.fn(), reset: vi.fn(),
  }),
}));
vi.mock("../hooks/useWebSocket", () => ({
  useWebSocket: () => ({ messages: [], isConnected: false, clearMessages: vi.fn() }),
}));

describe("ScriptsPanel", () => {
  it("renders scripts panel with run and delete buttons", () => {
    render(<ScriptsPanel client="default" />);
    expect(screen.getByTestId("scripts-panel")).toBeTruthy();
    expect(screen.getByTestId("scripts-run-button")).toBeTruthy();
    expect(screen.getByTestId("delete-scripts-button")).toBeTruthy();
  });

  it("shows confirmation dialog when delete button clicked", () => {
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    fireEvent.click(screen.getByTestId("delete-scripts-button"));
    expect(screen.getByTestId("delete-confirm-dialog")).toBeTruthy();
    expect(screen.getByTestId("confirm-delete-button")).toBeTruthy();
    expect(screen.getByTestId("cancel-delete-button")).toBeTruthy();
  });

  it("hides confirmation dialog when cancel clicked", () => {
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    fireEvent.click(screen.getByTestId("delete-scripts-button"));
    expect(screen.getByTestId("delete-confirm-dialog")).toBeTruthy();
    fireEvent.click(screen.getByTestId("cancel-delete-button"));
    expect(screen.queryByTestId("delete-confirm-dialog")).toBeNull();
  });
});
