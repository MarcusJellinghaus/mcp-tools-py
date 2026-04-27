# Summary: Add `run_tach_check` MCP Tool (Issue #180)

## Goal

Add an MCP tool `run_tach_check` that runs `tach check --output json` in the project directory and returns a status line + raw JSON output. Mirrors existing patterns (`run_lint_imports_check`, `run_vulture_check`).

Also fix an existing gap: `code_checker_vulture` is missing from `.importlinter` contracts.

## Architectural / Design Changes

| Aspect | Decision | Rationale |
|---|---|---|
| Subpackage | New `code_checker_tach/` (`__init__.py` + `runners.py`) | Consistency with vulture/bandit layout |
| Tool signature | Zero-parameter `run_tach_check()` | Intentional simplification; tach check is always run the same way |
| Output | Status line + raw JSON; stderr appended if present; `"tach check passed (no output)."` fallback | Mirrors vulture's empty-output fallback |
| Availability | File-existence pattern in venv bin dir (`tach.exe` / `tach`) | Same as lint-imports/vulture/ruff/bandit |
| Layer placement | `tool_implementation` layer; depends only on `utils` + `log_utils` | Matches sibling checkers |
| Error handling | Let tach errors propagate (no pre-check for `tach.toml`) | Consistent with other tools |
| `.importlinter` gap fix | Add **both** `code_checker_tach` and `code_checker_vulture` to layers + forbidden-imports contracts | Vulture was never added; fix in this PR |

No public API changes outside the new MCP tool. No new dependencies (tach already in dev deps).

## Files Created / Modified

### Created
- `src/mcp_tools_py/code_checker_tach/__init__.py`
- `src/mcp_tools_py/code_checker_tach/runners.py`
- `tests/test_code_checker_tach/__init__.py`
- `tests/test_code_checker_tach/test_runners.py`

### Modified
- `src/mcp_tools_py/server.py` — add tach binary resolution in `_check_tool_availability()`; add `self._tach_binary` attribute
- `src/mcp_tools_py/checker_tools.py` — add `_register_tach()` method; call from `register()`; import `run_tach_check`
- `tach.toml` — add `[[modules]]` entry for `mcp_tools_py.code_checker_tach`; add to `mcp_tools_py.checker_tools.depends_on`
- `.importlinter` — add `code_checker_tach` AND `code_checker_vulture` to layers contract and forbidden-imports contract
- `tests/test_tool_availability.py` — extend exact-equality dicts with `"tach"` key in `test_all_tools_available` / `test_all_tools_missing`
- `tests/test_checker_tools.py` — add tach to fixture, update registration count, add tach handler tests

## Implementation Steps

| Step | Scope | Commit |
|---|---|---|
| 1 | Create `code_checker_tach` subpackage + unit tests | feat: add code_checker_tach runner |
| 2 | Server tach binary resolution + availability tests | feat: add tach binary resolution in server |
| 3 | Register `run_tach_check` MCP tool + update `tach.toml` | feat: register run_tach_check MCP tool |
| 4 | Update `.importlinter` (tach + vulture) | chore: add code_checker_tach and code_checker_vulture to importlinter contracts |

Each step leaves the project in a passing state (pylint, pytest, mypy, lint-imports, tach all green).

## Constraints

- No `extra_args` parameter on the new tool (issue requirement)
- No backward-compat shims; clean additions only
- All quality checks must pass after each step
