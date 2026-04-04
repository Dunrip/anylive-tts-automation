import { isTauri, invoke } from "@tauri-apps/api/core";

/**
 * Opens the containing folder of a file in the system file explorer,
 * with the file selected/highlighted.
 * When not running in Tauri, this is a no-op.
 *
 * @param filePath - Absolute path to the file
 */
export async function openContainingFolder(filePath: string): Promise<void> {
  if (!isTauri()) {
    return;
  }

  try {
    const { revealItemInDir } = await import("@tauri-apps/plugin-opener");
    await revealItemInDir(filePath);
  } catch (err) {
    console.warn("[openFolder] revealItemInDir failed:", err);
  }
}

/**
 * Opens a directory in the system file explorer.
 * Handles both absolute and relative paths — the Rust side
 * resolves relative paths by walking up from CWD.
 * When not running in Tauri, this is a no-op.
 *
 * @param dirPath - Absolute or relative path to the directory
 */
export async function openFolder(dirPath: string): Promise<void> {
  if (!isTauri()) {
    return;
  }

  try {
    await invoke("open_in_finder", { path: dirPath });
  } catch (err) {
    console.warn("[openFolder] open_in_finder failed:", err);
  }
}
