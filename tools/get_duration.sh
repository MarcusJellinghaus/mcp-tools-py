#!/usr/bin/env bash
# Print human-readable duration between two epoch timestamps.
# Usage: bash tools/get_duration.sh <start> <end>
#   e.g.: bash tools/get_duration.sh 1774370000 1774370185
# Output: 3m 5s (185s)

if [ $# -lt 2 ]; then
  echo "Usage: $0 <start_epoch> <end_epoch>"
  exit 1
fi

diff=$(( $2 - $1 ))
if [ $diff -lt 0 ]; then
  diff=$(( -diff ))
fi

minutes=$(( diff / 60 ))
seconds=$(( diff % 60 ))

if [ $minutes -gt 0 ]; then
  echo "${minutes}m ${seconds}s (${diff}s)"
else
  echo "${seconds}s"
fi
