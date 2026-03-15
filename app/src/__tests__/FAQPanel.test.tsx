import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { FAQPanel } from "../components/faq/FAQPanel";

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

describe("FAQPanel", () => {
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
});
