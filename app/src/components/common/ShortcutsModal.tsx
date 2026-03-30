import React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getModifierKey } from "@/hooks/useKeyboardShortcuts";

interface ShortcutsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function getModifierDisplay(): string {
  return getModifierKey() === "Meta" ? "⌘" : "Ctrl";
}

export function ShortcutsModal({
  open,
  onOpenChange,
}: ShortcutsModalProps): React.ReactElement {
  const mod = getModifierDisplay();

  const shortcuts = [
    { keys: [`${mod}1`], description: "TTS Panel" },
    { keys: [`${mod}2`], description: "FAQ Panel" },
    { keys: [`${mod}3`], description: "Scripts Panel" },
    { keys: [`${mod}4`], description: "History Panel" },
    { keys: [`${mod}5`, `${mod},`], description: "Settings" },
    { keys: [`${mod}R`], description: "Run automation" },
    { keys: [`${mod}L`], description: "Toggle log panel" },
    { keys: [`${mod}O`], description: "Open CSV file" },
    { keys: [`${mod}K`], description: "Focus client switcher" },
    { keys: [`${mod}?`], description: "This help" },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm bg-[var(--bg-surface)] text-[var(--text-primary)]">
        <DialogHeader>
          <DialogTitle>Keyboard Shortcuts</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-2 mt-1">
          {shortcuts.map(({ keys, description }) => (
            <div
              key={description}
              className="flex items-center justify-between gap-4"
            >
              <span className="text-sm text-[var(--text-secondary)]">
                {description}
              </span>
              <div className="flex items-center gap-1">
                {keys.map((key, i) => (
                  <React.Fragment key={key}>
                    {i > 0 && (
                      <span className="text-xs text-[var(--text-muted)]">/</span>
                    )}
                    <kbd className="bg-[var(--bg-elevated)] px-2 py-0.5 rounded text-xs font-mono text-[var(--text-primary)] ring-1 ring-[var(--border-default)]">
                      {key}
                    </kbd>
                  </React.Fragment>
                ))}
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
