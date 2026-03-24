import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ScriptsPanel } from "../components/scripts/ScriptsPanel";
import { useAutomation } from "../hooks/useAutomation";

vi.mock("../components/common/CSVPicker", () => ({
  CSVPicker: () => <div data-testid="csv-picker-mock" />,
}));

vi.mock("../hooks/useWebSocket", () => ({
  useWebSocket: () => ({ messages: [], isConnected: false, clearMessages: vi.fn() }),
}));
vi.mock("../hooks/useAutomation");

describe("ScriptsPanel", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn();

    vi.mocked(useAutomation).mockReturnValue({
      isRunning: false,
      jobId: null,
      progress: { current: 0, total: 0 },
      versions: [],
      error: null,
      wsUrl: null,
      startRun: vi.fn(),
      handleMessage: vi.fn(),
      reset: vi.fn(),
      pollJobStatus: vi.fn(),
      cancelJob: vi.fn(),
      polledMessages: [],
    });
  });

  it("renders scripts panel with run, replace, and delete buttons", () => {
    render(<ScriptsPanel client="default" />);
    expect(screen.getByTestId("scripts-panel")).toBeTruthy();
    expect(screen.getByTestId("scripts-run-button")).toBeTruthy();
    expect(screen.getByTestId("replace-products-button")).toBeTruthy();
    expect(screen.getByTestId("delete-scripts-button")).toBeTruthy();
  });

  it("shows delete confirmation dialog when delete button clicked", () => {
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    fireEvent.click(screen.getByTestId("delete-scripts-button"));
    expect(screen.getByTestId("delete-confirm-dialog")).toBeTruthy();
    expect(screen.getByTestId("confirm-delete-button")).toBeTruthy();
    expect(screen.getByTestId("cancel-delete-button")).toBeTruthy();
  });

  it("hides delete confirmation dialog when cancel clicked", () => {
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    fireEvent.click(screen.getByTestId("delete-scripts-button"));
    expect(screen.getByTestId("delete-confirm-dialog")).toBeTruthy();
    fireEvent.click(screen.getByTestId("cancel-delete-button"));
    expect(screen.queryByTestId("delete-confirm-dialog")).toBeNull();
  });

  it("shows replace confirmation dialog when replace button clicked", () => {
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    fireEvent.click(screen.getByTestId("replace-products-button"));
    expect(screen.getByTestId("replace-confirm-dialog")).toBeTruthy();
    expect(screen.getByTestId("confirm-replace-button")).toBeTruthy();
    expect(screen.getByTestId("cancel-replace-button")).toBeTruthy();
  });

  it("hides replace confirmation dialog when cancel clicked", () => {
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    fireEvent.click(screen.getByTestId("replace-products-button"));
    expect(screen.getByTestId("replace-confirm-dialog")).toBeTruthy();
    fireEvent.click(screen.getByTestId("cancel-replace-button"));
    expect(screen.queryByTestId("replace-confirm-dialog")).toBeNull();
  });

  it("calls startRun with replace endpoint when confirmation is given", async () => {
    const sidecarUrl = "http://127.0.0.1:8080";
    const mockStartRun = vi.fn();
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: false,
      jobId: null,
      progress: { current: 0, total: 0 },
      versions: [],
      error: null,
      wsUrl: null,
      startRun: mockStartRun,
      handleMessage: vi.fn(),
      reset: vi.fn(),
      pollJobStatus: vi.fn(),
      cancelJob: vi.fn(),
      polledMessages: [],
    });

    render(<ScriptsPanel client="default" sidecarUrl={sidecarUrl} />);
    fireEvent.click(screen.getByTestId("replace-products-button"));
    fireEvent.click(screen.getByTestId("confirm-replace-button"));

    expect(mockStartRun).toHaveBeenCalledWith({
      sidecarUrl,
      endpoint: "/api/scripts/replace",
      configPath: "configs/default/live.json",
      csvPath: "",
      options: {
        headless: false,
        dry_run: false,
        start_product: undefined,
        limit: undefined,
      },
    });
  });

  it("disables replace button when automation is running", () => {
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: true,
      jobId: "123",
      progress: { current: 1, total: 10 },
      versions: [],
      error: null,
      wsUrl: null,
      startRun: vi.fn(),
      handleMessage: vi.fn(),
      reset: vi.fn(),
      pollJobStatus: vi.fn(),
      cancelJob: vi.fn(),
      polledMessages: [],
    });

    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    expect(screen.getByTestId("replace-products-button")).toBeDisabled();
  });
});
