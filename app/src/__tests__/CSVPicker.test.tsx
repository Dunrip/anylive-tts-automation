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
      expect(screen.getByTestId("toggle-csv-preview")).toBeTruthy();
    });
  });

  it("preview table is collapsed by default", async () => {
    const { open } = await import("@tauri-apps/plugin-dialog");
    (open as ReturnType<typeof vi.fn>).mockResolvedValue("/path/to/data.csv");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        rows: 15,
        products: 3,
        estimated_versions: 3,
        preview: Array.from({ length: 15 }, (_, i) => ({
          no: String(i + 1),
          product_name: `Product ${i + 1}`,
          script: `Script ${i + 1}`,
          audio_code: `SFD${i + 1}`,
        })),
        errors: [],
      }),
    });

    render(<CSVPicker sidecarUrl="http://127.0.0.1:8080" configPath="configs/default/tts.json" />);
    fireEvent.click(screen.getByTestId("select-csv-button"));

    await waitFor(() => {
      expect(screen.getByTestId("csv-summary")).toBeTruthy();
    });

    // Table should NOT be visible (collapsed by default)
    expect(screen.queryByTestId("csv-preview-table")).not.toBeInTheDocument();
    // Toggle button should be present
    expect(screen.getByTestId("toggle-csv-preview")).toBeInTheDocument();
  });

  it("preview table expands and collapses on toggle click", async () => {
    const { open } = await import("@tauri-apps/plugin-dialog");
    (open as ReturnType<typeof vi.fn>).mockResolvedValue("/path/to/data.csv");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        rows: 5,
        products: 2,
        estimated_versions: 2,
        preview: Array.from({ length: 5 }, (_, i) => ({
          no: String(i + 1),
          product_name: `Product ${i + 1}`,
          script: `Script ${i + 1}`,
          audio_code: `SFD${i + 1}`,
        })),
        errors: [],
      }),
    });

    render(<CSVPicker sidecarUrl="http://127.0.0.1:8080" configPath="configs/default/tts.json" />);
    fireEvent.click(screen.getByTestId("select-csv-button"));

    await waitFor(() => {
      expect(screen.getByTestId("toggle-csv-preview")).toBeInTheDocument();
    });

    // Expand
    fireEvent.click(screen.getByTestId("toggle-csv-preview"));
    expect(screen.getByTestId("csv-preview-table")).toBeInTheDocument();

    // Collapse
    fireEvent.click(screen.getByTestId("toggle-csv-preview"));
    expect(screen.queryByTestId("csv-preview-table")).not.toBeInTheDocument();
  });

  it("renders all rows from backend response", async () => {
    const { open } = await import("@tauri-apps/plugin-dialog");
    (open as ReturnType<typeof vi.fn>).mockResolvedValue("/path/to/data.csv");

    const mockRows = Array.from({ length: 15 }, (_, i) => ({
      no: String(i + 1),
      product_name: `Product ${i + 1}`,
      script: `Script ${i + 1}`,
      audio_code: `SFD${i + 1}`,
    }));

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        rows: 15,
        products: 3,
        estimated_versions: 3,
        preview: mockRows,
        errors: [],
      }),
    });

    render(<CSVPicker sidecarUrl="http://127.0.0.1:8080" configPath="configs/default/tts.json" />);
    fireEvent.click(screen.getByTestId("select-csv-button"));

    await waitFor(() => {
      expect(screen.getByTestId("toggle-csv-preview")).toBeInTheDocument();
    });

    // Expand to see rows
    fireEvent.click(screen.getByTestId("toggle-csv-preview"));

    // All 15 rows should be rendered
    const table = screen.getByTestId("csv-preview-table");
    const rows = table.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(15);
  });
});
