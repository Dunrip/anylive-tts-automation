import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ScriptsPanel } from "../components/scripts/ScriptsPanel";
import { useAutomation } from "../hooks/useAutomation";
import type { JobStatus, WSMessage } from "../lib/types";

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

function makeDefaultState() {
  return {
    isRunning: false,
    jobId: null as string | null,
    progress: { current: 0, total: 0 },
    versions: [] as { name: string; status: JobStatus }[],
    error: null as string | null,
    wsUrl: null as string | null,
    polledMessages: [] as WSMessage[],
    startRun: vi.fn(),
    handleMessage: vi.fn(),
    reset: vi.fn(),
    pollJobStatus: vi.fn(),
    cancelJob: vi.fn(),
  };
}

describe("ScriptsPanel — delete flow branches", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn();
    vi.mocked(useAutomation).mockReturnValue(makeDefaultState());
  });

  it("delete button is disabled when automation is running", () => {
    vi.mocked(useAutomation).mockReturnValue({
      ...makeDefaultState(),
      isRunning: true,
      jobId: "job-1",
    });
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    expect(screen.getByTestId("delete-scripts-button")).toBeDisabled();
  });

  it("handleDelete: fetch ok → dialog closes, no error shown", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true });
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    fireEvent.click(screen.getByTestId("delete-scripts-button"));
    fireEvent.click(screen.getByTestId("confirm-delete-button"));
    await waitFor(() =>
      expect((global.fetch as ReturnType<typeof vi.fn>)).toHaveBeenCalled()
    );
    expect(screen.queryByText("Delete failed")).toBeNull();
    expect(screen.queryByText("Could not connect to sidecar")).toBeNull();
    expect(screen.queryByTestId("delete-confirm-dialog")).toBeNull();
  });

  it("handleDelete: fetch !ok with detail → shows detail as error", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Server rejected delete" }),
    });
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    fireEvent.click(screen.getByTestId("delete-scripts-button"));
    fireEvent.click(screen.getByTestId("confirm-delete-button"));
    await waitFor(() =>
      expect(screen.getByText("Server rejected delete")).toBeTruthy()
    );
  });

  it("handleDelete: fetch !ok without detail → shows 'Delete failed'", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    });
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    fireEvent.click(screen.getByTestId("delete-scripts-button"));
    fireEvent.click(screen.getByTestId("confirm-delete-button"));
    await waitFor(() =>
      expect(screen.getByText("Delete failed")).toBeTruthy()
    );
  });

  it("handleDelete: network error → shows 'Could not connect to sidecar'", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(
      new TypeError("Network error")
    );
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    fireEvent.click(screen.getByTestId("delete-scripts-button"));
    fireEvent.click(screen.getByTestId("confirm-delete-button"));
    await waitFor(() =>
      expect(screen.getByText("Could not connect to sidecar")).toBeTruthy()
    );
  });
});

describe("ScriptsPanel — replace flow branches", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(useAutomation).mockReturnValue(makeDefaultState());
  });

  it("handleReplace: startRun throws → shows 'Could not connect to sidecar'", async () => {
    vi.mocked(useAutomation).mockReturnValue({
      ...makeDefaultState(),
      startRun: vi.fn().mockRejectedValue(new Error("connection failed")),
    });
    render(<ScriptsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);
    fireEvent.click(screen.getByTestId("replace-products-button"));
    fireEvent.click(screen.getByTestId("confirm-replace-button"));
    await waitFor(() =>
      expect(screen.getByText("Could not connect to sidecar")).toBeTruthy()
    );
  });
});

