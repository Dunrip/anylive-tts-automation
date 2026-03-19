import { test, expect } from "../fixtures";

test.describe("History Panel", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(
      () => !document.body.textContent?.includes("Starting sidecar..."),
      { timeout: 10_000 }
    );
    await page.getByTestId("nav-history").click();
    await expect(page.getByTestId("history-panel")).toBeVisible();
  });

  test("history panel renders with refresh button", async ({ page }) => {
    await expect(page.getByTestId("refresh-button")).toBeVisible();
  });

  test("type filter tabs are present", async ({ page }) => {
    await expect(page.getByTestId("filter-all")).toBeVisible();
    await expect(page.getByTestId("filter-tts")).toBeVisible();
    await expect(page.getByTestId("filter-faq")).toBeVisible();
    await expect(page.getByTestId("filter-script")).toBeVisible();
  });

  test("shows empty state when no runs exist", async ({ page }) => {
    // Fresh sidecar has no runs — empty-history should appear
    await expect(page.getByTestId("empty-history")).toBeVisible({ timeout: 5_000 });
  });

  test("switching type filters does not crash", async ({ page }) => {
    for (const filter of ["filter-tts", "filter-faq", "filter-script", "filter-all"]) {
      await page.getByTestId(filter).click();
      // Panel must remain visible after each filter click
      await expect(page.getByTestId("history-panel")).toBeVisible();
    }
  });

  test("refresh button triggers reload", async ({ page }) => {
    // Just verify click doesn't crash the panel
    await page.getByTestId("refresh-button").click();
    await expect(page.getByTestId("history-panel")).toBeVisible();
  });
});
