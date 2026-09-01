# Step 4 — Centralise the unavailable-tool messages

Implements **Decision 9**. See [summary.md](./summary.md) §6.

Sixteen strings across eleven files name `--venv-path`. After Steps 2-3 every one of
them points at a flag that no longer affects the outcome, so leaving them alone
would merely relocate the misdiagnosis. Depends on Step 3.

## WHERE

| File | Line(s) | Change |
|---|---|---|
| `src/mcp_tools_py/server.py` | new method; `_is_tool_available` probe warning | add `tool_unavailable_message` |
| `checker_tools/lint_imports_tool.py` | `:39-45` | helper, `package="import-linter"` |
| `checker_tools/vulture_tool.py` | `:40-45` | helper |
| `checker_tools/ruff_check_tool.py` | `:41-46` | helper |
| `checker_tools/ruff_fix_tool.py` | `:42-47` | helper |
| `checker_tools/bandit_tool.py` | `:42-47` | helper |
| `checker_tools/tach_tool.py` | `:29-34` | helper |
| `checker_tools/mypy_tool.py` | `:61-66` | helper |
| `checker_tools/pylint_tool.py` | `:39-44` | helper |
| `checker_tools/pytest_tool.py` | `:70-75` | helper |
| `formatter/formatter_tools.py` | `:66-72` | helper, `"Error: "` prefix kept |
| `tests/test_tool_availability.py` | `:546` | assertion now targets the directory |
| `tests/test_checker_tools.py` | `:186`, `:376`, `:420`, `:464` | `mock_server` must return a real message string |
| `tests/test_formatter_tools.py` | `:278` | same, for the `black` assertion |
| `tests/test_code_checker_bandit/test_integration.py` | `:45` | same, for `_make_mock_server` |

The five startup warnings were absorbed by Step 3's loop; this step covers the
remaining eleven strings.

## WHAT

```python
class ToolServer:
    def tool_unavailable_message(self, key: str, package: Optional[str] = None) -> str:
        """Build the standard 'tool not available' message for `key`.

        Args:
            key: Tool key as used in `_tool_availability`.
            package: Distribution name to tell the user to install, when it
                differs from `key` (import-linter provides `lint-imports`).

        Returns:
            A message naming --python-executable and the location searched.
        """
```

Public (no leading underscore) — the `checker_tools` modules are separate modules
calling into the server, and the existing public/private split there already has
them reaching `server._is_tool_available`. Either is defensible; pick one and be
consistent.

## HOW

- Two templates, selected on `_TOOL_MODULES.get(key) is None`:
  - **script group** — report the **directory searched**
    (`os.path.dirname(self._resolved_python)`), never `"N/A"`. When one of these
    tools is unavailable, `_tool_binaries` has no entry by construction, which is
    exactly why today's `server._ruff_binary or "N/A"` always prints
    "ruff is not available at N/A". The directory searched is what would have made
    the original bug self-diagnosing.
  - **probe group** — report `self._resolved_python`, as today.
- Both templates say `--python-executable`. No template mentions `--venv-path`.
- Both must keep the substrings existing tests assert on: `"<key> is not available"`
  and `"Restart the server"`.
- `formatter_tools.py` keeps its `Error: ` prefix at the call site.
- `ruff_check_tool` and `ruff_fix_tool` carry the same message today; both now call
  the helper, so the duplication disappears.
- `_is_tool_available`'s own failure warning (Step 2 left the `--venv-path` wording
  in place) is rewritten here too.
- The six `server._tool_binaries.get(key)` message reads introduced in Step 3
  disappear, leaving only the six run-site reads.

## ALGORITHM

```
searched = os.path.dirname(self._resolved_python)
name = package or key
if _TOOL_MODULES.get(key) is None:
    return (f"{key} is not available. No {key} console script was found in "
            f"{searched}. Ensure --python-executable points to an environment "
            f"where {name} is installed. Restart the server after installing.")
return (f"{key} is not available in the configured Python environment "
        f"({self._resolved_python}). Ensure --python-executable points to the "
        f"environment where {name} is installed. Restart the server after installing.")
```

## DATA

Returns `str`. No state change, no I/O beyond reading `self._resolved_python`.

## TESTS (write first)

