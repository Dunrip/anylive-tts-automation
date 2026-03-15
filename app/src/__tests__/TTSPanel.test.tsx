import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../components/common/StatusBadge";
import { ProgressBar } from "../components/common/ProgressBar";
import { TTSPanel } from "../components/tts/TTSPanel";

// Mock CSVPicker to avoid Tauri dialog dependency
vi.mock("../components/common/CSVPicker", () => ({
  CSVPicker: ({ onFileSelected }: { onFileSelected?: (path: string, preview: unknown) => void }) => (
    <div data-testid="csv-picker-mock">
      <button onClick={() => onFileSelected?.("/test.csv", { rows: 5, products: 2, estimated_versions: 2, preview: [], errors: [] })}>
        Mock Select CSV
      </button>
    </div>
  ),
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
    expect(screen.getByText("3/10 versions (30%)")).toBeTruthy();
  });

  it("renders 0% when no progress", () => {
    render(<ProgressBar current={0} total={10} />);
    expect(screen.getByText("0/10 versions (0%)")).toBeTruthy();
  });
});

describe("TTSPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders TTS panel with run button", () => {
    render(<TTSPanel client="default" />);
    expect(screen.getByTestId("tts-panel")).toBeTruthy();
    expect(screen.getByTestId("run-button")).toBeTruthy();
    expect(screen.getByTestId("stop-button")).toBeTruthy();
  });

  it("run button is disabled without CSV", () => {
    render(<TTSPanel client="default" />);
    const runBtn = screen.getByTestId("run-button") as HTMLButtonElement;
    expect(runBtn.disabled).toBe(true);
  });

  it("renders options checkboxes", () => {
    render(<TTSPanel client="default" />);
    expect(screen.getByTestId("option-headless")).toBeTruthy();
    expect(screen.getByTestId("option-dry_run")).toBeTruthy();
    expect(screen.getByTestId("option-debug")).toBeTruthy();
  });
});
