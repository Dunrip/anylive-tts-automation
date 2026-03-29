import { spawn } from "child_process";
import { writeFile, mkdir } from "fs/promises";
import * as os from "os";
import * as path from "path";

const SIDECAR_PORT = 8765;
const PID_FILE = "/tmp/anylive-e2e-sidecar.pid";
const TMPDIR_FILE = "/tmp/anylive-e2e-tmpdir.txt";
const REPO_ROOT = path.resolve(__dirname, "../..");

export default async function globalSetup(): Promise<void> {
  const tmpDir = path.join(os.tmpdir(), `anylive-e2e-${Date.now()}`);
  await mkdir(tmpDir, { recursive: true });
  await writeFile(TMPDIR_FILE, tmpDir);

  const serverScript = path.join(REPO_ROOT, "app", "sidecar", "server.py");
  const venvPython = path.join(REPO_ROOT, ".venv", "bin", "python3");
  const pythonCmd = require("fs").existsSync(venvPython) ? venvPython : "python3";

  const sidecar = spawn(pythonCmd, [
    serverScript,
    "--port", String(SIDECAR_PORT),
    "--app-data-dir", tmpDir,
  ], {
    cwd: REPO_ROOT,
    env: { ...process.env, PYTHONPATH: REPO_ROOT },
  });

  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("Sidecar did not start within 15s")), 15000);
    sidecar.stdout?.on("data", (data: Buffer) => {
      const line = data.toString();
      if (line.includes("SERVER_READY:")) {
        clearTimeout(timeout);
        resolve();
      }
    });
    sidecar.stderr?.on("data", (data: Buffer) => {
      process.stderr.write(`[sidecar] ${data.toString()}`);
    });
    sidecar.on("error", (err) => {
      clearTimeout(timeout);
      reject(new Error(`Sidecar spawn error: ${err.message}`));
    });
  });

  await writeFile(PID_FILE, String(sidecar.pid));
  console.log(`[e2e] Sidecar started on port ${SIDECAR_PORT} (PID: ${sidecar.pid})`);
  console.log(`[e2e] App data dir: ${tmpDir}`);
}