1. `test_script_tool_message_reports_directory` — a script-group key produces a
   message containing the script directory and **not** `"N/A"` and **not**
   `"--venv-path"`.
2. `test_probe_tool_message_reports_interpreter` — a probe-group key produces a
   message containing `_resolved_python` and `--python-executable`.
3. `test_lint_imports_message_names_import_linter` — `package="import-linter"`
   appears; `lint-imports is not available` also appears.
4. **Re-point** `test_lint_imports_unavailable_returns_error`
   (`tests/test_tool_availability.py:542-547`): it sets a binary path and asserts
   that path appears in the message. Both halves change — the message now reports
   the directory searched, so assert on that instead.
5. A guard test that no `--venv-path` string survives in the tool modules is
   optional; a `search_files` sweep at review time is enough.

The short-circuit tests in `tests/test_tool_availability.py`
(`test_pytest_unavailable_returns_error` etc.) build a **real** `ToolServer`, and
both templates preserve the `"<tool> is not available"` / `"Restart the server"`
substrings, so they pass unchanged. If one fails, fix the template, not the test.

**Fix** — six assertions run against a `MagicMock` server instead, and those do
**not** pass unchanged. Once the message comes from
`server.tool_unavailable_message(...)`, a `MagicMock` returns a `MagicMock`, and
`assert "ruff is not available" in result` raises
`TypeError: argument of type 'MagicMock' is not iterable`:

6. `tests/test_checker_tools.py` — `mock_server` fixture (`:13-40`); assertions at
   `:186` (vulture), `:376` and `:420` (ruff check / ruff fix), `:464` (tach).
7. `tests/test_formatter_tools.py` — its `mock_server` fixture; assertion at `:278`
   (black).
8. `tests/test_code_checker_bandit/test_integration.py` — `_make_mock_server`
   (`:11-19`); assertion at `:45` (bandit).

Give each mock a real return value, e.g.
`server.tool_unavailable_message = lambda key, package=None: f"{key} is not available in <dir>. Restart the server after installing."`,
mirroring the existing `server._is_tool_available = lambda tool: ...` line already
in those fixtures. Building a real `ToolServer` in those tests is also defensible;
pick one and apply it consistently across the three files.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_4.md`. Steps 1-3 are done.
>
> Implement Step 4 only: add `ToolServer.tool_unavailable_message(key, package=None)`
> with two templates — one for console-script tools (report the **directory
> searched**, i.e. `os.path.dirname(self._resolved_python)`) and one for
> `python -m` tools (report `self._resolved_python`). Both must name
> `--python-executable` and neither may mention `--venv-path`. Then replace the
> unavailable-tool message at all ten `checker_tools` / `formatter_tools` call
> sites with a call to it, and rewrite the `--venv-path` wording still left in
> `_is_tool_available`'s failure warning.
>
> Today the six console-script messages read `server._X_binary or "N/A"`, and when
> the tool is unavailable that value is always `None` — so they literally print
> "ruff is not available at N/A". Reporting the directory searched is the point of
> this step.
>
> One exception the templates must not flatten: `lint_imports_tool.py` names
> **import-linter**, the pip package, not the tool. Pass `package="import-linter"`
> at that one call site. `formatter_tools.py` keeps its `"Error: "` prefix at the
> call site.
>
> Keep the substrings `"<key> is not available"` and `"Restart the server"` — several
> existing tests assert on them.
>
> Write the tests first, including re-pointing
> `test_lint_imports_unavailable_returns_error`, which currently asserts a binary
> path appears in the message.
>
> Three test files use a `MagicMock` server and assert `"<tool> is not available" in
> result`: `tests/test_checker_tools.py` (`:186`, `:376`, `:420`, `:464`),
> `tests/test_formatter_tools.py` (`:278`) and
> `tests/test_code_checker_bandit/test_integration.py` (`:45`). Routing the message
> through `server.tool_unavailable_message(...)` makes those mocks return a
> `MagicMock`, and the `in` check raises `TypeError`. Give the fixtures a
> `tool_unavailable_message` that returns a real string — alongside the
> `_is_tool_available` lambda they already set — or build a real `ToolServer`.
>
> Then run, in order: `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`,
> `run_mypy_check`. All must pass. Commit as one commit.
