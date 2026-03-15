#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Building sidecar with PyInstaller..."
pyinstaller sidecar.spec --clean -y

MACHINE=$(uname -m)
OS=$(uname -s)

if [ "$OS" = "Darwin" ]; then
    if [ "$MACHINE" = "arm64" ]; then
        TARGET_TRIPLE="aarch64-apple-darwin"
    else
        TARGET_TRIPLE="x86_64-apple-darwin"
    fi
elif [ "$OS" = "Windows_NT" ] || [[ "$OS" == MINGW* ]]; then
    TARGET_TRIPLE="x86_64-pc-windows-msvc"
    EXE_SUFFIX=".exe"
else
    TARGET_TRIPLE="${MACHINE}-unknown-linux-gnu"
fi

BINARY_DIR="dist/sidecar-server"
BINARY_NAME="sidecar-server${EXE_SUFFIX:-}"
TARGET_NAME="sidecar-server-${TARGET_TRIPLE}${EXE_SUFFIX:-}"

if [ -f "$BINARY_DIR/$BINARY_NAME" ]; then
    cp "$BINARY_DIR/$BINARY_NAME" "$BINARY_DIR/$TARGET_NAME"
    echo "Binary renamed to: $TARGET_NAME"
else
    echo "ERROR: Binary not found at $BINARY_DIR/$BINARY_NAME"
    exit 1
fi

echo "Build complete: $BINARY_DIR/$TARGET_NAME"
