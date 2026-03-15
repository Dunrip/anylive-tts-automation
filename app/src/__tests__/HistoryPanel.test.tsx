import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { HistoryPanel } from "../components/history/HistoryPanel";

vi.mock("../hooks/useHistory", () => ({
  useHistory: () => ({
    runs: [
      {
        id: "run-1",
        automation_type: "tts",
        client: "default",
        status: "success",
        started_at: "2026-01-01T10:00:00Z",
        finished_at: "2026-01-01T10:05:00Z",
        versions_total: 10,
        versions_success: 10,
        versions_failed: 0,
        error: null,
      },
      {
        id: "run-2",
        automation_type: "faq",
        client: "default",
        status: "failed",
        started_at: "2026-01-01T09:00:00Z",
        finished_at: "2026-01-01T09:02:00Z",
        versions_total: 5,
        versions_success: 3,
        versions_failed: 2,
        error: "Connection timeout",
      },
    ],
    loading: false,
    error: null,
    refresh: vi.fn(),
  }),
}));

describe("HistoryPanel", () => {
  it("renders history panel with table", () => {
    render(<HistoryPanel />);
    expect(screen.getByTestId("history-panel")).toBeTruthy();
  });

  it("renders history rows", () => {
    render(<HistoryPanel />);
    expect(screen.getByTestId("history-row-run-1")).toBeTruthy();
    expect(screen.getByTestId("history-row-run-2")).toBeTruthy();
  });

  it("filters by type - TTS only", () => {
    render(<HistoryPanel />);
    fireEvent.click(screen.getByTestId("filter-tts"));
    expect(screen.getByTestId("history-row-run-1")).toBeTruthy();
    expect(screen.queryByTestId("history-row-run-2")).toBeNull();
  });

  it("filters by type - FAQ only", () => {
    render(<HistoryPanel />);
    fireEvent.click(screen.getByTestId("filter-faq"));
    expect(screen.queryByTestId("history-row-run-1")).toBeNull();
    expect(screen.getByTestId("history-row-run-2")).toBeTruthy();
  });

  it("expands row on click to show details", () => {
    render(<HistoryPanel />);
    fireEvent.click(screen.getByTestId("history-row-run-1"));
    expect(screen.getByTestId("history-detail-run-1")).toBeTruthy();
  });

  it("collapses row on second click", () => {
    render(<HistoryPanel />);
    fireEvent.click(screen.getByTestId("history-row-run-1"));
    expect(screen.getByTestId("history-detail-run-1")).toBeTruthy();
    fireEvent.click(screen.getByTestId("history-row-run-1"));
    expect(screen.queryByTestId("history-detail-run-1")).toBeNull();
  });
});
