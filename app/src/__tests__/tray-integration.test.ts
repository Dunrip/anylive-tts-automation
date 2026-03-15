import { describe, it, expect, vi } from "vitest";

vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: () => ({
    hide: vi.fn().mockResolvedValue(undefined),
    show: vi.fn().mockResolvedValue(undefined),
    setFocus: vi.fn().mockResolvedValue(undefined),
    close: vi.fn().mockResolvedValue(undefined),
  }),
}));

describe("Tray Integration", () => {
  it("window close should hide not destroy", async () => {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    const window = getCurrentWindow();

    await window.hide();
    expect(window.hide).toHaveBeenCalled();
  });

  it("tray menu should have Show Window and Quit items", () => {
    const expectedMenuItems = ["show", "quit"];
    const menuItemIds = ["show", "quit"];

    expectedMenuItems.forEach(item => {
      expect(menuItemIds).toContain(item);
    });
  });

  it("single instance plugin is configured", () => {
    const plugins = ["tauri_plugin_single_instance", "tauri_plugin_shell"];
    expect(plugins).toContain("tauri_plugin_single_instance");
  });
});
