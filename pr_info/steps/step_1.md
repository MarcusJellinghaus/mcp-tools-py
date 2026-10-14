# Step 1: Toolkit skeleton — entry point, describe(), prompt_fragments(), test action

See `pr_info/steps/summary.md` for full architectural context.

## WHERE

- Create `src/mcp_tools_py/toolkit.py`.
- Create `tests/test_toolkit.py`.
- Modify `pyproject.toml`: add a new top-level table (after `[project.scripts]`):

  ```toml
  [project.entry-points."mcp_coder.toolkits"]
  mcp-tools-py = "mcp_tools_py.toolkit:PythonToolkit"
  ```

## WHAT

In `src/mcp_tools_py/toolkit.py`:

```python
class PythonToolkit(Toolkit):
    def describe(self, config: Mapping[str, Any]) -> ToolkitInfo: ...
    def run(self, request: ActionRequest) -> ActionResult: ...
    def prompt_fragments(self) -> dict[str, str]: ...

def _build_context(project_dir: Path) -> ToolContext: ...
def _run_test(context: ToolContext, depth: str) -> ActionResult: ...
def _result_from_findings(
    error: str | None,
    findings: list[Finding],
    ok_summary: str,
    findings_summary: str,
) -> ActionResult: ...
```

`_result_from_findings` is the one generic helper this step needs (shared
by `_run_test` and later steps): `error` set → `status="error"`; `findings`
non-empty → `status="findings"` with `fix_text` built from them; else
`status="ok"`.

`describe()` returns the **final, complete** `ToolkitInfo` for all three
actions, even though `run()` only handles `test` so far (the `actions`/
`llm_permissions` entries for `format`/`check` are static data, not tied to
`run()`'s current completeness):

```python
ToolkitInfo(
    actions={
        "format": ["apply", "check"],
        "check": ["quick", "standard", "full"],
        "test": ["quick", "standard", "full"],
    },
    params_schema={"type": "object", "properties": {}, "additionalProperties": False},
    llm_permissions={
        "format": {d: ["mcp__mcp-tools-py__run_format_code"] for d in ("apply", "check")},
        "check": {
            "quick": ["mcp__mcp-tools-py__run_mypy_check"],
            "standard": ["mcp__mcp-tools-py__run_mypy_check", "mcp__mcp-tools-py__run_pylint_check"],
            "full": [
                "mcp__mcp-tools-py__run_mypy_check",
                "mcp__mcp-tools-py__run_pylint_check",
                "mcp__mcp-tools-py__run_vulture_check",
                "mcp__mcp-tools-py__run_lint_imports_check",
                "mcp__mcp-tools-py__run_tach_check",
                "mcp__mcp-tools-py__run_ruff_check",
                "mcp__mcp-tools-py__run_bandit_check",
            ],
        },
        "test": {d: ["mcp__mcp-tools-py__run_pytest_check"] for d in ("quick", "standard", "full")},
    },
)
```

`prompt_fragments()` returns `language_context`, `check_instructions`, and
`fix.check`. Copy the "Mypy Fix Prompt" body from
`mcp_coder/src/mcp_coder/prompts/prompts.md` (reference project `mcp_coder`)
into `fix.check`, dropping the `Mypy output:\n[mypy_output]` lines — the
actual output now travels via `ActionResult.fix_text`.

## HOW

- Import from `mcp_coder_utils.toolkit`: `Toolkit`, `ToolkitInfo`,
  `ActionRequest`, `ActionResult`, `Finding`.
- Import `ToolContext` from `mcp_tools_py.utils.tool_context` and
  `PythonEnvironment` from `mcp_tools_py.utils.python_environment`.
- Import `check_code_with_pytest` from `mcp_tools_py.code_checker_pytest.runners`.
- `_build_context` mirrors `ToolServer.__init__`'s defaults (no
  `python_executable`/`venv_path` override — `PythonEnvironment.resolve()`
  with no args, same as the old `mcp_coder/mcp_tools_py.py` shim):
  `ToolContext(project_dir=project_dir, environment=PythonEnvironment.resolve())`.
- `run()` dispatches only on `"test"` for now; any other action raises
  `NotImplementedError(request.action)` (replaced incrementally in steps 2–3).

## ALGORITHM (`_run_test`)

```
if pytest not available via context.is_tool_available: return error
markers = ["not integration"] if depth == "quick" else None
result = check_code_with_pytest(project_dir, python_executable=str(context.environment.interpreter),
                                 test_folder=context.test_folder, markers=markers,
                                 venv_bin=str(context.environment.bin_dir),
                                 timeout_seconds=context.resolve_timeout("pytest"))
if not result["success"]: "No Tests Found" in error -> skipped, else -> error
else: failed+error count > 0 -> findings (Finding per failing test, key=nodeid), else -> ok
```

`depth == "full"` additionally measures coverage: build the temp dir /
`coverage_args` / env the same way `pytest_tool.run_pytest_check(coverage=True)`
does (reuse `code_checker_pytest.coverage.coverage_args`,
`read_coverage_report`, `format_coverage_digest`, `read_fail_under`,
`selection_line`, and `utils.project_config.resolve_coverage_source`), then
set `action_result.raw` to the digest text after construction (`ActionResult`
is mutable; this never changes `status`, per the decision that a
`fail_under` miss is informational only).

## DATA

- `Finding(key=test.nodeid, message=<failure summary>, path=test.nodeid.split("::")[0])`
  for each `PytestReport.tests` entry with `outcome in ("failed", "error")`.
- `ActionResult(status, summary, findings=[...], fix_text=..., raw=...)`.

## Tests (write first, in `tests/test_toolkit.py`)

- `PythonToolkit` is discoverable: `importlib.metadata.entry_points(group="mcp_coder.toolkits")`
  contains `mcp-tools-py` resolving to `PythonToolkit`.
- `describe({})` returns the exact `actions`/`params_schema`/`llm_permissions`
  shown above.
- `prompt_fragments()` contains `language_context`, `check_instructions`,
  `fix.check`; `fix.check` contains no `[mypy_output]` substring.
- `run()` for `test@quick`/`standard`/`full` against a tiny fixture project
  (reuse the pattern from `tests/test_code_checker_pytest/*`): passing tests
  → `ok`; a failing test → `findings` with one `Finding` keyed by node id and
  non-empty `fix_text`; no tests collected → `skipped`; `full` depth sets
  `raw` to a non-empty coverage digest without changing `status`.
- `_result_from_findings` unit-tested directly for its three branches.

## Precondition check

After adding the entry point, reinstall the package editable
(`pip install -e .` in the tool environment, or the project's existing dev
install mechanism) so `importlib.metadata.entry_points()` picks it up. If the
entry point is still not discoverable after reinstalling, write one line to
`pr_info/.blocked.txt` and stop.

---

## LLM Prompt

Read `pr_info/steps/summary.md` for the overall architecture, then implement
**Step 1** exactly as described in `pr_info/steps/step_1.md`.

Follow TDD: write the tests listed under "Tests" in `tests/test_toolkit.py`
first, confirm they fail for the right reason, then implement
`src/mcp_tools_py/toolkit.py` and the `pyproject.toml` entry point to make
them pass. Run pylint, pytest, and mypy via the MCP tools and fix all issues
before finishing.

If the entry point is not discoverable after reinstalling as described under
"Precondition check", write one line to `pr_info/.blocked.txt` and stop.
