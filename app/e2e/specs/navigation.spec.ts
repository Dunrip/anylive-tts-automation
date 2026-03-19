import { test, expect } from "../fixtures";

test.describe("Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(
      () => !document.body.textContent?.includes("Starting sidecar..."),
      { timeout: 10_000 }
    );
  });

  test("clicking FAQ nav shows FAQ panel", async ({ page }) => {
    await page.getByTestId("nav-faq").click();
    await expect(page.getByTestId("faq-panel")).toBeVisible();
    await expect(page.getByTestId("tts-panel")).not.toBeVisible();
  });

  test("clicking Scripts nav shows Scripts panel", async ({ page }) => {
    await page.getByTestId("nav-scripts").click();
    await expect(page.getByTestId("scripts-panel")).toBeVisible();
  });

  test("clicking History nav shows History panel", async ({ page }) => {
    await page.getByTestId("nav-history").click();
    await expect(page.getByTestId("history-panel")).toBeVisible();
  });

  test("clicking Settings nav shows Settings panel", async ({ page }) => {
    await page.getByTestId("nav-settings").click();
    await expect(page.getByTestId("settings-panel")).toBeVisible();
  });

  test("navigating back to TTS shows TTS panel", async ({ page }) => {
    await page.getByTestId("nav-faq").click();
    await page.getByTestId("nav-tts").click();
    await expect(page.getByTestId("tts-panel")).toBeVisible();
  });
});
