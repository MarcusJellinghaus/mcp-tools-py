#!/bin/bash
# Reinstall mcp-tools-py in editable mode (developer convenience).
# Resolves an mcp-coder from OUTSIDE the repo venv, drives `mcp-coder install`
# against this repo, then activates the venv if sourced.
#
# Usage: source tools/reinstall_local.sh   (persists venv activation)
#    or: bash   tools/reinstall_local.sh   (does not persist activation)

(return 0 2>/dev/null) && _SOURCED=1 || _SOURCED=0

_SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
_SCRIPT_DIR="$( cd "$( dirname "$_SCRIPT_PATH" )" && pwd )"
REPO_DIR="$( cd "$_SCRIPT_DIR/.." && pwd )"
VENV_BIN="$REPO_DIR/.venv/bin"

# The install rewrites $VENV_BIN/mcp-coder, so the driver must come from
# elsewhere. `type -a -P` lists every PATH hit; `command -v` gives only the
# first and so cannot be filtered.
MC=""
if [ -n "$MCP_CODER_VENV_PATH" ] \
    && [ -x "$MCP_CODER_VENV_PATH/mcp-coder" ] \
    && [ "$MCP_CODER_VENV_PATH" != "$VENV_BIN" ]; then
    MC="$MCP_CODER_VENV_PATH/mcp-coder"
fi
if [ -z "$MC" ]; then
    while IFS= read -r p; do
        case "$p" in "$VENV_BIN/"*) continue ;; esac
        MC="$p"; break
    done <<< "$(type -a -P mcp-coder 2>/dev/null)"
fi
if [ -z "$MC" ]; then
    echo "[FAIL] No mcp-coder found outside $REPO_DIR/.venv."
    echo "       reinstall_local rewrites the repo venv, so it cannot be driven from it."
    echo "       Install the tool env first (pip install mcp-coder) or set"
    echo "       MCP_CODER_VENV_PATH to its Scripts/bin directory."
    [ "$_SOURCED" = "1" ] && return 1 || exit 1
fi

if ! "$MC" install "$REPO_DIR" \
    --source local \
    --local-path "$REPO_DIR" \
    --refresh; then
    echo "[FAIL] mcp-coder install failed"
    [ "$_SOURCED" = "1" ] && return 1 || exit 1
fi

# Activate venv (only persists if this script was sourced)
if [ -n "$VIRTUAL_ENV" ] && [ "$VIRTUAL_ENV" != "$REPO_DIR/.venv" ]; then
    echo "  Deactivating wrong virtual environment: $VIRTUAL_ENV"
    deactivate 2>/dev/null || true
fi

if [ "$VIRTUAL_ENV" != "$REPO_DIR/.venv" ]; then
    # shellcheck disable=SC1090,SC1091
    source "$VENV_BIN/activate"
fi

if [ "$_SOURCED" != "1" ]; then
    echo ""
    echo "Note: Activation does not persist because this script was not sourced."
    echo "      To activate now, run:  source $VENV_BIN/activate"
fi

unset _SOURCED _SCRIPT_PATH _SCRIPT_DIR REPO_DIR VENV_BIN MC p
