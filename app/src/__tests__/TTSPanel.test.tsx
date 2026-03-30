import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StatusBadge } from "../components/common/StatusBadge";
import { ProgressBar } from "../components/common/ProgressBar";
import { TTSPanel } from "../components/tts/TTSPanel";
import { useAutomation } from "../hooks/useAutomation";
import { TooltipProvider } from "../components/ui/tooltip";

vi.mock("../hooks/useNotification", () => ({
  useNotification: () => ({ sendJobNotification: vi.fn() }),
}));

// Mock CSVPicker to avoid Tauri dialog dependency
vi.mock("../components/common/CSVPicker", () => ({
  CSVPicker: ({
    onFileSelected,
    onClear,
  }: {
    onFileSelected?: (path: string, preview: unknown) => void;
    onClear?: () => void;
  }) => (
    <div data-testid="csv-picker-mock">
      <button
        type="button"
        onClick={() =>
          onFileSelected?.("/test.csv", {
            rows: 5,
            products: 2,
            estimated_versions: 2,
            version_names: ["V1", "V2"],
            preview: [],
            errors: [],
          })
        }
      >
        Mock Select CSV
      </button>
      <button type="button" data-testid="csv-clear" onClick={() => onClear?.()}>
        Clear
      </button>
    </div>
  ),
}));

vi.mock("../hooks/useAutomation");

vi.mock("../hooks/useWebSocket", () => ({
  useWebSocket: () => ({ messages: [], isConnected: false, clearMessages: vi.fn() }),
}));

describe("StatusBadge", () => {
  it("renders pending badge", () => {
    render(<StatusBadge status="pending" />);
    expect(screen.getByTestId("status-badge-pending")).toBeTruthy();
    expect(screen.getByText("Pending")).toBeTruthy();
  });

  it("renders running badge", () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByTestId("status-badge-running")).toBeTruthy();
    expect(screen.getByText("Running")).toBeTruthy();
  });

  it("renders success badge", () => {
    render(<StatusBadge status="success" />);
    expect(screen.getByTestId("status-badge-success")).toBeTruthy();
    expect(screen.getByText("Success")).toBeTruthy();
  });

  it("renders failed badge", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByTestId("status-badge-failed")).toBeTruthy();
    expect(screen.getByText("Failed")).toBeTruthy();
  });
});

describe("ProgressBar", () => {
  it("renders with correct percentage", () => {
    render(<ProgressBar current={3} total={10} />);
    expect(screen.getByTestId("progress-bar")).toBeTruthy();
    expect(screen.getByTestId("progress-text")).toBeTruthy();
    expect(screen.getByText("2/10 versions (20%)")).toBeTruthy();
  });

  it("renders 0% when no progress", () => {
    render(<ProgressBar current={0} total={10} />);
    expect(screen.getByText("0/10 versions (0%)")).toBeTruthy();
  });
});

