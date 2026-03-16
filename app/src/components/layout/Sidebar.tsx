import React, { useState, useRef, useEffect } from "react";
import { NAV_ITEMS, PanelType } from "../../lib/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface SidebarProps {
  activePanel: PanelType;
  onPanelChange: (panel: PanelType) => void;
  clients: string[];
  selectedClient: string;
  onClientChange: (client: string) => void;
  sessionValid: boolean;
  sidecarUrl?: string | null;
  onRelogin?: () => void;
  onClientCreated?: (name: string) => void;
  onClientDeleted?: (name: string) => void;
}

function ClientSelect({
  clients,
  selected,
  onChange,
}: {
  clients: string[];
  selected: string;
  onChange: (client: string) => void;
}): React.ReactElement {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent): void => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        data-testid="client-switcher"
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="w-full flex items-center justify-between bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md px-2 py-1.5 text-[13px] cursor-pointer text-left"
      >
        <span>{selected}</span>
        <span className={cn("text-[10px] text-[var(--text-muted)] transition-transform", open && "rotate-180")}>\u25BE</span>
      </button>
      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+4px)] z-50 bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md py-1 shadow-lg max-h-[200px] overflow-y-auto">
          {clients.map((client) => (
            <button
              key={client}
              type="button"
              onClick={() => { onChange(client); setOpen(false); }}
              className={cn(
                "w-full text-left px-2.5 py-1.5 text-[13px] border-none cursor-pointer transition-colors",
                client === selected
                  ? "bg-primary/20 text-[var(--text-primary)] font-medium"
                  : "bg-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
              )}
            >
              {client}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Sidebar({
  activePanel,
  onPanelChange,
  clients,
  selectedClient,
  onClientChange,
  sessionValid,
  sidecarUrl,
  onRelogin,
  onClientCreated,
  onClientDeleted,
}: SidebarProps): React.ReactElement {
  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const handleCreate = async (): Promise<void> => {
    const name = newName.trim();
    if (!name) return;
    if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
      setCreateError("Use only letters, numbers, hyphens, underscores");
      return;
    }
    setCreateError(null);

    if (sidecarUrl) {
      try {
        const resp = await fetch(`${sidecarUrl}/api/configs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({ detail: "Failed" }));
          setCreateError(err.detail || "Failed");
          return;
        }
      } catch {
        setCreateError("Could not connect to sidecar");
        return;
      }
    } else {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("create_client_config", { name });
      } catch (err: unknown) {
        setCreateError(String(err) || "Failed to create config directory");
        return;
      }
    }
    onClientCreated?.(name);
    setNewName("");
    setIsCreating(false);
  };

  const handleDelete = async (): Promise<void> => {
    if (selectedClient === "default") return;
    if (!confirm(`Delete client "${selectedClient}"? This removes its config files.`)) return;
    try {
      if (sidecarUrl) {
        // No sidecar delete endpoint yet — use Rust
      }
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("delete_client_config", { name: selectedClient });
      onClientDeleted?.(selectedClient);
    } catch (err: unknown) {
      setCreateError(String(err));
    }
  };

  return (
    <aside className="w-[220px] min-w-[220px] h-full bg-[var(--bg-surface)] border-r border-[var(--border-default)] flex flex-col py-3">
      {/* App title */}
      <div className="px-4 pb-3 border-b border-[var(--border-default)] mb-2">
        <h1 className="text-sm font-semibold text-[var(--text-primary)] m-0">
          AnyLive TTS
        </h1>
      </div>

      {/* Client switcher */}
      <div className="px-3 pb-3">
        <div className="flex items-center justify-between mb-1">
          <label className="text-[11px] text-[var(--text-muted)]">CLIENT</label>
          <div className="flex gap-2">
            {selectedClient !== "default" && (
              <button
                data-testid="delete-client-button"
                onClick={handleDelete}
                className="text-[10px] text-[var(--text-muted)] hover:text-[var(--error)] bg-transparent border-none cursor-pointer p-0 transition-colors"
              >
                Delete
              </button>
            )}
            <button
              data-testid="new-client-button"
              onClick={() => setIsCreating((prev) => !prev)}
              className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text-secondary)] bg-transparent border-none cursor-pointer p-0 transition-colors"
            >
              {isCreating ? "Cancel" : "+ New"}
            </button>
          </div>
        </div>
        <ClientSelect
          clients={clients}
          selected={selectedClient}
          onChange={onClientChange}
        />
        {isCreating && (
          <div className="flex flex-col gap-1.5 mt-2">
            <input
              data-testid="new-client-input"
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              placeholder="client-name"
              autoFocus
              className="w-full px-2 py-1.5 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-default)] rounded-md text-[13px]"
            />
            <Button data-testid="create-client-button" size="xs" onClick={handleCreate} disabled={!newName.trim()} className="w-full">
              Create
            </Button>
            {createError && (
              <span className="text-[10px] text-[var(--error)]">{createError}</span>
            )}
          </div>
        )}
      </div>

      {/* Navigation items */}
      <nav className="flex-1 px-2">
        {NAV_ITEMS.map((item) => {
          const isActive = activePanel === item.panel;
          return (
            <button
              key={item.id}
              data-testid={`nav-${item.id}`}
              onClick={() => onPanelChange(item.panel)}
              className={cn(
                "w-full flex items-center gap-2.5 px-3 py-2 rounded-md border-none cursor-pointer text-[13px] text-left mb-0.5 border-l-2",
                isActive
                  ? "bg-[var(--bg-hover)] text-[var(--text-primary)] font-medium border-l-primary"
                  : "bg-transparent text-[var(--text-secondary)] font-normal border-l-transparent"
              )}
            >
              <span className="text-base">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Session indicator */}
      <div className="px-4 py-3 border-t border-[var(--border-default)]">
        <div className="flex items-center gap-2 mb-2">
          <div
            data-testid="sidecar-dot"
            className={cn("size-2 rounded-full shrink-0", sidecarUrl ? "bg-[var(--success)]" : "bg-[var(--warning)]")}
          />
          <span className="text-xs text-[var(--text-secondary)]">
            {sidecarUrl ? "Sidecar Connected" : "Sidecar Connecting"}
          </span>
        </div>

        <div className={cn("flex items-center gap-2", sessionValid ? "mb-0" : "mb-2")}>
          <div
            data-testid="session-dot"
            className={cn("size-2 rounded-full shrink-0", sessionValid ? "bg-[var(--success)]" : "bg-[var(--error)]")}
          />
          <span className={cn("text-xs", sessionValid ? "text-[var(--success)]" : "text-[var(--error)]")}>
            {sessionValid ? "Session Active" : "Session Expired"}
          </span>
        </div>
        {!sessionValid && onRelogin && (
          <Button data-testid="relogin-button" size="xs" onClick={onRelogin} className="w-full">Re-login</Button>
        )}
      </div>
    </aside>
  );
}
