# Step 5: verify() + docs/upgrade-notes.md

See `pr_info/steps/summary.md` for full architectural context.

## WHERE

- Modify `src/mcp_tools_py/toolkit.py`: add `PythonToolkit.verify`.
- Extend `tests/test_toolkit.py`. By this step the file carries every
  scenario from steps 1–5; if it is over the project's file-size check
  (`mcp-coder check file-size`) once this step's tests are added, split it
  into `tests/test_toolkit_*.py` files by action (`test_toolkit_format.py`,
  `test_toolkit_check.py`, `test_toolkit_test.py`, `test_toolkit_verify.py`)
  rather than leaving it oversized.
- Modify `docs/upgrade-notes.md`: add a new entry at the top (newest first).

## WHAT

```python
def verify(self, project_dir: Path) -> list[VerifyItem]: ...
```

## HOW

- Import `VerifyItem` from `mcp_coder_utils.toolkit` (already imported for
  other types; add `VerifyItem` to the existing import line).
- Reuse `_build_context(project_dir)` (step 1) to get a `ToolContext`.
- One `VerifyItem` per tool key in `mcp_tools_py.utils.tool_context.CONSOLE_SCRIPT_TOOLS`
  plus `"mypy"`, `"pylint"`, `"pytest"` (the three `python -m` tools), using
  `context.is_tool_available`/`unavailable_message` exactly as
  `ToolServer._warn_missing_console_scripts` and every `checker_tools/*`
  registrar already do — no new availability logic.
- One additional `VerifyItem` named `"formatter"` from
  `mcp_tools_py.formatter.runner.resolve_steps(project_dir)`: a caught
  `ValueError` becomes `status="error"` with the exception text as
  `message`; success becomes `status="ok"`.

## ALGORITHM

```
context = _build_context(project_dir)
items = []
for tool in sorted(CONSOLE_SCRIPT_TOOLS | {"mypy", "pylint", "pytest"}):
    ok = context.is_tool_available(tool)
    items.append(VerifyItem(name=tool, status="ok" if ok else "error",
                             message="" if ok else context.unavailable_message(tool)))
try:
    resolve_steps(project_dir)
    items.append(VerifyItem(name="formatter", status="ok"))
except ValueError as exc:
    items.append(VerifyItem(name="formatter", status="error", message=str(exc)))
return items
```

## DATA

- `list[VerifyItem]`, one entry per tool (`mypy`, `pylint`, `pytest`, and
  every name in `CONSOLE_SCRIPT_TOOLS`: `black`, `isort`, `ruff`, `bandit`,
  `vulture`, `tach`, `lint-imports`) plus one `"formatter"` entry — 11 items
  total on a healthy install.

## docs/upgrade-notes.md

Add a new section above the existing newest entry:

```markdown
## Toolkit interface for mcp-coder (#245)

`src/mcp_tools_py/toolkit.py` adds `PythonToolkit`, registered under the
`mcp_coder.toolkits` entry-point group as `mcp-tools-py`. It implements the
`Toolkit` contract from `mcp-coder-utils` (`mcp_coder_utils.toolkit`),
letting mcp-coder drive `format`/`check`/`test` actions through structured
`ActionResult`s instead of parsing MCP tool prose. `mcp-coder-utils` remains
an unpinned dependency in `pyproject.toml` for now (tracked as a separate
follow-up).

No existing MCP tool or CLI behaviour changes; this is a new, additive
entry point.
```

## Tests (write first)

- `verify()` on a healthy environment returns 11 `VerifyItem`s, all
  `status="ok"`.
- `verify()` with one console-script tool missing (patch
  `PythonEnvironment.binary` or point `tool_environment` at an empty
  directory) → that tool's `VerifyItem` is `status="error"` with a non-empty
  `message`; the others stay `"ok"`.
- `verify()` on a project with no formatter declared (neither
  `[tool.black]`/`[tool.ruff.format]` nor `[tool.mcp-tools-py] formatter`) →
  the `"formatter"` item is `status="error"`.

## Precondition check

If `mcp_coder_utils.toolkit` does not export `VerifyItem` with the
`name`/`status`/`message`/`hint` shape documented in mcp-coder-utils#41 (the
installed `mcp-coder-utils` version mismatches what steps 1–4 already
imported), write one line to `pr_info/.blocked.txt` and stop.

---

## LLM Prompt

Read `pr_info/steps/summary.md` for the overall architecture, then implement
**Step 5** exactly as described in `pr_info/steps/step_5.md`.

Follow TDD: write the tests listed under "Tests" in `tests/test_toolkit.py`
first, confirm they fail for the right reason, then implement
`PythonToolkit.verify` in `src/mcp_tools_py/toolkit.py` and update
`docs/upgrade-notes.md`. Run pylint, pytest, and mypy via the MCP tools and
fix all issues before finishing.

If `VerifyItem`'s shape does not match what's described under "Precondition
check", write one line to `pr_info/.blocked.txt` and stop.
