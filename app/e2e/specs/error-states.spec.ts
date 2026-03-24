import { test, expect } from "../fixtures";

test.describe("Error States", () => {
  test("app renders even when /api/configs returns 500", async ({ page }) => {
    await page.route("**/api/configs*", (route) => {
      void route.fulfill({ status: 500, body: "Internal Server Error" });
    });
    await page.goto("/");
    await page.waitForFunction(
      () => !document.body.textContent?.includes("Starting sidecar..."),
      { timeout: 10_000 }
    );
    // Sidebar must still be present despite config failure
    await expect(page.getByTestId("nav-tts")).toBeVisible();
  });

  test("TTS panel renders even when config fetch fails", async ({ page }) => {
    await page.route("**/api/configs/**", (route) => {
      void route.fulfill({ status: 500, body: "error" });
    });
    await page.goto("/");
    await page.waitForFunction(
      () => !document.body.textContent?.includes("Starting sidecar..."),
      { timeout: 10_000 }
    );
    await expect(page.getByTestId("tts-panel")).toBeVisible();
  });

  test("connection-lost banner is not shown on initial load", async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(
      () => !document.body.textContent?.includes("Starting sidecar..."),
      { timeout: 10_000 }
    );
    // Banner only shows during an active job with a dropped WS connection
    await expect(page.getByTestId("connection-lost-banner")).not.toBeVisible();
  });

  test("automation-error element is not shown when no job has run", async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(
      () => !document.body.textContent?.includes("Starting sidecar..."),
      { timeout: 10_000 }
    );
    await expect(page.getByTestId("automation-error")).not.toBeVisible();
  });
});
