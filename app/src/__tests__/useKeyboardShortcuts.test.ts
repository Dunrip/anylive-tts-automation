import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useKeyboardShortcuts, getModifierKey } from "../hooks/useKeyboardShortcuts";
import type { PanelType } from "../lib/navigation";

describe("getModifierKey", () => {
  const originalPlatform = navigator.platform;

  afterEach(() => {
    Object.defineProperty(navigator, "platform", {
      value: originalPlatform,
      configurable: true,
    });
  });

  it("returns Meta on macOS", () => {
    Object.defineProperty(navigator, "platform", {
      value: "MacIntel",
      configurable: true,
    });
    expect(getModifierKey()).toBe("Meta");
  });

  it("returns Meta on Macbook Pro", () => {
    Object.defineProperty(navigator, "platform", {
      value: "MacPPC",
      configurable: true,
    });
    expect(getModifierKey()).toBe("Meta");
  });

  it("returns Control on Windows", () => {
    Object.defineProperty(navigator, "platform", {
      value: "Win32",
      configurable: true,
    });
    expect(getModifierKey()).toBe("Control");
  });

  it("returns Control on Linux", () => {
    Object.defineProperty(navigator, "platform", {
      value: "Linux x86_64",
      configurable: true,
    });
    expect(getModifierKey()).toBe("Control");
  });

  it("returns Control as default fallback", () => {
    Object.defineProperty(navigator, "platform", {
      value: "Unknown",
      configurable: true,
    });
    expect(getModifierKey()).toBe("Control");
  });
});

describe("useKeyboardShortcuts", () => {
  const originalPlatform = navigator.platform;
  let mockOnPanelChange: ReturnType<typeof vi.fn>;
  let mockOnRun: ReturnType<typeof vi.fn>;
  let mockOnToggleLog: ReturnType<typeof vi.fn>;
  let mockOnOpenCsv: ReturnType<typeof vi.fn>;
  let mockOnFocusClientSwitcher: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockOnPanelChange = vi.fn();
    mockOnRun = vi.fn();
    mockOnToggleLog = vi.fn();
    mockOnOpenCsv = vi.fn();
    mockOnFocusClientSwitcher = vi.fn();
    Object.defineProperty(navigator, "platform", {
      value: "MacIntel",
      configurable: true,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, "platform", {
      value: originalPlatform,
      configurable: true,
    });
  });

  describe("Panel navigation shortcuts", () => {
    it("⌘1 navigates to TTS panel", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "1",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnPanelChange).toHaveBeenCalledWith("tts");
    });

    it("⌘2 navigates to FAQ panel", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "2",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnPanelChange).toHaveBeenCalledWith("faq");
    });

    it("⌘3 navigates to Scripts panel", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "3",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnPanelChange).toHaveBeenCalledWith("scripts");
    });

    it("⌘4 navigates to History panel", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "4",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnPanelChange).toHaveBeenCalledWith("history");
    });

    it("⌘5 navigates to Settings panel", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "5",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnPanelChange).toHaveBeenCalledWith("settings");
    });

    it("⌘, navigates to Settings panel", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: ",",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnPanelChange).toHaveBeenCalledWith("settings");
    });
  });

  describe("Action shortcuts", () => {
    it("⌘R calls onRun", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
          onRun: mockOnRun as () => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "r",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnRun).toHaveBeenCalled();
    });

    it("⌘R (uppercase) calls onRun", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
          onRun: mockOnRun as () => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "R",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnRun).toHaveBeenCalled();
    });

    it("⌘L calls onToggleLog", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
          onToggleLog: mockOnToggleLog as () => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "l",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnToggleLog).toHaveBeenCalled();
    });

    it("⌘O calls onOpenCsv", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
          onOpenCsv: mockOnOpenCsv as () => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "o",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnOpenCsv).toHaveBeenCalled();
    });

    it("⌘K calls onFocusClientSwitcher", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
          onFocusClientSwitcher: mockOnFocusClientSwitcher as () => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "k",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnFocusClientSwitcher).toHaveBeenCalled();
    });
  });

  describe("Modifier key detection", () => {
    it("does not trigger without modifier key", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "1",
        metaKey: false,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnPanelChange).not.toHaveBeenCalled();
    });

    it("uses Control key on Windows", () => {
      Object.defineProperty(navigator, "platform", {
        value: "Win32",
        configurable: true,
      });

      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "1",
        ctrlKey: true,
        metaKey: false,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnPanelChange).toHaveBeenCalledWith("tts");
    });

    it("ignores Control key on macOS", () => {
      Object.defineProperty(navigator, "platform", {
        value: "MacIntel",
        configurable: true,
      });

      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "1",
        ctrlKey: true,
        metaKey: false,
        bubbles: true,
      });
      window.dispatchEvent(event);

      expect(mockOnPanelChange).not.toHaveBeenCalled();
    });
  });

  describe("Event prevention", () => {
    it("prevents default on panel navigation", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "1",
        metaKey: true,
        bubbles: true,
      });
      const preventDefaultSpy = vi.spyOn(event, "preventDefault");

      window.dispatchEvent(event);

      expect(preventDefaultSpy).toHaveBeenCalled();
    });

    it("prevents default on action shortcuts", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
          onRun: mockOnRun as () => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "r",
        metaKey: true,
        bubbles: true,
      });
      const preventDefaultSpy = vi.spyOn(event, "preventDefault");

      window.dispatchEvent(event);

      expect(preventDefaultSpy).toHaveBeenCalled();
    });
  });

  describe("Optional handlers", () => {
    it("handles missing onRun handler gracefully", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "r",
        metaKey: true,
        bubbles: true,
      });

      expect(() => window.dispatchEvent(event)).not.toThrow();
    });

    it("handles missing onToggleLog handler gracefully", () => {
      renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      const event = new KeyboardEvent("keydown", {
        key: "l",
        metaKey: true,
        bubbles: true,
      });

      expect(() => window.dispatchEvent(event)).not.toThrow();
    });
  });

  describe("Cleanup", () => {
    it("removes event listener on unmount", () => {
      const removeEventListenerSpy = vi.spyOn(window, "removeEventListener");

      const { unmount } = renderHook(() =>
        useKeyboardShortcuts({
          onPanelChange: mockOnPanelChange as (panel: PanelType) => void,
        })
      );

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        "keydown",
        expect.any(Function)
      );
    });
  });
});
