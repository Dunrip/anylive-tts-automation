import { test as base, expect } from "@playwright/test";

export const SIDECAR_URL = "http://127.0.0.1:8765";

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.addInitScript(() => {
      (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {
        invoke: async (cmd: string) => {
          if (cmd === "list_client_configs") return ["default"];
          if (cmd === "create_client_config") return { status: "ok" };
          if (cmd === "delete_client_config") return { status: "ok" };
          if (cmd === "get_sidecar_port") return 8765;
          return null;
        },
        metadata: {},
        plugins: {},
        transformCallback: () => 0,
      };
    });

    await page.route("**/api/session/**", (route) => {
      void route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ valid: true, display_name: "Test User", email: "test@example.com" }),
      });
    });

    await page.route("**/api/setup/chromium-status", (route) => {
      void route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ installed: true, path: "/usr/bin/chromium" }),
      });
    });

    await use(page);
  },
});

export { expect };
