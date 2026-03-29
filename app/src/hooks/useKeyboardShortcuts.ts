import { useEffect, useCallback } from "react";
import type { PanelType } from "../lib/navigation";

interface ShortcutHandlers {
  onPanelChange: (panel: PanelType) => void;
  onRun?: () => void;
  onToggleLog?: () => void;
  onOpenCsv?: () => void;
  onFocusClientSwitcher?: () => void;
}

const PANEL_SHORTCUTS: Record<string, PanelType> = {
  "1": "tts",
  "2": "faq",
  "3": "scripts",
  "4": "history",
  "5": "settings",
  ",": "settings",
};

function getModifierKey(): string {
  if (typeof navigator === "undefined") return "Control";
  return navigator.userAgent.includes("Mac") ? "Meta" : "Control";
}

export function useKeyboardShortcuts(handlers: ShortcutHandlers): void {
  const handleKeyDown = useCallback(
    (event: KeyboardEvent): void => {
      const modifierKey = getModifierKey();
      const isModifier = modifierKey === "Meta" ? event.metaKey : event.ctrlKey;

      if (!isModifier) return;

      const key = event.key;

      // Panel navigation: ⌘1-5 and ⌘,
      if (PANEL_SHORTCUTS[key]) {
        event.preventDefault();
        handlers.onPanelChange(PANEL_SHORTCUTS[key]);
        return;
      }

      // Run: ⌘R
      if (key === "r" || key === "R") {
        event.preventDefault();
        handlers.onRun?.();
        return;
      }

      // Toggle log: ⌘L
      if (key === "l" || key === "L") {
        event.preventDefault();
        handlers.onToggleLog?.();
        return;
      }

      // Open CSV: ⌘O
      if (key === "o" || key === "O") {
        event.preventDefault();
        handlers.onOpenCsv?.();
        return;
      }

      // Focus client switcher: ⌘K
      if (key === "k" || key === "K") {
        event.preventDefault();
        handlers.onFocusClientSwitcher?.();
        return;
      }
    },
    [handlers]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);
}

export { getModifierKey };