describe("ScriptsPanel — progress and version list branches", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(useAutomation).mockReturnValue(makeDefaultState());
  });

  it("shows progress bar when isRunning (current=0, total>0)", () => {
    vi.mocked(useAutomation).mockReturnValue({
      ...makeDefaultState(),
      isRunning: true,
      jobId: "job-1",
      progress: { current: 0, total: 5 },
    });
    render(<ScriptsPanel client="default" />);
    expect(screen.getByTestId("progress-bar")).toBeTruthy();
  });

  it("shows progress bar when not running but progress.current > 0", () => {
    vi.mocked(useAutomation).mockReturnValue({
      ...makeDefaultState(),
      isRunning: false,
      progress: { current: 3, total: 5 },
    });
    render(<ScriptsPanel client="default" />);
    expect(screen.getByTestId("progress-bar")).toBeTruthy();
  });

  it("does not render progress bar when not running and current=0", () => {
    render(<ScriptsPanel client="default" />);
    expect(screen.queryByTestId("progress-bar")).toBeNull();
  });

  it("renders version list with items when versions are present", () => {
    vi.mocked(useAutomation).mockReturnValue({
      ...makeDefaultState(),
      versions: [
        { name: "Script A", status: "success" as const },
        { name: "Script B", status: "failed" as const },
      ],
    });
    render(<ScriptsPanel client="default" />);
    expect(screen.getByTestId("scripts-version-list")).toBeTruthy();
    expect(screen.getByText("Script A")).toBeTruthy();
    expect(screen.getByText("Script B")).toBeTruthy();
  });

  it("does not render version list when versions is empty", () => {
    render(<ScriptsPanel client="default" />);
    expect(screen.queryByTestId("scripts-version-list")).toBeNull();
  });
});

describe("ScriptsPanel — advanced options and URL branches", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(useAutomation).mockReturnValue(makeDefaultState());
  });

  it("advanced toggle reveals and hides start-product, limit, and audio-dir fields", () => {
    render(<ScriptsPanel client="default" />);
    expect(screen.queryByTestId("scripts-option-start-product")).toBeNull();
    expect(screen.queryByTestId("scripts-option-limit")).toBeNull();
    expect(screen.queryByTestId("scripts-option-audio-dir")).toBeNull();

    fireEvent.click(screen.getByTestId("scripts-toggle-advanced"));
    expect(screen.getByTestId("scripts-option-start-product")).toBeTruthy();
    expect(screen.getByTestId("scripts-option-limit")).toBeTruthy();
    expect(screen.getByTestId("scripts-option-audio-dir")).toBeTruthy();

    fireEvent.click(screen.getByTestId("scripts-toggle-advanced"));
    expect(screen.queryByTestId("scripts-option-start-product")).toBeNull();
  });

  it("headless checkbox toggles between checked and unchecked", () => {
    render(<ScriptsPanel client="default" />);
    const cb = screen.getByTestId("scripts-option-headless") as HTMLInputElement;
    expect(cb.checked).toBe(false);
    fireEvent.click(cb);
    expect(cb.checked).toBe(true);
    fireEvent.click(cb);
    expect(cb.checked).toBe(false);
  });

  it("dry_run checkbox starts unchecked and toggles on click", () => {
    render(<ScriptsPanel client="default" />);
    const cb = screen.getByTestId("scripts-option-dry_run") as HTMLInputElement;
    expect(cb.checked).toBe(false);
    fireEvent.click(cb);
    expect(cb.checked).toBe(true);
  });

  it("debug checkbox starts unchecked and toggles on click", () => {
    render(<ScriptsPanel client="default" />);
    const cb = screen.getByTestId("scripts-option-debug") as HTMLInputElement;
    expect(cb.checked).toBe(false);
    fireEvent.click(cb);
    expect(cb.checked).toBe(true);
  });

  it("base URL input fires onBaseUrlChange callback with new value", () => {
    const onBaseUrlChange = vi.fn();
    render(
      <ScriptsPanel
        client="default"
        baseUrl="https://initial.example.com"
        onBaseUrlChange={onBaseUrlChange}
      />
    );
    fireEvent.change(screen.getByTestId("input-scripts-base-url"), {
      target: { value: "https://new.example.com" },
    });
    expect(onBaseUrlChange).toHaveBeenCalledWith("https://new.example.com");
  });

  it("renders base URL input with provided baseUrl value", () => {
    render(<ScriptsPanel client="default" baseUrl="https://test.example.com" />);
    const input = screen.getByTestId("input-scripts-base-url") as HTMLInputElement;
    expect(input.value).toBe("https://test.example.com");
  });
});
