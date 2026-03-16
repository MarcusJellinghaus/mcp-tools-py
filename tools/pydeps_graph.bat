@echo off
REM Generate dependency graph using pydeps
REM Usage: tools\pydeps_graph.bat
REM
REM Creates:
REM   - docs/architecture/dependencies/pydeps_graph.svg (requires GraphViz)
REM   - docs/architecture/dependencies/pydeps_graph.dot (always created)
REM
REM Note: For SVG output, install GraphViz from https://graphviz.org/download/

echo Generating dependency graph with pydeps...

REM Ensure output directory exists
if not exist "docs\architecture\dependencies" mkdir "docs\architecture\dependencies"

REM Always generate DOT file (no GraphViz needed)
echo Creating DOT file...
pydeps src/mcp_tools_py --max-bacon 2 --cluster --rankdir TB --no-output --show-dot > docs/architecture/dependencies/pydeps_graph.dot 2>nul

REM Try to generate SVG (requires GraphViz)
echo Creating SVG file (requires GraphViz)...
pydeps src/mcp_tools_py --max-bacon 2 --cluster --rankdir TB --noshow -x "tests.*" -o docs/architecture/dependencies/pydeps_graph.svg 2>nul

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Created: docs/architecture/dependencies/pydeps_graph.svg
    echo Created: docs/architecture/dependencies/pydeps_graph.dot
) else (
    echo.
    echo Created: docs/architecture/dependencies/pydeps_graph.dot
    echo.
    echo SVG generation failed - GraphViz not installed.
    echo Install from: https://graphviz.org/download/
)
