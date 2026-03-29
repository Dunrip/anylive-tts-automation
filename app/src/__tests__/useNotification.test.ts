import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { formatNotificationMessage, useNotification } from "../hooks/useNotification";
import {
  isPermissionGranted,
  requestPermission,
  sendNotification,
} from "@tauri-apps/plugin-notification";

vi.mock("@tauri-apps/plugin-notification", () => ({
  isPermissionGranted: vi.fn(),
  requestPermission: vi.fn(),
  sendNotification: vi.fn(),
}));

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

describe("useNotification — sendJobNotification", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(sendNotification).mockResolvedValue(undefined);
  });

  it("does nothing when enabled is false — no notification sent", async () => {
    const { result } = renderHook(() => useNotification({ enabled: false }));

    await act(async () => {
      await result.current.sendJobNotification("tts", {
        versionsTotal: 5,
        versionsSuccess: 5,
        versionsFailed: 0,
      });
    });

    expect(vi.mocked(isPermissionGranted)).not.toHaveBeenCalled();
    expect(vi.mocked(sendNotification)).not.toHaveBeenCalled();
  });

  it("sends notification immediately when permission is already granted", async () => {
    vi.mocked(isPermissionGranted).mockResolvedValue(true);

    const { result } = renderHook(() => useNotification({ enabled: true }));

    await act(async () => {
      await result.current.sendJobNotification("tts", {
        versionsTotal: 5,
        versionsSuccess: 5,
        versionsFailed: 0,
      });
    });

    expect(vi.mocked(requestPermission)).not.toHaveBeenCalled();
    expect(vi.mocked(sendNotification)).toHaveBeenCalledWith({
      title: expect.stringContaining("TTS"),
      body: expect.stringContaining("5/5"),
    });
  });

  it("requests permission and sends when initially not granted but then granted", async () => {
    vi.mocked(isPermissionGranted).mockResolvedValue(false);
    vi.mocked(requestPermission).mockResolvedValue("granted");

    const { result } = renderHook(() => useNotification({ enabled: true }));

    await act(async () => {
      await result.current.sendJobNotification("tts", {
        versionsTotal: 3,
        versionsSuccess: 3,
        versionsFailed: 0,
      });
    });

    expect(vi.mocked(requestPermission)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(sendNotification)).toHaveBeenCalledTimes(1);
  });

  it("does not send notification when permission is denied after request", async () => {
    vi.mocked(isPermissionGranted).mockResolvedValue(false);
    vi.mocked(requestPermission).mockResolvedValue("denied");

    const { result } = renderHook(() => useNotification({ enabled: true }));

    await act(async () => {
      await result.current.sendJobNotification("tts", {
        versionsTotal: 3,
        versionsSuccess: 3,
        versionsFailed: 0,
      });
    });

    expect(vi.mocked(requestPermission)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(sendNotification)).not.toHaveBeenCalled();
  });

  it("swallows errors when notification plugin throws (catch branch)", async () => {
    vi.mocked(isPermissionGranted).mockRejectedValue(new Error("Plugin unavailable"));

    const { result } = renderHook(() => useNotification({ enabled: true }));

    await expect(
      act(async () => {
        await result.current.sendJobNotification("tts", {
          versionsTotal: 5,
          versionsSuccess: 5,
          versionsFailed: 0,
        });
      })
    ).resolves.not.toThrow();

    expect(vi.mocked(sendNotification)).not.toHaveBeenCalled();
  });

  it("formats and sends correct notification body for partial failure", async () => {
    vi.mocked(isPermissionGranted).mockResolvedValue(true);

    const { result } = renderHook(() => useNotification({ enabled: true }));

    await act(async () => {
      await result.current.sendJobNotification("faq", {
        versionsTotal: 10,
        versionsSuccess: 7,
        versionsFailed: 3,
      });
    });

    expect(vi.mocked(sendNotification)).toHaveBeenCalledWith({
      title: expect.stringContaining("FAQ"),
      body: expect.stringContaining("3 failed"),
    });
  });

  it("formats and sends correct notification body for job error", async () => {
    vi.mocked(isPermissionGranted).mockResolvedValue(true);

    const { result } = renderHook(() => useNotification({ enabled: true }));

    await act(async () => {
      await result.current.sendJobNotification("script", {
        versionsTotal: 5,
        versionsSuccess: 0,
        versionsFailed: 5,
        error: "Session expired",
      });
    });

    expect(vi.mocked(sendNotification)).toHaveBeenCalledWith({
      title: expect.stringContaining("Failed"),
      body: "Session expired",
    });
  });
});
