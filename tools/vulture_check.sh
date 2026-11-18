#!/bin/bash
# Check for dead/unused code using vulture
#
# Usage from Git Bash: ./tools/vulture_check.sh

if ! command -v vulture &> /dev/null; then
    echo "ERROR: vulture not found. Install with: uv pip install vulture"
    exit 1
fi

echo "Checking for dead code..."
vulture src tests vulture_whitelist.py --min-confidence 60 "$@"
