# Step 7 — End-to-end acceptance tests

Steps 1–6 tested each piece. This step proves the **whole** thing on real projects with
real subprocesses, and in particular proves the churn problem is solved.

A test-only commit. If any of these fail, the fix belongs in the step that owns the
behaviour — but it lands here, in this commit, rather than reopening an earlier one.

## WHERE

**Create** `tests/test_formatter_integration.py`

No mocks in this module. Every test builds a real `tmp_path` project, runs the real
formatter binaries from the tool env, and inspects the files on disk. black, isort and
ruff are all declared dependencies of mcp-tools-py, so they are present.

## WHAT

Entry point under test is `formatter.runner.run_format_code` — the importable layer, which
is what mcp_coder calls — plus one case through the MCP registration to prove the two
agree.

Helper:

```python
def _project(tmp_path: Path, pyproject: str, files: dict[str, str]) -> Path:
    """Write a project with a pyproject.toml and some source files."""
```

## TESTS

### 1. The churn test — the reason this issue exists

**Acceptance criterion.** A `tmp_path` repo whose `pyproject.toml` carries
`[tool.ruff.format]` and **no** `[tool.black]` and **no** explicit
`[tool.mcp-tools-py] formatter` key, so the test exercises **detection**, not the key.

```
write already-ruff-formatted, already-sorted source
snapshot file bytes
run_format_code(python_executable=sys.executable, project_root, ["src"], steps=None)
assert bytes unchanged          # no diff
assert results.keys() == ["ruff_imports", "ruff_format"]
assert all(r.success for r in results.values())
```

Byte comparison, not a string comparison — trailing newlines matter.

**The source uses stdlib-only imports** (e.g. `import os` / `import sys`). Whether a
module in a `tmp_path` project counts as first-party or third-party depends on ruff's
detection, not on the formatter; a stdlib-only fixture cannot produce a spurious sort diff
from that classification.

### 2. Sibling: the explicit key

Same repo, plus `[tool.mcp-tools-py] formatter = "ruff"`. Same assertions. Proves the key
path and the detection path land in the same place.

### 3. The black repo still works

A repo with `[tool.black]` only, unsorted and unformatted source, `steps=None`. Assert the
steps are `["isort", "black"]` and the files are actually sorted and formatted on disk.

### 4. Explicit `["isort", "black"]` on a **ruff** repo

The repos that have not migrated keep working, and an explicit list overrides detection
entirely. Acceptance criterion: *existing explicit `["isort", "black"]` behaviour
unchanged* — meaning the steps that run and their `success`, `files_changed` and
`unparsable_files`. `output` **text** is exempt: step 3 prepends a version banner to it
deliberately.

### 5. `python_executable` is inert

Call `run_format_code("/nonexistent/python", ...)` on the black repo. The files are still
formatted. **Acceptance criterion:** passing any value — including a bogus path — does not
change which formatter binary runs. This is what protects mcp_coder, which still calls the
runner directly with `sys.executable`.

### 6. Parse error, ruff repo, write mode

Source tree with one good file — badly formatted **and** with unsorted imports — and one
syntax-error file.

A syntax error is visible to **both** ruff steps, and `ruff_imports` runs first and fails,
so `run_format_code` breaks before `ruff_format`. That makes "only the format problem"
unreachable through the default step list. Two tests, therefore:

**6a — through `run_format_code`, default steps.** `ruff_imports` is the step that
reports:

```
assert list(results) == ["ruff_imports"]          # the run stops here
assert results["ruff_imports"].success is False
assert "src/bad.py" in results["ruff_imports"].unparsable_files
assert the good file's imports were sorted on disk   # the others still get processed
```

**6b — `ruff_format` directly, `steps=["ruff_format"]`.** The only way to reach
`ruff_format` with a syntax-error file present:

```
assert results["ruff_format"].success is False
assert "src/bad.py" in results["ruff_format"].unparsable_files
assert the good file was reformatted on disk
```

