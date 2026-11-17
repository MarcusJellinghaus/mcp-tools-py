#!/bin/bash
# Lint with ruff (rules from [tool.ruff.lint] in pyproject.toml)
#
# Usage from Git Bash: ./tools/ruff_check.sh

if ! command -v ruff &> /dev/null; then
    echo "ERROR: ruff not found. Install with: uv pip install ruff"
    exit 1
fi

echo "Linting with ruff..."
ruff check src tests tools "$@"
