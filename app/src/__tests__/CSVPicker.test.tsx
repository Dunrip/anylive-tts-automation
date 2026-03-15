import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CSVPicker } from "../components/common/CSVPicker";

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
}));

describe("CSVPicker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders select button", () => {
    render(<CSVPicker />);
    expect(screen.getByTestId("select-csv-button")).toBeTruthy();
  });

  it("shows file name after selection", async () => {
    const { open } = await import("@tauri-apps/plugin-dialog");
    (open as ReturnType<typeof vi.fn>).mockResolvedValue("/path/to/data.csv");

    render(<CSVPicker />);
    fireEvent.click(screen.getByTestId("select-csv-button"));

    await waitFor(() => {
      expect(screen.getByTestId("selected-file-name")).toBeTruthy();
      expect(screen.getByText("data.csv")).toBeTruthy();
    });
  });

  it("shows clear button after selection", async () => {
    const { open } = await import("@tauri-apps/plugin-dialog");
    (open as ReturnType<typeof vi.fn>).mockResolvedValue("/path/to/data.csv");

    render(<CSVPicker />);
    fireEvent.click(screen.getByTestId("select-csv-button"));

    await waitFor(() => {
      expect(screen.getByTestId("clear-csv-button")).toBeTruthy();
    });
  });

  it("clears selection when clear button clicked", async () => {
    const { open } = await import("@tauri-apps/plugin-dialog");
    (open as ReturnType<typeof vi.fn>).mockResolvedValue("/path/to/data.csv");
    const onClear = vi.fn();

    render(<CSVPicker onClear={onClear} />);
    fireEvent.click(screen.getByTestId("select-csv-button"));

    await waitFor(() => {
      expect(screen.getByTestId("clear-csv-button")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("clear-csv-button"));
    expect(onClear).toHaveBeenCalled();
  });

  it("shows preview when sidecarUrl provided", async () => {
    const { open } = await import("@tauri-apps/plugin-dialog");
    (open as ReturnType<typeof vi.fn>).mockResolvedValue("/path/to/data.csv");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        rows: 10,
        products: 3,
        estimated_versions: 3,
        preview: [{ no: "1", product_name: "Product A", script: "Script text", audio_code: "SFD1" }],
        errors: [],
      }),
    });

    render(<CSVPicker sidecarUrl="http://127.0.0.1:8080" configPath="configs/default/tts.json" />);
    fireEvent.click(screen.getByTestId("select-csv-button"));

    await waitFor(() => {
      expect(screen.getByTestId("csv-summary")).toBeTruthy();
      expect(screen.getByText(/10 rows/)).toBeTruthy();
    });
  });
});
