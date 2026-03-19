import { test, expect } from "../fixtures";

test.describe("App Load", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(
      () => !document.body.textContent?.includes("Starting sidecar..."),
      { timeout: 10_000 }
    );
  });

  test("renders sidebar with all nav items", async ({ page }) => {
    await expect(page.getByTestId("nav-tts")).toBeVisible();
    await expect(page.getByTestId("nav-faq")).toBeVisible();
    await expect(page.getByTestId("nav-scripts")).toBeVisible();
    await expect(page.getByTestId("nav-history")).toBeVisible();
    await expect(page.getByTestId("nav-settings")).toBeVisible();
  });

  test("TTS panel is active by default", async ({ page }) => {
    await expect(page.getByTestId("tts-panel")).toBeVisible();
  });

  test("log viewer is visible", async ({ page }) => {
    await expect(page.getByTestId("log-viewer")).toBeVisible();
  });

  test("sidecar status dot is shown in sidebar", async ({ page }) => {
    await expect(page.getByTestId("status-dot")).toBeVisible();
  });
});
