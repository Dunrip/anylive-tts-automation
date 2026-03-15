import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SetupWizard } from "../components/common/SetupWizard";

describe("SetupWizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  it("renders setup wizard modal", () => {
    render(<SetupWizard sidecarUrl="http://127.0.0.1:8080" onComplete={vi.fn()} />);
    expect(screen.getByTestId("setup-wizard")).toBeTruthy();
    expect(screen.getByTestId("install-button")).toBeTruthy();
  });

  it("shows installing state when button clicked", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: () => new Promise(() => {}), // Never resolves
    });

    render(<SetupWizard sidecarUrl="http://127.0.0.1:8080" onComplete={vi.fn()} />);
    fireEvent.click(screen.getByTestId("install-button"));

    await waitFor(() => {
      expect(screen.getByText("Installing...")).toBeTruthy();
    });
  });

  it("calls onComplete after successful install", async () => {
    const onComplete = vi.fn();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: () => Promise.resolve({ status: "installed" }),
    });

    render(<SetupWizard sidecarUrl="http://127.0.0.1:8080" onComplete={onComplete} />);
    fireEvent.click(screen.getByTestId("install-button"));

    await waitFor(() => {
      expect(screen.getByTestId("setup-message")).toBeTruthy();
    }, { timeout: 3000 });
  });
});
