import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThemePreview } from "../components/common/ThemePreview";

describe("ThemePreview", () => {
  it("renders the design tokens preview", () => {
    render(<ThemePreview />);
    expect(screen.getByText("AnyLive TTS — Design Tokens")).toBeTruthy();
  });

  it("renders surfaces section", () => {
    render(<ThemePreview />);
    expect(screen.getByText("Surfaces")).toBeTruthy();
  });

  it("renders status colors section", () => {
    render(<ThemePreview />);
    expect(screen.getByText("Status")).toBeTruthy();
  });
});
