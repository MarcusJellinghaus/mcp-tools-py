#!/usr/bin/env bash
# Print current time (human-readable + epoch). Usage: bash tools/get_time.sh
echo "$(date '+%Y-%m-%d %H:%M:%S') ($(date +%s))"
