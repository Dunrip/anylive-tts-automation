import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SettingsPanel } from "../components/settings/SettingsPanel";

describe("SettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  it("renders all TTS config form fields", () => {
    render(<SettingsPanel client="default" />);
    expect(screen.getByTestId("settings-panel")).toBeTruthy();
    expect(screen.getByTestId("input-version-template")).toBeTruthy();
    expect(screen.getByTestId("input-voice-name")).toBeTruthy();
    expect(screen.getByTestId("input-max-scripts")).toBeTruthy();
  });

  it("renders CSV column mapping fields", () => {
    render(<SettingsPanel client="default" />);
    expect(screen.getByTestId("input-csv-product_number")).toBeTruthy();
    expect(screen.getByTestId("input-csv-product_name")).toBeTruthy();
    expect(screen.getByTestId("input-csv-script_content")).toBeTruthy();
    expect(screen.getByTestId("input-csv-audio_code")).toBeTruthy();
  });

  it("renders save and reset buttons", () => {
    render(<SettingsPanel client="default" />);
    expect(screen.getByTestId("save-button")).toBeTruthy();
    expect(screen.getByTestId("reset-button")).toBeTruthy();
  });

  it("loads config from sidecar on mount", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        tts: {
          base_url: "https://example.com",
          version_template: "MyTemplate",
          voice_name: "MyVoice",
          max_scripts_per_version: 5,
          csv_columns: { product_number: "No.", product_name: "Name", script_content: "Script", audio_code: "Code" },
        },
      }),
    });

    render(<SettingsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);

    await waitFor(() => {
      const input = screen.getByTestId("input-version-template") as HTMLInputElement;
      expect(input.value).toBe("MyTemplate");
    });
  });

  it("calls PUT when save button clicked", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ tts: {} }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ status: "saved" }) });

    render(<SettingsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);

    await waitFor(() => {}); // Wait for initial load

    fireEvent.click(screen.getByTestId("save-button"));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/configs/default"),
        expect.objectContaining({ method: "PUT" })
      );
    });
  });

  it("resets to original values when reset clicked", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        tts: { base_url: "", version_template: "MyTemplate", voice_name: "", max_scripts_per_version: 10, csv_columns: {} },
      }),
    });

    render(<SettingsPanel client="default" sidecarUrl="http://127.0.0.1:8080" />);

    await waitFor(() => {
      const input = screen.getByTestId("input-version-template") as HTMLInputElement;
      expect(input.value).toBe("MyTemplate");
    });

    // Change value
    fireEvent.change(screen.getByTestId("input-version-template"), { target: { value: "ChangedTemplate" } });

    // Reset
    fireEvent.click(screen.getByTestId("reset-button"));

    await waitFor(() => {
      const input = screen.getByTestId("input-version-template") as HTMLInputElement;
      expect(input.value).toBe("MyTemplate");
    });
  });
});
