import { test, expect } from "../fixtures";

test.describe("Settings Panel", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(
      () => !document.body.textContent?.includes("Starting sidecar..."),
      { timeout: 10_000 }
    );
    await page.getByTestId("nav-settings").click();
    await expect(page.getByTestId("settings-panel")).toBeVisible();
  });

  test("settings fields are present", async ({ page }) => {
    await expect(page.getByTestId("input-version-template")).toBeVisible();
    await expect(page.getByTestId("input-voice-name")).toBeVisible();
    await expect(page.getByTestId("input-max-scripts")).toBeVisible();
  });

  test("save button is present and enabled", async ({ page }) => {
    await expect(page.getByTestId("save-button")).toBeVisible();
    await expect(page.getByTestId("save-button")).toBeEnabled();
  });

  test("reset button is present", async ({ page }) => {
    await expect(page.getByTestId("reset-button")).toBeVisible();
  });

  test("toggle checkboxes are present", async ({ page }) => {
    await expect(page.getByTestId("toggle-voice-selection")).toBeVisible();
    await expect(page.getByTestId("toggle-product-info")).toBeVisible();
  });

  test("editing version template and saving shows success", async ({ page }) => {
    const input = page.getByTestId("input-version-template");
    await input.fill("My_Template");
    await page.getByTestId("save-button").click();
    await expect(page.getByTestId("save-success")).toBeVisible({ timeout: 5_000 });
  });

  test("save success feedback auto-hides after 2 seconds", async ({ page }) => {
    await page.getByTestId("input-voice-name").fill("TestVoice");
    await page.getByTestId("save-button").click();
    await expect(page.getByTestId("save-success")).toBeVisible({ timeout: 5_000 });
    // After 2s the panel resets to idle and the success message disappears
    await expect(page.getByTestId("save-success")).not.toBeVisible({ timeout: 5_000 });
  });
});