describe("TTSPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: false,
      jobId: null,
      progress: { current: 0, total: 0 },
      versions: [],
      error: null,
      wsUrl: null,
      polledMessages: [],
      startRun: vi.fn(),
      handleMessage: vi.fn(),
      reset: vi.fn(),
      pollJobStatus: vi.fn(),
      cancelJob: vi.fn(),
    });
  });

  it("renders TTS panel with run button", () => {
    render(
      <TooltipProvider>
        <TTSPanel client="default" />
      </TooltipProvider>
    );
    expect(screen.getByTestId("tts-panel")).toBeTruthy();
    expect(screen.getByTestId("run-button")).toBeTruthy();
    expect(screen.queryByTestId("stop-button")).toBeNull();
  });

  it("run button is disabled without CSV", () => {
    render(
      <TooltipProvider>
        <TTSPanel client="default" />
      </TooltipProvider>
    );
    const runBtn = screen.getByTestId("run-button") as HTMLButtonElement;
    expect(runBtn.disabled).toBe(true);
  });

  it("renders options checkboxes", () => {
    render(
      <TooltipProvider>
        <TTSPanel client="default" />
      </TooltipProvider>
    );
    expect(screen.getByTestId("option-headless")).toBeTruthy();
    expect(screen.getByTestId("option-dry_run")).toBeTruthy();
    expect(screen.getByTestId("option-debug")).toBeTruthy();
  });

  it("shows cancel button and Running... text when isRunning", () => {
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: true,
      jobId: "job-abc",
      progress: { current: 0, total: 0 },
      versions: [],
      error: null,
      wsUrl: null,
      polledMessages: [],
      startRun: vi.fn(),
      handleMessage: vi.fn(),
      reset: vi.fn(),
      pollJobStatus: vi.fn(),
      cancelJob: vi.fn(),
    });
    render(
      <TooltipProvider>
        <TTSPanel client="default" sidecarUrl="http://localhost:1234" />
      </TooltipProvider>
    );
    expect(screen.getByTestId("cancel-button")).toBeTruthy();
    expect(screen.getByTestId("run-button").textContent).toBe("Running...");
  });

  it("cancel button click calls cancelJob with sidecarUrl", () => {
    const cancelJob = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: true,
      jobId: "job-abc",
      progress: { current: 0, total: 0 },
      versions: [],
      error: null,
      wsUrl: null,
      polledMessages: [],
      startRun: vi.fn(),
      handleMessage: vi.fn(),
      reset: vi.fn(),
      pollJobStatus: vi.fn(),
      cancelJob,
    });
    render(
      <TooltipProvider>
        <TTSPanel client="default" sidecarUrl="http://localhost:1234" />
      </TooltipProvider>
    );
    fireEvent.click(screen.getByTestId("cancel-button"));
    expect(cancelJob).toHaveBeenCalledWith("http://localhost:1234");
  });

  it("toggle advanced shows and hides start-version and limit fields", () => {
    render(
      <TooltipProvider>
        <TTSPanel client="default" />
      </TooltipProvider>
    );
    expect(screen.queryByTestId("option-start-version")).toBeNull();
    expect(screen.queryByTestId("option-limit")).toBeNull();

    fireEvent.click(screen.getByTestId("toggle-advanced"));
    expect(screen.getByTestId("option-start-version")).toBeTruthy();
    expect(screen.getByTestId("option-limit")).toBeTruthy();

    fireEvent.click(screen.getByTestId("toggle-advanced"));
    expect(screen.queryByTestId("option-start-version")).toBeNull();
  });

  it("error banner renders when automation error is set", () => {
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: false,
      jobId: null,
      progress: { current: 0, total: 0 },
      versions: [],
      error: "Something went wrong",
      wsUrl: null,
      polledMessages: [],
      startRun: vi.fn(),
      handleMessage: vi.fn(),
      reset: vi.fn(),
      pollJobStatus: vi.fn(),
      cancelJob: vi.fn(),
    });
    render(
      <TooltipProvider>
        <TTSPanel client="default" />
      </TooltipProvider>
    );
    const banner = screen.getByTestId("automation-error");
    expect(banner).toBeTruthy();
    expect(banner.textContent).toBe("Something went wrong");
  });

  it("version list renders with version items when versions are present", () => {
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: false,
      jobId: null,
      progress: { current: 0, total: 0 },
      versions: [
        { name: "V1", status: "success" },
        { name: "V2", status: "failed" },
      ],
      error: null,
      wsUrl: null,
      polledMessages: [],
      startRun: vi.fn(),
      handleMessage: vi.fn(),
      reset: vi.fn(),
      pollJobStatus: vi.fn(),
      cancelJob: vi.fn(),
    });
    render(
      <TooltipProvider>
        <TTSPanel client="default" />
      </TooltipProvider>
    );
    expect(screen.getByTestId("version-list")).toBeTruthy();
    expect(screen.getByText("V1")).toBeTruthy();
    expect(screen.getByText("V2")).toBeTruthy();
  });

  it("progress bar shows when progress.current > 0", () => {
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: false,
      jobId: null,
      progress: { current: 3, total: 10 },
      versions: [],
      error: null,
      wsUrl: null,
      polledMessages: [],
      startRun: vi.fn(),
      handleMessage: vi.fn(),
      reset: vi.fn(),
      pollJobStatus: vi.fn(),
      cancelJob: vi.fn(),
    });
    render(
      <TooltipProvider>
        <TTSPanel client="default" />
      </TooltipProvider>
    );
    expect(screen.getByTestId("progress-bar")).toBeTruthy();
  });

  it("toggling download mode switches options UI to download-specific checkboxes", () => {
    render(
      <TooltipProvider>
        <TTSPanel client="default" />
      </TooltipProvider>
    );
    expect(screen.getByTestId("option-dry_run")).toBeTruthy();
    expect(screen.queryByTestId("option-replace")).toBeNull();

    fireEvent.click(screen.getByTestId("option-download"));
    expect(screen.getByTestId("option-replace")).toBeTruthy();
    expect(screen.queryByTestId("option-dry_run")).toBeNull();
  });

  it("run button enabled in download mode without CSV when sidecarUrl provided", () => {
    render(
      <TooltipProvider>
        <TTSPanel client="default" sidecarUrl="http://localhost:1234" />
      </TooltipProvider>
    );
    const runBtn = screen.getByTestId("run-button") as HTMLButtonElement;
    expect(runBtn.disabled).toBe(true);

    fireEvent.click(screen.getByTestId("option-download"));
    expect(runBtn.disabled).toBe(false);
  });

  it("run button shows Download text in download mode", () => {
    render(
      <TooltipProvider>
        <TTSPanel client="default" sidecarUrl="http://localhost:1234" />
      </TooltipProvider>
    );
    fireEvent.click(screen.getByTestId("option-download"));
    expect(screen.getByTestId("run-button").textContent).toBe("Download");
  });
});
