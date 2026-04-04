import { beforeEach, describe, expect, it, vi } from "vitest";
import { isTauri, invoke } from "@tauri-apps/api/core";
import { openContainingFolder, openFolder } from "../lib/openFolder";

vi.mock("@tauri-apps/api/core", () => ({
  isTauri: vi.fn(),
  invoke: vi.fn(),
}));

vi.mock("@tauri-apps/plugin-opener", () => ({
  revealItemInDir: vi.fn(),
}));

describe("openFolder utilities", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("openContainingFolder", () => {
    it("no-ops when not in Tauri", async () => {
      vi.mocked(isTauri).mockReturnValue(false);
      await openContainingFolder("/path/to/file.txt");
      const { revealItemInDir } = await import("@tauri-apps/plugin-opener");
      expect(vi.mocked(revealItemInDir)).not.toHaveBeenCalled();
    });

    it("calls revealItemInDir with file path", async () => {
      vi.mocked(isTauri).mockReturnValue(true);
      const { revealItemInDir } = await import("@tauri-apps/plugin-opener");
      vi.mocked(revealItemInDir).mockResolvedValue(undefined);
      await openContainingFolder("/path/to/file.txt");
      expect(vi.mocked(revealItemInDir)).toHaveBeenCalledWith("/path/to/file.txt");
    });

    it("silently ignores errors", async () => {
      vi.mocked(isTauri).mockReturnValue(true);
      const { revealItemInDir } = await import("@tauri-apps/plugin-opener");
      vi.mocked(revealItemInDir).mockRejectedValue(new Error("fail"));
      await expect(openContainingFolder("/x")).resolves.toBeUndefined();
    });
  });

  describe("openFolder", () => {
    it("no-ops when not in Tauri", async () => {
      vi.mocked(isTauri).mockReturnValue(false);
      await openFolder("downloads");
      expect(invoke).not.toHaveBeenCalled();
    });

    it("invokes open_in_finder with the path", async () => {
      vi.mocked(isTauri).mockReturnValue(true);
      vi.mocked(invoke).mockResolvedValue(undefined);
      await openFolder("downloads");
      expect(invoke).toHaveBeenCalledWith("open_in_finder", { path: "downloads" });
    });

    it("silently ignores errors", async () => {
      vi.mocked(isTauri).mockReturnValue(true);
      vi.mocked(invoke).mockRejectedValue(new Error("fail"));
      await expect(openFolder("downloads")).resolves.toBeUndefined();
    });
  });
});
