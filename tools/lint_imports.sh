#!/usr/bin/env bash
# Run import-linter to check architectural boundaries
# Configuration is in .importlinter file (INI format)

set -e

if ! command -v lint-imports &> /dev/null; then
    echo "ERROR: lint-imports not found. Install with: pip install import-linter"
    exit 1
fi

lint-imports "$@"
