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

### 2. Sibling: the explicit key

Same repo, plus `[tool.mcp-tools-py] formatter = "ruff"`. Same assertions. Proves the key
path and the detection path land in the same place.

### 3. The black repo still works

A repo with `[tool.black]` only, unsorted and unformatted source, `steps=None`. Assert the
steps are `["isort", "black"]` and the files are actually sorted and formatted on disk.

### 4. Explicit `["isort", "black"]` on a **ruff** repo

The repos that have not migrated keep working, and an explicit list overrides detection
entirely. Acceptance criterion: *existing explicit `["isort", "black"]` behaviour
unchanged*.

### 5. `python_executable` is inert

Call `run_format_code("/nonexistent/python", ...)` on the black repo. The files are still
formatted. **Acceptance criterion:** passing any value — including a bogus path — does not
change which formatter binary runs. This is what protects mcp_coder, which still calls the
runner directly with `sys.executable`.

### 6. Parse error, ruff repo, write mode

Source tree with one good file and one syntax-error file.

```
assert results["ruff_format"].success is False
assert "bad.py" in results["ruff_format"].unparsable_files
assert good file was reformatted on disk        # the others still get formatted
```

And the same for `ruff_imports` via its JSON syntax-error diagnostics. Note the runner
stops after the first failing step in write mode, so assert these in two separate tests —
one with only the import problem, one with only the format problem — or assert on
`ruff_imports` first since it runs first.

### 7. `steps=[]` at both entry points

`ValueError` from `formatter.runner.run_format_code`, and an error **string** from the MCP
registration. Acceptance criterion, and worth re-proving end to end because it is the case
that used to silently mean "the defaults".

### 8. Both declared → error, neither declared → error

Real `tmp_path` repos, `steps=None`. Assert the message names the key and the file.

### 9. Version line present

Every step's `output` first line names the formatter and a version, on both the ruff and
the black repo. Acceptance criterion: *each step's `output` names the formatter version it
ran*. Assert the tool name and that the version is not `"unknown"`, not an exact version
string.

### 10. MCP layer agrees with the runner layer

Capture the registered `run_format_code` as `tests/test_formatter_tools.py` does, point a
`ToolContext` at the ruff repo, call it with no `steps`, and assert the output has
`## ruff_imports` and `## ruff_format` sections and no `## black`. One defaulting rule,
two entry points.

## DATA

No new structures.

## NOTE ON RUNTIME

These spawn real subprocesses. Keep each project to two or three tiny files. If the module
is slow enough to annoy, mark it `integration` — but prefer keeping it in the default run,
because the churn test is the one that must not be skipped.

## DONE WHEN

pylint / pytest / mypy / tach / lint-imports pass, and every acceptance criterion in the
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
> no `steps`. Compare bytes. Add a sibling that sets the explicit key.
>
> Also cover: a black repo still resolving to isort+black; explicit `["isort", "black"]` on
> a ruff repo; a bogus `python_executable` not changing which binary runs; parse errors
> leaving the other files formatted; `steps=[]` raising at the runner and returning an
> error string at the MCP layer; both-declared and neither-declared errors naming the key
> and the file; a version line on every step; and the MCP layer resolving to the same steps
> as the runner layer.
>
> This is a test-only commit. If a test fails, fix the source — but land the fix in this
> commit rather than amending an earlier step.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check` and
> `run_lint_imports_check`. All must pass. Then make exactly one commit.
