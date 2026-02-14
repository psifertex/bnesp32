#!/bin/bash
# Run ESP32-C3 plugin tests using Binary Ninja's Python
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

export PYTHONPATH="/Applications/Binary Ninja-enterprise-dev.app/Contents/Resources/python:${PROJECT_DIR}"

# Use homebrew python (has pytest); fall back to system python3
PYTHON="${PYTHON:-/opt/homebrew/bin/python3}"

cd "$PROJECT_DIR"
"$PYTHON" -m pytest tests/ -v "$@"
