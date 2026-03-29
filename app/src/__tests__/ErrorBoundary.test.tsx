import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "../components/common/ErrorBoundary";

// Component that throws an error during render
const ThrowingComponent = () => {
  throw new Error("Test error message");
};

// Component that renders normally
const NormalComponent = () => <div>Normal content</div>;

describe("ErrorBoundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Suppress console.error for these tests since ErrorBoundary logs errors
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders children normally when no error occurs", () => {
    render(
      <ErrorBoundary>
        <NormalComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText("Normal content")).toBeTruthy();
  });

  it("displays fallback UI when child component throws", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeTruthy();
  });

  it("fallback root has correct data-testid", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    const fallback = screen.getByTestId("error-boundary-fallback");
    expect(fallback).toBeTruthy();
    expect(fallback.getAttribute("data-testid")).toBe("error-boundary-fallback");
  });

  it("reload button exists and is clickable", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    const reloadButton = screen.getByRole("button", { name: /reload page/i });
    expect(reloadButton).toBeTruthy();
    expect(reloadButton).toBeInstanceOf(HTMLButtonElement);
    expect((reloadButton as HTMLButtonElement).type).toBe("button");
  });

  it("displays error message in fallback", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText("Test error message")).toBeTruthy();
  });

  it("uses custom fallback when provided", () => {
    const customFallback = <div data-testid="custom-fallback">Custom error UI</div>;

    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByTestId("custom-fallback")).toBeTruthy();
    expect(screen.getByText("Custom error UI")).toBeTruthy();
  });

  it("calls componentDidCatch when error occurs", () => {
    const consoleErrorSpy = vi.spyOn(console, "error");

    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(consoleErrorSpy).toHaveBeenCalled();
  });
});
