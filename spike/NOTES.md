# Wave 0 Spike Notes

## Goal
- Prove Python FastAPI sidecar packaged by PyInstaller `--onedir` can integrate with Tauri v2 sidecar flow.

## Status
- Completed for sidecar binary + pytest validation.

## Gotchas and Learnings
- Uvicorn graceful shutdown works reliably by setting `server.should_exit = True` from an async task waiting on a `threading.Event` that is triggered by a stdin watcher.
- `SERVER_READY:<port>` must be printed before `server.serve()` and flushed immediately so parent processes can discover the dynamic port quickly.
- `/health` may fail immediately after `SERVER_READY` due to startup race; tests and validation scripts need short retry loops.
- PyInstaller `--onedir` output path is `dist/spike-server/spike-server`; Tauri sidecar naming requires `spike-server-<target-triple>` binary naming.
- Hidden imports required in this spike: `uvicorn`, `fastapi`, `anyio`, `h11`.
- Tauri v2 sidecar wiring used `tauri-plugin-shell` with `app.shell().sidecar("spike-server")`, stdout parsing for `SERVER_READY`, and `bundle.externalBin` set to `binaries/spike-server`.
- Capability file needs `shell:default` permission for spawning and interacting with sidecar commands.
