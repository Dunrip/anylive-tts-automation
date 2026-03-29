import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FAQPanel } from "../components/faq/FAQPanel";
import { useAutomation } from "../hooks/useAutomation";

vi.mock("../components/common/CSVPicker", () => ({
  CSVPicker: () => <div data-testid="csv-picker-mock" />,
}));
vi.mock("../hooks/useAutomation");
vi.mock("../hooks/useWebSocket", () => ({
  useWebSocket: () => ({ messages: [], isConnected: false, clearMessages: vi.fn() }),
}));

describe("FAQPanel", () => {
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

  it("renders FAQ panel with run button", () => {
    render(<FAQPanel client="default" />);
    expect(screen.getByTestId("faq-panel")).toBeTruthy();
    expect(screen.getByTestId("faq-run-button")).toBeTruthy();
  });

  it("renders audio dir selector", () => {
    render(<FAQPanel client="default" />);
    expect(screen.getByTestId("audio-dir-input")).toBeTruthy();
  });

  it("renders option checkboxes", () => {
    render(<FAQPanel client="default" />);
    expect(screen.getByTestId("faq-option-headless")).toBeTruthy();
    expect(screen.getByTestId("faq-option-dry_run")).toBeTruthy();
    expect(screen.getByTestId("faq-option-debug")).toBeTruthy();
  });

  it("run button is disabled without CSV", () => {
    render(<FAQPanel client="default" />);
    const btn = screen.getByTestId("faq-run-button") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it("shows Running... text and keeps button disabled when isRunning", () => {
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: true,
      jobId: "job-123",
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
    render(<FAQPanel client="default" />);
    const btn = screen.getByTestId("faq-run-button") as HTMLButtonElement;
    expect(btn.textContent).toBe("Running...");
    expect(btn.disabled).toBe(true);
  });

  it("advanced toggle shows and hides start-product and limit fields", () => {
    render(<FAQPanel client="default" />);
    expect(screen.queryByTestId("faq-option-start-product")).toBeNull();
    expect(screen.queryByTestId("faq-option-limit")).toBeNull();

    fireEvent.click(screen.getByTestId("faq-toggle-advanced"));
    expect(screen.getByTestId("faq-option-start-product")).toBeTruthy();
    expect(screen.getByTestId("faq-option-limit")).toBeTruthy();

    fireEvent.click(screen.getByTestId("faq-toggle-advanced"));
    expect(screen.queryByTestId("faq-option-start-product")).toBeNull();
  });

  it("product list renders when versions present", () => {
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: false,
      jobId: null,
      progress: { current: 0, total: 0 },
      versions: [
        { name: "Product A", status: "success" },
        { name: "Product B", status: "failed" },
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
    render(<FAQPanel client="default" />);
    expect(screen.getByTestId("product-list")).toBeTruthy();
    expect(screen.getByText("Product A")).toBeTruthy();
    expect(screen.getByText("Product B")).toBeTruthy();
  });

  it("error banner shows when automation error is set", () => {
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: false,
      jobId: null,
      progress: { current: 0, total: 0 },
      versions: [],
      error: "FAQ run failed",
      wsUrl: null,
      polledMessages: [],
      startRun: vi.fn(),
      handleMessage: vi.fn(),
      reset: vi.fn(),
      pollJobStatus: vi.fn(),
      cancelJob: vi.fn(),
    });
    render(<FAQPanel client="default" />);
    const errorBanner = screen.getByTestId("faq-error");
    expect(errorBanner).toBeTruthy();
    expect(errorBanner.textContent).toBe("FAQ run failed");
  });

  it("progress bar shows when progress.current > 0", () => {
    vi.mocked(useAutomation).mockReturnValue({
      isRunning: false,
      jobId: null,
      progress: { current: 2, total: 5 },
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
    render(<FAQPanel client="default" />);
    expect(screen.getByTestId("progress-bar")).toBeTruthy();
  });
});
