import { test, expect } from "../fixtures";

test.describe("Job Integration", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(
      () => !document.body.textContent?.includes("Starting sidecar..."),
      { timeout: 10_000 }
    );
  });

  test("starting a job (download mode) shows cancel button", async ({ page }) => {
    // TTSPanel posts to /api/tts/run; mock it to return a fake job_id
    await page.route("**/api/tts/run", (route) => {
      if (route.request().method() === "POST") {
        void route.fulfill({
          status: 202,
          contentType: "application/json",
          body: JSON.stringify({ job_id: "test-job-001", status: "accepted" }),
        });
      } else {
        void route.continue();
      }
    });

    await page.route("**/api/jobs/test-job-001", (route) => {
      void route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: "test-job-001",
          status: "running",
          progress: { current: 0, total: 1 },
          messages: [],
        }),
      });
    });

    // Use download mode (no CSV required)
    await page.getByTestId("option-download").click();
    await expect(page.getByTestId("run-button")).toBeEnabled({ timeout: 5_000 });
    await page.getByTestId("run-button").click();

    // Cancel button should now be visible
    await expect(page.getByTestId("cancel-button")).toBeVisible({ timeout: 5_000 });
  });

  test("polled log messages appear in log viewer", async ({ page }) => {
    const JOB_ID = "test-poll-job";

    // TTSPanel posts to /api/tts/run
    await page.route("**/api/tts/run", (route) => {
      if (route.request().method() === "POST") {
        void route.fulfill({
          status: 202,
          contentType: "application/json",
          body: JSON.stringify({ job_id: JOB_ID, status: "accepted" }),
        });
      } else {
        void route.continue();
      }
    });

    await page.route(`**/api/jobs/${JOB_ID}`, (route) => {
      void route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: JOB_ID,
          status: "running",
          progress: { current: 0, total: 1 },
          messages: [
            {
              type: "log",
              level: "INFO",
              message: "E2E test log message visible",
              timestamp: new Date().toISOString(),
              version: null,
            },
          ],
        }),
      });
    });

    // Use download mode (no CSV required)
    await page.getByTestId("option-download").click();
    await expect(page.getByTestId("run-button")).toBeEnabled({ timeout: 5_000 });
    await page.getByTestId("run-button").click();

    // Log message should appear in log viewer via polling
    await expect(page.getByTestId("log-content")).toContainText(
      "E2E test log message visible",
      { timeout: 10_000 }
    );
  });
});
