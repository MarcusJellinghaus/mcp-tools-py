#!/usr/bin/env bash
set -e
echo "Running vulture dead code check..."
vulture src tests --min-confidence 60
echo "Vulture check complete!"