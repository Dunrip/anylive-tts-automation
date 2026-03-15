import React from "react";

/**
 * ThemePreview - displays all Raycast design tokens visually.
 * Used for design system verification.
 */
export function ThemePreview(): React.ReactElement {
  return (
    <div className="p-6 space-y-4" style={{ backgroundColor: "var(--bg-base)" }}>
      <h2 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
        AnyLive TTS — Design Tokens
      </h2>
      
      {/* Surface colors */}
      <div className="space-y-2">
        <p className="mono" style={{ color: "var(--text-secondary)" }}>Surfaces</p>
        <div className="flex gap-2">
          <div className="w-16 h-12 rounded border" style={{ backgroundColor: "var(--bg-base)", borderColor: "var(--border-default)" }} title="--bg-base" />
          <div className="w-16 h-12 rounded border" style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-default)" }} title="--bg-surface" />
          <div className="w-16 h-12 rounded border" style={{ backgroundColor: "var(--bg-elevated)", borderColor: "var(--border-default)" }} title="--bg-elevated" />
          <div className="w-16 h-12 rounded border" style={{ backgroundColor: "var(--bg-hover)", borderColor: "var(--border-default)" }} title="--bg-hover" />
        </div>
      </div>

      {/* Status colors */}
      <div className="space-y-2">
        <p className="mono" style={{ color: "var(--text-secondary)" }}>Status</p>
        <div className="flex gap-2">
          <div className="w-16 h-8 rounded flex items-center justify-center text-white text-xs" style={{ backgroundColor: "var(--accent)" }}>Accent</div>
          <div className="w-16 h-8 rounded flex items-center justify-center text-white text-xs" style={{ backgroundColor: "var(--success)" }}>Success</div>
          <div className="w-16 h-8 rounded flex items-center justify-center text-white text-xs" style={{ backgroundColor: "var(--error)" }}>Error</div>
          <div className="w-16 h-8 rounded flex items-center justify-center text-white text-xs" style={{ backgroundColor: "var(--warning)" }}>Warning</div>
        </div>
      </div>
    </div>
  );
}
