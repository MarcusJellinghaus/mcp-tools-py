# Step 3 — Collapse `_check_tool_availability` into a loop; add `_tool_binaries`

Implements **Decisions 1 (eager half), 8, 15**. See [summary.md](./summary.md)
§1, §3, §5.

Fixes the second, unreported defect: the eager group is gated entirely on
`self.venv_path`, so with that flag unset all five tools record unavailable
regardless of what is installed. Depends on Step 2 (`_script_path`, `_TOOL_MODULES`).

## WHERE

| File | Change |
|---|---|
| `src/mcp_tools_py/server.py` | `__init__` (`:69-89`), `_check_tool_availability` (`:115-212`) |
| `src/mcp_tools_py/checker_tools/lint_imports_tool.py` | `:39`, `:48` |
| `src/mcp_tools_py/checker_tools/vulture_tool.py` | `:40`, `:64` |
| `src/mcp_tools_py/checker_tools/ruff_check_tool.py` | `:41`, `:66` |
| `src/mcp_tools_py/checker_tools/ruff_fix_tool.py` | `:42`, `:66` |
| `src/mcp_tools_py/checker_tools/bandit_tool.py` | `:42`, `:66` |
| `src/mcp_tools_py/checker_tools/tach_tool.py` | `:29`, `:41` |
| `tests/test_tool_availability.py` | `TestCheckToolAvailability`, plus `:542` |
| `tests/test_checker_tools.py` | `mock_server` fixture `:21`, `:34-37` |
| `tests/test_code_checker_bandit/test_integration.py` | `:16` |

## WHAT

```python
class ToolServer:
    def __init__(self, ...) -> None:
        ...
        self._tool_binaries: dict[str, str] = {}   # added in Step 2; must stay before _check_tool_availability()
        self._resolved_python = self._resolve_python_executable()
        self._tool_availability = self._check_tool_availability()

    def _check_tool_availability(self) -> dict[str, bool]:
        """Locate the console-script tools next to the resolved interpreter.

        Returns:
            Mapping of tool key to availability flag.
        """
```

Removes: `self._lint_imports_binary`, `self._vulture_binary`, `self._ruff_binary`,
`self._bandit_binary`, `self._tach_binary`.

## HOW

- `_tool_binaries` already exists — Step 2 introduced it for the fast path. It
  **must** stay initialised before `_check_tool_availability()` runs; this step adds
  the eager loop as its second writer.
