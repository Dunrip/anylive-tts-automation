#!/bin/bash
# Helper script to run AnyLive TTS Automation with correct environment

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if .venv exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Warning: .venv directory not found. Assuming environment is already set up or using global python."
fi

# Run the automation script with any arguments passed to this script
python auto_tts.py "$@"
