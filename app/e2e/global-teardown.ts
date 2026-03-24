import { readFile, unlink } from "fs/promises";

const PID_FILE = "/tmp/anylive-e2e-sidecar.pid";

export default async function globalTeardown(): Promise<void> {
  try {
    const pid = parseInt(await readFile(PID_FILE, "utf8"), 10);
    process.kill(pid, "SIGTERM");
    await unlink(PID_FILE);
    console.log(`[e2e] Sidecar (PID: ${pid}) terminated`);
  } catch {
    // Already dead or PID file missing — ignore
  }
}
