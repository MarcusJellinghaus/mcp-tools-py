#!/usr/bin/env bash
# Reinstall mcp-tools-py package in development mode (editable install)
# Usage: source tools/reinstall_local.sh   (from project root; persists venv activation)
#    or: bash tools/reinstall_local.sh     (does not persist activation to caller)

# Detect if script is sourced (return works only in sourced/function context)
(return 0 2>/dev/null) && _SOURCED=1 || _SOURCED=0

echo "============================================="
echo "MCP-Tools-Py Package Reinstallation (Developer)"
echo "============================================="
echo ""
echo "NOTE: This installs in editable mode from local source."
echo ""

# Determine project root (parent of tools directory)
_SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
_SCRIPT_DIR="$( cd "$( dirname "$_SCRIPT_PATH" )" && pwd )"
PROJECT_DIR="$( cd "$_SCRIPT_DIR/.." && pwd )"
VENV_DIR="$PROJECT_DIR/.venv"
VENV_BIN="$VENV_DIR/bin"
PY="$VENV_BIN/python"

echo "[0/8] Checking Python environment..."

# Silently deactivate any active venv
if command -v deactivate >/dev/null 2>&1; then
    deactivate 2>/dev/null || true
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "[FAIL] uv not found. Install it: pip install uv"
    [ "$_SOURCED" = "1" ] && return 1 || exit 1
fi
echo "[OK] uv found"

if [ ! -f "$VENV_BIN/activate" ]; then
    echo "Local virtual environment not found at $VENV_DIR"
    ( cd "$PROJECT_DIR" && uv venv .venv )
    echo "Local virtual environment created at $VENV_DIR"
fi
echo "[OK] Target environment: $VENV_DIR"
echo ""

echo "[1/8] Uninstalling existing packages..."
uv pip uninstall mcp-coder mcp-tools-py mcp-config mcp-workspace --python "$PY" 2>/dev/null || true
echo "[OK] Packages uninstalled"

echo ""
echo "[2/8] Installing mcp-tools-py (this project) in editable mode..."
# Editable install pulls all deps (including mcp-workspace, mcp-config) from
# PyPI first.
if ! ( cd "$PROJECT_DIR" && uv pip install -e ".[dev]" --python "$PY" ); then
    echo "[FAIL] Editable installation failed!"
    [ "$_SOURCED" = "1" ] && return 1 || exit 1
fi
echo "[OK] Package and dev dependencies installed (editable)"

echo ""
echo "[3/8] Overriding dependencies with GitHub versions..."
# Validate read_github_deps.py succeeds before parsing its output
if ! "$PY" "$PROJECT_DIR/tools/read_github_deps.py" >/dev/null 2>&1; then
    echo "[FAIL] read_github_deps.py failed!"
    "$PY" "$PROJECT_DIR/tools/read_github_deps.py"
    [ "$_SOURCED" = "1" ] && return 1 || exit 1
fi
# Read GitHub dependency overrides from pyproject.toml
while IFS= read -r CMD; do
    [ -z "$CMD" ] && continue
    echo "  $CMD"
    if ! eval "$CMD --python \"$PY\""; then
        echo "[FAIL] GitHub dependency override failed!"
        [ "$_SOURCED" = "1" ] && return 1 || exit 1
    fi
done < <("$PY" "$PROJECT_DIR/tools/read_github_deps.py")
echo "[OK] GitHub dependencies overridden from pyproject.toml"

echo ""
echo "[4/8] Finalizing editable install of mcp-tools-py..."
# Re-run to ensure local source is the active install after GitHub overrides
if ! ( cd "$PROJECT_DIR" && uv pip install -e . --python "$PY" ); then
    echo "[FAIL] Final editable install failed!"
    [ "$_SOURCED" = "1" ] && return 1 || exit 1
fi
echo "[OK] mcp-tools-py installed (editable)"

echo ""
echo "[5/8] Installing LangChain and MLflow dependencies..."
if ! uv pip install langchain langchain-anthropic mlflow --python "$PY"; then
    echo "[FAIL] LangChain/MLflow installation failed!"
    [ "$_SOURCED" = "1" ] && return 1 || exit 1
fi
echo "[OK] langchain, langchain-anthropic, mlflow installed"

echo ""
echo "[6/8] Verifying CLI entry points in venv..."
for tool in mcp-tools-py mcp-workspace mcp-coder; do
    if [ ! -x "$VENV_BIN/$tool" ]; then
        echo "[FAIL] $tool not found in $VENV_BIN"
        echo "  The entry point was not installed into the virtual environment."
        [ "$_SOURCED" = "1" ] && return 1 || exit 1
    fi
    echo "[OK] $tool found in $VENV_BIN"
done

echo ""
echo "[7/8] Verifying CLI functionality..."
for tool in mcp-tools-py mcp-workspace mcp-coder; do
    if ! "$VENV_BIN/$tool" --help >/dev/null 2>&1; then
        echo "[FAIL] $tool CLI verification failed!"
        [ "$_SOURCED" = "1" ] && return 1 || exit 1
    fi
    echo "[OK] $tool CLI works"
done

echo ""
echo "============================================="
echo "[8/8] Reinstallation completed successfully!"
echo ""
echo "Entry points installed in: $VENV_BIN"
echo "  - mcp-tools-py"
echo "  - mcp-workspace"
echo "  - mcp-coder"
echo "============================================="
echo ""

# Activate the correct venv (only persists if this script was sourced)
if [ -n "$VIRTUAL_ENV" ] && [ "$VIRTUAL_ENV" != "$VENV_DIR" ]; then
    echo "  Deactivating wrong virtual environment: $VIRTUAL_ENV"
    deactivate 2>/dev/null || true
fi

if [ "$VIRTUAL_ENV" != "$VENV_DIR" ]; then
    echo "  Activating virtual environment: $VENV_DIR"
    # shellcheck disable=SC1090,SC1091
    source "$VENV_BIN/activate"
fi

if [ "$_SOURCED" != "1" ]; then
    echo ""
    echo "Note: Activation does not persist because this script was not sourced."
    echo "      To activate in your current shell, run:"
    echo "        source $VENV_BIN/activate"
    echo "      Or source this script next time:"
    echo "        source tools/reinstall_local.sh"
fi

unset _SOURCED _SCRIPT_PATH _SCRIPT_DIR
