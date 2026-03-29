import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { toast } from "sonner";
import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import { useUpdateCheck } from "../hooks/useUpdateCheck";

vi.mock("sonner", () => ({
  toast: { info: vi.fn(), error: vi.fn(), success: vi.fn() },
}));

vi.mock("@tauri-apps/plugin-updater", () => ({
  check: vi.fn(),
}));

vi.mock("@tauri-apps/plugin-process", () => ({
  relaunch: vi.fn(),
}));

type InstallAction = { action: { onClick: () => Promise<void> } };

describe("useUpdateCheck", () => {
  const originalDEV = import.meta.env.DEV;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    import.meta.env.DEV = originalDEV;
  });

  it("hook returns installError null and clearInstallError initially", () => {
    const { result } = renderHook(() => useUpdateCheck());
    expect(result.current.installError).toBeNull();
    expect(typeof result.current.clearInstallError).toBe("function");
  });

  it("skips update check in DEV mode and installError stays null", async () => {
    const { result } = renderHook(() => useUpdateCheck());

    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(vi.mocked(check)).not.toHaveBeenCalled();
    expect(result.current.installError).toBeNull();
  });

  it("silently ignores outer check errors — installError remains null", async () => {
    import.meta.env.DEV = false;

    vi.mocked(check).mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useUpdateCheck());

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(result.current.installError).toBeNull();
  });

  it("shows no toast and no installError when no update is available", async () => {
    import.meta.env.DEV = false;

    vi.mocked(check).mockResolvedValue(null);

    const { result } = renderHook(() => useUpdateCheck());

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(vi.mocked(toast.info)).not.toHaveBeenCalled();
    expect(result.current.installError).toBeNull();
  });

  it("shows info toast when an update is available", async () => {
    import.meta.env.DEV = false;

    vi.mocked(check).mockResolvedValue({
      version: "1.2.3",
      downloadAndInstall: vi.fn().mockResolvedValue(undefined),
    } as unknown as Awaited<ReturnType<typeof check>>);

    renderHook(() => useUpdateCheck());

    await waitFor(() => {
      expect(vi.mocked(toast.info)).toHaveBeenCalledWith(
        expect.stringContaining("1.2.3"),
        expect.objectContaining({ action: expect.objectContaining({ label: "Install" }) })
      );
    });
  });

  it("sets installError state when update installation fails", async () => {
    import.meta.env.DEV = false;

    vi.mocked(check).mockResolvedValue({
      version: "1.2.3",
      downloadAndInstall: vi.fn().mockRejectedValue(new Error("Disk write failed")),
    } as unknown as Awaited<ReturnType<typeof check>>);

    const { result } = renderHook(() => useUpdateCheck());

    await waitFor(() => {
      expect(vi.mocked(toast.info)).toHaveBeenCalled();
    });

    const options = vi.mocked(toast.info).mock.calls[0][1] as unknown as InstallAction;

    await act(async () => {
      await options.action.onClick();
    });

    await waitFor(() => {
      expect(result.current.installError).toContain("Disk write failed");
    });
  });

  it("clearInstallError resets installError to null", async () => {
    import.meta.env.DEV = false;

    vi.mocked(check).mockResolvedValue({
      version: "1.2.3",
      downloadAndInstall: vi.fn().mockRejectedValue(new Error("fail")),
    } as unknown as Awaited<ReturnType<typeof check>>);

    const { result } = renderHook(() => useUpdateCheck());

    await waitFor(() => {
      expect(vi.mocked(toast.info)).toHaveBeenCalled();
    });

    const options = vi.mocked(toast.info).mock.calls[0][1] as unknown as InstallAction;
    await act(async () => { await options.action.onClick(); });

    await waitFor(() => {
      expect(result.current.installError).not.toBeNull();
    });

    act(() => { result.current.clearInstallError(); });

    expect(result.current.installError).toBeNull();
  });

  it("does not call relaunch when installation fails", async () => {
    import.meta.env.DEV = false;

    vi.mocked(check).mockResolvedValue({
      version: "1.2.3",
      downloadAndInstall: vi.fn().mockRejectedValue(new Error("install error")),
    } as unknown as Awaited<ReturnType<typeof check>>);

    renderHook(() => useUpdateCheck());

    await waitFor(() => {
      expect(vi.mocked(toast.info)).toHaveBeenCalled();
    });

    const options = vi.mocked(toast.info).mock.calls[0][1] as unknown as InstallAction;
    await act(async () => { await options.action.onClick(); });

    expect(vi.mocked(relaunch)).not.toHaveBeenCalled();
  });

  it("calls relaunch after successful installation", async () => {
    import.meta.env.DEV = false;

    vi.mocked(check).mockResolvedValue({
      version: "2.0.0",
      downloadAndInstall: vi.fn().mockResolvedValue(undefined),
    } as unknown as Awaited<ReturnType<typeof check>>);
    vi.mocked(relaunch).mockResolvedValue(undefined);

    renderHook(() => useUpdateCheck());

    await waitFor(() => {
      expect(vi.mocked(toast.info)).toHaveBeenCalled();
    });

    const options = vi.mocked(toast.info).mock.calls[0][1] as unknown as InstallAction;
    await act(async () => {
      await options.action.onClick();
    });

    expect(vi.mocked(relaunch)).toHaveBeenCalled();
  });

  it("sets fallback installError message when a non-Error is thrown during install", async () => {
    import.meta.env.DEV = false;

    vi.mocked(check).mockResolvedValue({
      version: "2.0.0",
      downloadAndInstall: vi.fn().mockRejectedValue("string-thrown-error"),
    } as unknown as Awaited<ReturnType<typeof check>>);

    const { result } = renderHook(() => useUpdateCheck());

    await waitFor(() => {
      expect(vi.mocked(toast.info)).toHaveBeenCalled();
    });

    const options = vi.mocked(toast.info).mock.calls[0][1] as unknown as InstallAction;
    await act(async () => {
      await options.action.onClick();
    });

    await waitFor(() => {
      expect(result.current.installError).toBe("Update installation failed");
    });
  });
});
