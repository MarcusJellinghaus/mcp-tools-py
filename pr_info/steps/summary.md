# Issue #104: Add ruff MCP tools (check + fix) for linting

## Goal

Add `run_ruff_check()` and `run_ruff_fix()` MCP tools wrapping the ruff linter, following the established checker module pattern used by pylint/mypy/vulture.

## Architecture & Design Changes

### New Package: `src/mcp_tools_py/code_checker_ruff/`

Follows the standard 4-file checker module pattern:

```
code_checker_ruff/
    __init__.py      — re-exports public API
    models.py        — RuffMessage, RuffResult (flat NamedTuples)
    parsers.py       — parse ruff --output-format=json, normalize abs→rel paths
    reporting.py     — group by rule code, sort by prefix category then frequency
    runners.py       — run_ruff_check_impl(), run_ruff_fix_impl()
```

**Design decisions (KISS):**
- `RuffMessage` is flat — `line`, `column`, `end_line`, `end_column`, `fixable` (bool) instead of nested location/fix objects
- Path normalization uses `os.path.relpath()` inline — no custom helper module
- Reporting has one format function — no instruction lookup dict (ruff messages + `url` field are self-documenting)
- `run_ruff_fix` detects changed files by running check first (to identify fixable-violation files), then applying `--fix`

### Integration Points

1. **`server.py`** — binary-in-venv discovery for ruff (same as vulture/lint-imports pattern). Sets `self._ruff_binary` and `availability["ruff"]`.
2. **`checker_tools.py`** — two new tool registrations: `_register_ruff_check()` and `_register_ruff_fix()`. Called from `register()`.
3. **`pyproject.toml`** — `ruff>=0.9.0` added to dependencies.
4. **`tach.toml`** — new `mcp_tools_py.code_checker_ruff` module in `tool_implementation` layer; added to `checker_tools` depends_on.
5. **`.importlinter`** — `code_checker_ruff` added to layers contract (same tier as other checkers) and forbidden-imports list.

### Key Constraints

- Ruff is a standalone binary — no `python -m ruff`, binary discovery only
- Ruff JSON outputs absolute paths — parser normalizes to relative
- Exit codes: 0 = clean, 1 = violations found (not a failure), 2 = error
- `--fix` modifies files in-place — docstring must warn
- DOC rules require `--preview` — user's responsibility via `extra_args`
- CLAUDE.md: no changes (ruff is not a mandatory check)

## Files Created

| File | Purpose |
|------|---------|
| `src/mcp_tools_py/code_checker_ruff/__init__.py` | Package init, re-exports |
| `src/mcp_tools_py/code_checker_ruff/models.py` | RuffMessage, RuffResult |
| `src/mcp_tools_py/code_checker_ruff/parsers.py` | JSON parsing, path normalization |
| `src/mcp_tools_py/code_checker_ruff/reporting.py` | Grouping, sorting, LLM prompt formatting |
| `src/mcp_tools_py/code_checker_ruff/runners.py` | Subprocess execution, command construction |
| `tests/test_code_checker_ruff/__init__.py` | Test package init |
| `tests/test_code_checker_ruff/test_parsers.py` | Parser unit tests |
| `tests/test_code_checker_ruff/test_reporting.py` | Reporting unit tests |
| `tests/test_code_checker_ruff/test_runners.py` | Runner unit tests |

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/server.py` | Add ruff binary discovery in `_check_tool_availability()` |
| `src/mcp_tools_py/checker_tools.py` | Add `_register_ruff_check()`, `_register_ruff_fix()`, import ruff module |
| `pyproject.toml` | Add `ruff>=0.9.0` to dependencies |
| `tach.toml` | Add `code_checker_ruff` module + update `checker_tools` deps |
| `.importlinter` | Add `code_checker_ruff` to layers + forbidden-imports contracts |
| `tests/test_checker_tools.py` | Update tool count assertion (5→7), add ruff to mock fixtures |

## Implementation Steps

- **Step 1**: Models + parsers (with tests) — foundational data layer
- **Step 2**: Reporting (with tests) — formatting/grouping logic
- **Step 3**: Runners (with tests) — subprocess execution for check + fix
- **Step 4**: Server discovery + checker_tools registration — wiring into MCP
- **Step 5**: Architecture config + dependency — tach, import-linter, pyproject.toml
