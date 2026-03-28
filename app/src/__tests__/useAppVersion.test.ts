import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { getVersion } from "@tauri-apps/api/app";
import { isTauri } from "@tauri-apps/api/core";
import { useAppVersion } from "../hooks/useAppVersion";

vi.mock("@tauri-apps/api/app", () => ({
  getVersion: vi.fn(),
}));

vi.mock("@tauri-apps/api/core", () => ({
  isTauri: vi.fn(),
}));

describe("useAppVersion", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns 'dev' when isTauri() is false", () => {
    const isTauriMock = vi.mocked(isTauri);
    isTauriMock.mockReturnValue(false);

    const { result } = renderHook(() => useAppVersion());

    expect(result.current).toBe("dev");
  });

  it("returns resolved version when isTauri() is true and getVersion() succeeds", async () => {
    const isTauriMock = vi.mocked(isTauri);
    const getVersionMock = vi.mocked(getVersion);

    isTauriMock.mockReturnValue(true);
    getVersionMock.mockResolvedValue("1.2.3");

    const { result } = renderHook(() => useAppVersion());

    await waitFor(() => {
      expect(result.current).toBe("1.2.3");
    });
  });

  it("remains undefined when isTauri() is true but getVersion() rejects", async () => {
    const isTauriMock = vi.mocked(isTauri);
    const getVersionMock = vi.mocked(getVersion);

    isTauriMock.mockReturnValue(true);
    getVersionMock.mockRejectedValue(new Error("getVersion failed"));

    const { result } = renderHook(() => useAppVersion());

    // Wait a bit to ensure rejection is processed
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(result.current).toBeUndefined();
  });
});
