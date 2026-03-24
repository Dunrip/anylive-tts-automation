import { test, expect } from "../fixtures";

test.describe("TTS Panel", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(
      () => !document.body.textContent?.includes("Starting sidecar..."),
      { timeout: 10_000 }
    );
    await expect(page.getByTestId("tts-panel")).toBeVisible();
  });

  test("run button is visible but disabled without CSV or download mode", async ({ page }) => {
    const runBtn = page.getByTestId("run-button");
    await expect(runBtn).toBeVisible();
    // Disabled because no CSV is selected and download mode is off
    await expect(runBtn).toBeDisabled();
  });

  test("run button is enabled when download mode is active", async ({ page }) => {
    // Enable download mode — no CSV required in download mode
    await page.getByTestId("option-download").click();
    const runBtn = page.getByTestId("run-button");
    await expect(runBtn).toBeEnabled({ timeout: 5_000 });
  });

  test("cancel button is not visible when no job is running", async ({ page }) => {
    await expect(page.getByTestId("cancel-button")).not.toBeVisible();
  });

  test("headless checkbox toggles", async ({ page }) => {
    // In default (non-download) mode, option-headless is visible
    const checkbox = page.getByTestId("option-headless");
    await expect(checkbox).toBeVisible();
    const before = await checkbox.isChecked();
    await checkbox.click();
    expect(await checkbox.isChecked()).toBe(!before);
  });

  test("advanced options toggle reveals extra options", async ({ page }) => {
    // Advanced options are hidden by default (not rendered)
    await expect(page.getByTestId("option-start-version")).not.toBeVisible();
    await expect(page.getByTestId("option-limit")).not.toBeVisible();

    await page.getByTestId("toggle-advanced").click();

    await expect(page.getByTestId("option-start-version")).toBeVisible();
    await expect(page.getByTestId("option-limit")).toBeVisible();
  });

  test("version filter input accepts text (download mode)", async ({ page }) => {
    // option-version-filter only exists in download mode
    await page.getByTestId("option-download").click();
    const input = page.getByTestId("option-version-filter");
    await expect(input).toBeVisible();
    await input.fill("1-5,10");
    await expect(input).toHaveValue("1-5,10");
  });

  test("base URL input is editable", async ({ page }) => {
    const input = page.getByTestId("input-tts-base-url");
    await input.fill("https://example.com/scripts/123");
    await expect(input).toHaveValue("https://example.com/scripts/123");
  });
});
