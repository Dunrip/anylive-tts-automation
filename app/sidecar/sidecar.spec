# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for AnyLive TTS Sidecar
# Mode: --onedir (keep binary and _internal together for Tauri resources)

import platform
from pathlib import Path

# Determine target triple for binary naming
machine = platform.machine().lower()
system = platform.system().lower()

if system == "darwin":
    if machine in ("arm64", "aarch64"):
        TARGET_TRIPLE = "aarch64-apple-darwin"
    else:
        TARGET_TRIPLE = "x86_64-apple-darwin"
elif system == "windows":
    TARGET_TRIPLE = "x86_64-pc-windows-msvc"
else:
    TARGET_TRIPLE = f"{machine}-unknown-linux-gnu"

# Paths
SIDECAR_DIR = Path(SPECPATH)
REPO_ROOT = SIDECAR_DIR.parent.parent

block_cipher = None

a = Analysis(
    [str(SIDECAR_DIR / "server.py")],
    pathex=[str(REPO_ROOT), str(SIDECAR_DIR)],
    binaries=[],
    datas=[
        # Include configs directory from repo root
        (str(REPO_ROOT / "configs"), "configs"),
    ],
    hiddenimports=[
        # FastAPI + uvicorn
        "fastapi",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "anyio",
        "anyio._backends._asyncio",
        "h11",
        "websockets",
        "starlette",
        "pydantic",
        "pydantic.v1",
        # Automation scripts
        "auto_tts",
        "auto_faq",
        "auto_script",
        "shared",
        # Playwright
        "playwright",
        "playwright.async_api",
        # Data
        "pandas",
        "numpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(SIDECAR_DIR / "rthook_playwright.py")],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sidecar-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="sidecar-server",
)
