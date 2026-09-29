# review-plan review log 1

## Round 1 — 2026-09-29
**Findings**:
I'll gather context systematically.`pr_info/steps/step_2.md:72` — high — `formatter_binary` placed in `formatter/runner.py` while `runner.py` already imports `run_black`/`run_isort` from those modules; having the runners import back from `runner.py` is a circular import that fails at import time. `common.py` (or a new small module) must be created in step 2, not offered as an equal alternative.

`pr_info/steps/step_5.md:137` — high — Test 6 requires the `--fix` run to be skipped when a syntax-error diagnostic is present, which contradicts the issue's acceptance criterion "a parse error in one file yields `success=False` … **with the other files still formatted**" for `ruff_imports`.

`pr_info/steps/step_5.md:73` — high — The ALGORITHM block runs the fix unconditionally in write mode, directly contradicting Test 6 at line 137 in the same file; the implementer cannot satisfy both.

`pr_info/steps/step_7.md:82` — high — Test 6 asserts the good file is still formatted for `ruff_imports` after a parse error, contradicting `step_5.md:137`. The two step files specify opposite behaviour for the same code path.

`pr_info/steps/step_7.md:84` — medium — "one with only the format problem" is unreachable through `run_format_code`: `ruff_imports` runs first and its JSON pre-check reports the same syntax error, so the runner breaks before `ruff_format`. That case can only be reached with an explicit `steps=["ruff_format"]`.

`pr_info/steps/step_6.md:158` — medium — `resolve_timeout(tool: ToolName)` takes a `Literal`, but the plan declares `_STEP_TOOLS: dict[str, str]` and `step_tool(step) -> str`; under the repo's `strict = true` mypy this fails the per-step gate. The mapping and accessor need `ToolName`, not `str`.

`pr_info/steps/step_2.md:76` — medium — `formatter_binary` resolves via `PythonEnvironment.resolve()` directly while the MCP layer answers availability from the injectable `ToolContext.tool_environment`; the fixture-patched availability check and the binary actually invoked can disagree, which is exactly what the rewritten `test_tool_unavailable_returns_error` would then be asserting against a different resolution path.

`pr_info/steps/step_6.md:99` — medium — Publicising `_read_mcp_tools_section` modifies `src/mcp_tools_py/utils/project_config.py`, which is absent from the "Files modified" list in `pr_info/steps/summary.md:166`.

`pr_info/steps/step_6.md:150` — low — `[step_tool(s) for s in resolved_steps]` passes `["ruff", "ruff"]` to `check_line_length_conflicts`; the plan does not say whether duplicates yield duplicated warnings.

`pr_info/steps/summary.md:240` — medium — Two open questions for Marcus (release-note home, new `docs/pyproject-configuration.md` subsection) are load-bearing for step 8 but left unresolved, so step 8 is not fully specified.

`pr_info/steps/step_8.md:60` — low — The plan updates `runner.py`'s module and `steps` docstrings but never states that `runner.py::run_format_code`'s own `python_executable` docstring must be marked deprecated, although the issue names that function explicitly alongside `run_black`/`run_isort`.
**Decisions**:
Verdict(decision='tasks', tasks=['In pr_info/steps/step_2.md:72, require creating a new shared module (e.g. formatter/common.py) for formatter_binary rather than offering formatter/runner.py as an equal alternative — placing it in runner.py creates a circular import with run_black/run_isort.', "Resolve the syntax-error contradiction across pr_info/steps/step_5.md:73, step_5.md:137 and step_7.md:82 by specifying one behaviour that matches the issue's acceptance criterion: a parse error yields success=False while the other files are still formatted for ruff_imports. Update the ALGORITHM block and both Test 6 specifications so they agree.", 'In pr_info/steps/step_2.md:76, specify that formatter_binary resolves through the injectable ToolContext.tool_environment (the same path the MCP availability check uses) rather than calling PythonEnvironment.resolve() directly, so the availability check and the invoked binary cannot diverge.', 'In pr_info/steps/step_6.md:158, type _STEP_TOOLS and step_tool() with ToolName instead of str so resolve_timeout(tool: ToolName) type-checks under strict mypy.', 'Add src/mcp_tools_py/utils/project_config.py to the "Files modified" list in pr_info/steps/summary.md:166, since step_6.md:99 publicises _read_mcp_tools_section there.', 'Resolve or remove the two open questions at pr_info/steps/summary.md:240 (release-note home and the new docs/pyproject-configuration.md subsection) so step 8 is fully specified; pick a concrete answer rather than leaving it for Marcus.'], escalate_reason=None)
**Changes**:
applied
