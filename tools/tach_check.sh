#!/usr/bin/env bash
# Run tach architectural boundary check
# Configuration is in tach.toml

set -e

if ! command -v tach &> /dev/null; then
    echo "ERROR: tach not found. Install with: pip install tach"
    exit 1
fi

echo "Running tach architectural boundary check..."
tach check "$@"
