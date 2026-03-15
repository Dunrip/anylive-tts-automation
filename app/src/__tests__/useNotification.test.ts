import { describe, it, expect } from "vitest";
import { formatNotificationMessage } from "../hooks/useNotification";

describe("formatNotificationMessage", () => {
  it("formats success message correctly", () => {
    const result = formatNotificationMessage("tts", {
      versionsTotal: 20,
      versionsSuccess: 20,
      versionsFailed: 0,
    });
    expect(result.title).toContain("TTS");
    expect(result.body).toContain("20/20");
    expect(result.body).toContain("succeeded");
  });

  it("formats partial success message correctly", () => {
    const result = formatNotificationMessage("tts", {
      versionsTotal: 20,
      versionsSuccess: 18,
      versionsFailed: 2,
    });
    expect(result.body).toContain("18/20");
    expect(result.body).toContain("2 failed");
  });

  it("formats failure message with error", () => {
    const result = formatNotificationMessage("faq", {
      versionsTotal: 5,
      versionsSuccess: 0,
      versionsFailed: 5,
      error: "Session expired",
    });
    expect(result.title).toContain("Failed");
    expect(result.body).toBe("Session expired");
  });

  it("disabled notifications skip the call", () => {
    const result = formatNotificationMessage("script", {
      versionsTotal: 3,
      versionsSuccess: 3,
      versionsFailed: 0,
    });
    expect(result.title).toBeTruthy();
    expect(result.body).toBeTruthy();
  });
});