- The loop skips every descriptor with a non-`None` module — the probe group stays
  lazy (#167 made it so deliberately; do not move it back to startup). The script
  group stays eager because file existence is instant.
- Presence in `_tool_binaries` means available, so the six
  `assert binary is not None` guards at the run sites are deleted:
  `binary = server._tool_binaries["ruff"]` is already `str`.
- The six `server._X_binary or "N/A"` message reads become
  `server._tool_binaries.get(key)` for now. Step 4 removes them entirely.
- A loop cannot assign five distinct attribute names without `setattr`, which mypy
  strict and vulture both flag — hence the dict.

## ALGORITHM

```
availability: dict[str, bool] = {}
for key, module in _TOOL_MODULES.items():
    if module is not None: continue          # probe group is lazy
    path = self._script_path(key)
    if path is not None: self._tool_binaries[key] = path
    else: logger.warning("%s not found in %s. Ensure --python-executable ...", key, script_dir)
    availability[key] = path is not None
return availability
```

The five copy-pasted warnings collapse into this one. Write the final wording here
(`--python-executable`, plus the directory searched); Step 4 handles the ten
tool-module messages.

## DATA

- `self._tool_binaries: dict[str, str]` — script group only, five keys at most.
  Absent key means unavailable. The probe group is always invoked as
  `python -m <module>` and never through its console script, so entries for it
  would be written and never read.
- `_check_tool_availability` returns `dict[str, bool]` with exactly the five script
  keys, as today.

## TESTS (write first)

Reuse the `tmp_path` script-directory helper from Step 2.

**Rewrite** — these three build a server with no `venv_path` and no
`os.path.exists` patch, then assert all five script tools are unavailable. Once
detection follows `_resolved_python` (= `sys.executable` = this project's own venv
under test) they would find the real binaries and flip to `True`. Pin the searched
directory instead:

1. `test_all_tools_missing` → empty `tmp_path` script dir, all five `False`,
   `_tool_binaries` empty.
2. `test_lint_imports_unavailable_when_no_venv` → rename to reflect "script not on
   disk"; assert `"lint-imports" not in server._tool_binaries`.
3. `test_vulture_unavailable_when_no_venv` → same shape.

**Re-point** — `_X_binary` → `_tool_binaries`. A found path becomes
`server._tool_binaries[key]`; **an `is None` assertion does not**. An absent key is
what now means unavailable, so `assert server._tool_binaries["lint-imports"] is None`
raises `KeyError`. The seven `is None` assertions
(`:175`, `:178`, `:203`, `:205`, `:207`, `:234`, `:236`) become
`assert "<key>" not in server._tool_binaries` — or `.get("<key>") is None` — matching
the Rewrite bullet above:

4. `test_all_tools_available`, `test_lint_imports_available_when_binary_exists`
   (`:162`, subscript), `test_lint_imports_unavailable_when_binary_missing`
   (`:203,205,207`, `not in`), `test_vulture_available_when_binary_exists`
   (`:222`, subscript), `test_vulture_unavailable_when_no_venv`
   (`:234,236`, `not in`).
5. `test_lint_imports_unavailable_returns_error` (`:542`) sets
   `server._lint_imports_binary`; change to `server._tool_binaries`. The message
   assertion at `:546` still holds in this step — Step 4 changes it.

**New:**

6. `test_scripts_found_without_venv_path` — script dir populated, `venv_path=None`
   → all five available and present in `_tool_binaries`. This is the unreported
   bug; it must fail before the change.

**Fixtures:** `tests/test_checker_tools.py::mock_server` sets all five attributes
(`:21`, `:34-37`) — replace with a single `server._tool_binaries = {...}`.
`tests/test_code_checker_bandit/test_integration.py:16` likewise.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_3.md`. Steps 1-2 are done.
>
> Implement Step 3 only: replace the five copy-pasted 12-line blocks in
> `ToolServer._check_tool_availability` with one loop over `_TOOL_MODULES` that
> skips entries with a module (those stay lazy) and, for the rest, calls
> `self._script_path(key)`. Store found paths in a new
> `self._tool_binaries: dict[str, str]`, initialised in `__init__` **before**
> `_check_tool_availability()` is called. Delete the five `_lint_imports_binary` /
> `_vulture_binary` / `_ruff_binary` / `_bandit_binary` / `_tach_binary`
> attributes and re-point the twelve reads across the six `checker_tools/*_tool.py`
> modules. Presence in the dict means available, so the six
> `assert binary is not None` guards go too.
>
> This fixes a second bug: detection was gated on `self.venv_path`, so with that
> flag unset all five tools reported unavailable regardless of what was installed.
> Add a test for that which fails before the change.
>
> Write the tests first. Three existing tests (`test_all_tools_missing`,
> `test_lint_imports_unavailable_when_no_venv`, `test_vulture_unavailable_when_no_venv`)
> assume detection keys on `venv_path` and will flip to `True` against the ambient
> interpreter — rewrite them to pin the searched directory with a `tmp_path` script
> dir, do not just re-point them. Also update the `mock_server` fixture in
> `tests/test_checker_tools.py` and `_make_mock_server` in
> `tests/test_code_checker_bandit/test_integration.py`.
>
> Keep `os.path.exists` and `os.name`, not `pathlib`. Do not change any
> tool-unavailable message wording beyond the collapsed startup warning — Step 4
> owns that. Do not touch `_is_tool_available`.
>
> Then run, in order: `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`,
> `run_mypy_check`. All must pass. Commit as one commit.
