#!/usr/bin/env bash
# Generate dependency graph using pydeps
# Usage: tools/pydeps_graph.sh
#
# Creates:
#   - docs/architecture/dependencies/pydeps_graph.svg (requires GraphViz)
#   - docs/architecture/dependencies/pydeps_graph.dot (always created)
#
# Note: For SVG output, install GraphViz from https://graphviz.org/download/

set -e

if ! command -v pydeps &> /dev/null; then
    echo "ERROR: pydeps not found. Install with: pip install pydeps"
    exit 1
fi

echo "Generating dependency graph with pydeps..."

# Ensure output directory exists
mkdir -p docs/architecture/dependencies

# Always generate DOT file (no GraphViz needed)
echo "Creating DOT file..."
pydeps src/mcp_tools_py --max-bacon 2 --cluster --rankdir TB --no-output --show-dot > docs/architecture/dependencies/pydeps_graph.dot 2>/dev/null || true

# Try to generate SVG (requires GraphViz)
echo "Creating SVG file (requires GraphViz)..."
if pydeps src/mcp_tools_py --max-bacon 2 --cluster --rankdir TB --noshow -x "tests.*" -o docs/architecture/dependencies/pydeps_graph.svg 2>/dev/null; then
    echo ""
    echo "Created: docs/architecture/dependencies/pydeps_graph.svg"
    echo "Created: docs/architecture/dependencies/pydeps_graph.dot"
else
    echo ""
    echo "Created: docs/architecture/dependencies/pydeps_graph.dot"
    echo ""
    echo "SVG generation failed - GraphViz not installed."
    echo "Install from: https://graphviz.org/download/"
fi
