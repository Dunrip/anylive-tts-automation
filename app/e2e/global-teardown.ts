import { readFile, unlink, rm } from "fs/promises";

const PID_FILE = "/tmp/anylive-e2e-sidecar.pid";
const TMPDIR_FILE = "/tmp/anylive-e2e-tmpdir.txt";

export default async function globalTeardown(): Promise<void> {
  try {
    const pid = parseInt(await readFile(PID_FILE, "utf8"), 10);
    process.kill(pid, "SIGTERM");
    await unlink(PID_FILE);
    console.log(`[e2e] Sidecar (PID: ${pid}) terminated`);
  } catch {
    // Already dead or PID file missing — ignore
  }

  try {
    const tmpDir = (await readFile(TMPDIR_FILE, "utf8")).trim();
    await rm(tmpDir, { recursive: true, force: true });
    await unlink(TMPDIR_FILE);
    console.log(`[e2e] Temp dir removed: ${tmpDir}`);
  } catch {
    // Temp dir missing or already removed — ignore
  }
}
