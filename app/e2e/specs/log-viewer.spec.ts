import { test, expect } from "../fixtures";

test.describe("Log Viewer", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(
      () => !document.body.textContent?.includes("Starting sidecar..."),
      { timeout: 10_000 }
    );
    await expect(page.getByTestId("log-viewer")).toBeVisible();
  });

  test("log viewer is expanded by default", async ({ page }) => {
    await expect(page.getByTestId("log-content")).toBeVisible();
  });

  test("collapse button hides log content", async ({ page }) => {
    await page.getByTestId("collapse-button").click();
    await expect(page.getByTestId("log-content")).not.toBeVisible();
  });

  test("expand button shows log content again after collapse", async ({ page }) => {
    await page.getByTestId("collapse-button").click();
    await expect(page.getByTestId("log-content")).not.toBeVisible();
    await page.getByTestId("collapse-button").click();
    await expect(page.getByTestId("log-content")).toBeVisible();
  });

  test("all level filter buttons are present and active", async ({ page }) => {
    for (const level of ["INFO", "WARN", "ERROR", "DEBUG"] as const) {
      const btn = page.getByTestId(`level-toggle-${level}`);
      await expect(btn).toBeVisible();
      // Active state = opacity-100, not opacity-30
      await expect(btn).not.toHaveClass(/opacity-30/);
    }
  });

  test("toggling WARN level dims the button", async ({ page }) => {
    await page.getByTestId("level-toggle-WARN").click();
    await expect(page.getByTestId("level-toggle-WARN")).toHaveClass(/opacity-30/);
  });

  test("toggling WARN off then on restores active state", async ({ page }) => {
    await page.getByTestId("level-toggle-WARN").click();
    await expect(page.getByTestId("level-toggle-WARN")).toHaveClass(/opacity-30/);
    await page.getByTestId("level-toggle-WARN").click();
    await expect(page.getByTestId("level-toggle-WARN")).not.toHaveClass(/opacity-30/);
  });

  test("filter input is present and accepts text", async ({ page }) => {
    const input = page.getByTestId("log-filter");
    await expect(input).toBeVisible();
    await input.fill("ERROR");
    await expect(input).toHaveValue("ERROR");
  });

  test("copy button is present", async ({ page }) => {
    await expect(page.getByTestId("copy-logs-button")).toBeVisible();
  });
});
