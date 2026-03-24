import React from "react";

const isWindows = typeof navigator !== "undefined" && navigator.userAgent.includes("Windows");

export function Titlebar(): React.ReactElement | null {
  const handleMinimize = async () => {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().minimize();
  };

  const handleMaximize = async () => {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().toggleMaximize();
  };

  const handleClose = async () => {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().hide();
  };

  if (!isWindows) {
    return null;
  }

  return (
    <div
      data-tauri-drag-region
      data-testid="titlebar"
      className="h-8 flex items-center shrink-0 select-none bg-[var(--bg-surface)] justify-end"
    >
      {isWindows && (
        <div className="flex">
          <button
            data-testid="titlebar-minimize"
            onClick={handleMinimize}
            className="h-8 w-11 flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors text-xs border-none bg-transparent cursor-pointer"
            aria-label="Minimize"
          >
            −
          </button>
          <button
            data-testid="titlebar-maximize"
            onClick={handleMaximize}
            className="h-8 w-11 flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors text-xs border-none bg-transparent cursor-pointer"
            aria-label="Maximize"
          >
            □
          </button>
          <button
            data-testid="titlebar-close"
            onClick={handleClose}
            className="h-8 w-11 flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--error)] hover:text-white transition-colors text-xs border-none bg-transparent cursor-pointer"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
