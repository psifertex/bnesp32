#!/bin/bash
# Run the ESP32 firmware loader test suite using Binary Ninja's Python environment.
#
# Uses the Binary Ninja "lastrun" file to locate the installation, so this
# script works regardless of install path or edition (Personal/Commercial/Enterprise).
#
# Usage:
#   ./run_tests.sh                  # run all tests
#   ./run_tests.sh -k "test_parse"  # run matching tests
#   ./run_tests.sh -v               # verbose output

set -euo pipefail

# Locate Binary Ninja via the lastrun file
if [[ "$(uname)" == "Darwin" ]]; then
    BN_USER_DIR="$HOME/Library/Application Support/Binary Ninja"
elif [[ "$(uname)" == "Linux" ]]; then
    BN_USER_DIR="$HOME/.binaryninja"
else
    echo "Error: Unsupported platform $(uname)" >&2
    exit 1
fi

LASTRUN_FILE="$BN_USER_DIR/lastrun"

if [[ ! -f "$LASTRUN_FILE" ]]; then
    echo "Error: Binary Ninja lastrun file not found at: $LASTRUN_FILE" >&2
    echo "Make sure Binary Ninja has been run at least once." >&2
    exit 1
fi

BN_INSTALL_DIR=$(cat "$LASTRUN_FILE")

# The lastrun file points to the MacOS/ or bin/ directory; we need the
# Resources/python directory for the Python API.
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS: .../Contents/MacOS -> .../Contents/Resources/python
    BN_PYTHON_DIR="${BN_INSTALL_DIR%/MacOS}/Resources/python"
else
    # Linux: .../binaryninja -> .../binaryninja/python
    BN_PYTHON_DIR="$BN_INSTALL_DIR/python"
fi

if [[ ! -d "$BN_PYTHON_DIR" ]]; then
    echo "Error: Binary Ninja Python directory not found at: $BN_PYTHON_DIR" >&2
    echo "lastrun points to: $BN_INSTALL_DIR" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export PYTHONPATH="$BN_PYTHON_DIR${PYTHONPATH:+:$PYTHONPATH}"

# Use PYTHON environment variable if set, otherwise find a python3 with pytest
if [[ -n "${PYTHON:-}" ]]; then
    PYTHON_BIN="$PYTHON"
elif /opt/homebrew/bin/python3 -c "import pytest" 2>/dev/null; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
elif python3 -c "import pytest" 2>/dev/null; then
    PYTHON_BIN="python3"
else
    echo "Error: No python3 with pytest found. Install pytest or set PYTHON=path/to/python3" >&2
    exit 1
fi

exec "$PYTHON_BIN" -m pytest "$SCRIPT_DIR/tests" "$@"
