import { test, expect } from "../fixtures";

test("app loads and shows sidebar", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-testid="nav-tts"]')).toBeVisible();
});