Both prove the same acceptance criterion — a parse error yields `success=False` and a
populated `unparsable_files` while the remaining files are still processed. Neither step
suppresses its work because one file is unparsable; see `step_5.md` for why.

**Paths are project-relative with forward slashes** in `files_changed` and
`unparsable_files`, per `step_5.md`. Assert the full relative path, never a bare
`"bad.py"` — a bare basename is not a member of either list.

**6c — `check_only=True` on the same tree.** `steps=["ruff_format"]`, `check_only=True`:
`success is False` **and** `"src/bad.py" in unparsable_files`. Check mode must name the
file it could not read, not merely fail.

### 7. `steps=[]` at both entry points

`ValueError` from `formatter.runner.run_format_code`, and an error **string** from the MCP
registration. Acceptance criterion, and worth re-proving end to end because it is the case
that used to silently mean "the defaults".

### 8. Both declared → error, neither declared → error

Real `tmp_path` repos, `steps=None`. Assert the message names the key and the file.

### 9. Version line present

Every step's `output` first line names the formatter and a version, on both the ruff and
the black repo. Acceptance criterion: *each step's `output` names the formatter version it
ran*. Assert the tool name and that the version is not `"unknown"` — proving the real
`<binary> --version` call succeeded within the step's budget — not an exact version string.

### 10. MCP layer agrees with the runner layer

Capture the registered `run_format_code` as `tests/test_formatter_tools.py` does. Build a
`ToolContext` directly with `project_dir` set to the tmp ruff repo and the **real default
tool environment** — `environment=PythonEnvironment.resolve()` for the required field, and
leave `tool_environment` unset so its `default_factory` supplies it.
Do **not** use the conftest `tool_context` fixture: its tool env is a dummy script
directory of empty stubs, so no real formatter would run. Call it with no `steps`, and
assert the output has
`## ruff_imports` and `## ruff_format` sections and no `## black`. One defaulting rule,
two entry points.

## DATA

No new structures.

## NOTE ON RUNTIME

These spawn real subprocesses. Keep each project to two or three tiny files. If the module
is slow enough to annoy, mark it `integration` — but prefer keeping it in the default run,
because the churn test is the one that must not be skipped.

## DONE WHEN

pylint / pytest / mypy / tach / lint-imports / ruff / vulture pass, and every acceptance criterion in the
issue has a test naming it.

---

## LLM PROMPT

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_7.md`.
>
> Create `tests/test_formatter_integration.py` with real end-to-end tests — no mocks, real
> `tmp_path` projects, real formatter binaries, assertions against files on disk.
>
> The central test is the churn test: a repo carrying `[tool.ruff.format]`, **no**
> `[tool.black]` and **no** explicit `[tool.mcp-tools-py] formatter` key, with
> already-formatted source, must produce **no diff** when `run_format_code` is called with
> no `steps`. Compare bytes. Use stdlib-only imports in that source, so first-party /
> third-party classification cannot produce a spurious diff. Add a sibling that sets the
> explicit key.
>
> Also cover: a black repo still resolving to isort+black; explicit `["isort", "black"]` on
> a ruff repo; a bogus `python_executable` not changing which binary runs; parse errors
> leaving the other files formatted — `ruff_imports` through the default step list, and
> `ruff_format` via an explicit `steps=["ruff_format"]`, because `ruff_imports` fails
> first on the same file and stops the run; `steps=[]` raising at the runner and returning an
> error string at the MCP layer; both-declared and neither-declared errors naming the key
> and the file; a version line on every step; and the MCP layer resolving to the same steps
> as the runner layer — for that one, build a `ToolContext` with the real default tool
> environment and `project_dir` at the tmp ruff repo, not the conftest `tool_context`
> fixture, whose tool env holds empty stub scripts.
>
> This is a test-only commit. If a test fails, fix the source — but land the fix in this
> commit rather than amending an earlier step.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check`,
> `run_lint_imports_check`, `run_ruff_check` and `run_vulture_check`. All must pass. Then
> make exactly one commit.
