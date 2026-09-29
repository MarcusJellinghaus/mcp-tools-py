# Step 5 — `run_ruff_imports`

The import-sorting step that replaces isort. **`ruff format` does not sort imports** —
verified against ruff 0.16.8: `import os,sys` becomes `import os, sys`, not two lines. So
this step is load-bearing, not belt-and-braces.

Named `ruff_imports`, not `ruff_check_fix`, which would read like the unrelated
`run_ruff_fix` MCP tool.

## WHERE

**Modify** `src/mcp_tools_py/formatter/ruff_runner.py` (created in step 4)
**Modify** `src/mcp_tools_py/utils/project_config.py` — new public
`read_pyproject_tool_tables(project_root: Path)`; the existing private
`_read_mcp_tools_section` delegates to it
**Create** `tests/test_ruff_imports_runner.py`
**Modify** `tests/test_project_config.py` — cover the new reader

The shared `pyproject.toml` reader is introduced **here**, not in step 6, because
`per_file_ignores_notice` is its first consumer. Step 6's `resolve_steps` is the second.
Introducing it later would leave `formatter/` hand-rolling a second `tomllib` reader that
step 6 never consolidates.

## WHAT

```python
def run_ruff_imports(
    python_executable: str,          # deprecated: accepted and ignored
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
    *,
    environment: PythonEnvironment | None = None,
) -> FormatterResult:
```

Same signature as the other three, including the trailing keyword-only `environment`.

## Why this is two invocations in write mode

A `--fix` run's JSON lists only the **remaining unfixed** diagnostics, so `files_changed`
cannot be read from it. `run_ruff_fix_impl` in `code_checker_ruff/runners.py:112-136`
already solves this with a pre-check that collects the fixable messages before the fix is
applied. Mirror it.

| mode | invocations |
|---|---|
| write | `ruff check --select I --output-format json <dirs>`, then `ruff check --select I --fix <dirs>` |
| check | `ruff check --select I --output-format json <dirs>` |

Do not import from `code_checker_ruff` — tach forbids it (same layer). The shared piece is
`parse_ruff_json_output`, which step 1 moved to `utils/ruff_parsing.py`.

**Timeout:** both invocations get the full `timeout_seconds`, so write mode consumes
2 × `ruff-timeout` — exactly as `docs/pyproject-configuration.md:45` already records for
`run_ruff_fix`. Step 8 documents it.

## Why parse errors come from JSON, not the exit code

`ruff check --select I --fix` exits **1** both for a parse error and for ordinary unfixed
violations, and writes nothing to stderr. The exit code cannot discriminate. So syntax
errors are detected from `--output-format json` syntax-error diagnostics instead.

**Probe this before writing the detection.** In `.scratch/`, run
`ruff check --select I --output-format json` over a file with a syntax error and record
the diagnostic's shape — in particular whether `code` is `null` and how `message` reads.
Write the predicate against what you observe. Delete `.scratch/` when done.

Expected shape: a syntax-error diagnostic carries no rule code, so
`not message.code` is the discriminator, with the filename taken from `filename`.

## ALGORITHM

```
binary = formatter_binary("ruff", environment);  if None -> unavailable FormatterResult
json_cmd = [binary, "check", "--select", "I", "--output-format", "json"] + target_dirs
pre = execute_command(json_cmd, cwd=project_dir, timeout_seconds=...)
timed_out / execution_error -> early return, no version banner
messages, parse_error = parse_ruff_json_output(pre.stdout, project_dir)
unparsable = sorted({norm(m.filename) for m in messages if not m.code})
violations = sorted({norm(m.filename) for m in messages if m.code})   # any I diagnostic
changed    = sorted({norm(m.filename) for m in messages if m.fixable})
if check_only:  success = (not violations and not unparsable)
else:           run [binary, "check", "--select", "I", "--fix"] + target_dirs
                # runs even when `unparsable` is non-empty — ruff skips the
                # unparsable file and still sorts the rest
                success = (fix.return_code == 0 and not unparsable)
output = version_line("ruff", environment=environment) + per_file_ignores_notice(...) + combined
```

`files_changed` is populated from the **pre-check** run in both modes — that is what makes
it correct in write mode, where the fix run's JSON would report nothing.

### One path normalization, shared with `run_ruff_format`

`parse_ruff_json_output` already relativises `filename` with `os.path.relpath`, which on
Windows yields `src\bad.py`. **Both lists in both ruff runners hold project-relative paths
with forward slashes**, so the `norm()` above is the single guarded
`relative_path(path, project_dir)` helper in `formatter/common.py`, introduced in
`step_4.md` and used by `run_ruff_format` and `run_ruff_imports` alike:

```python
if os.path.isabs(path):
    path = os.path.relpath(path, project_dir)
return path.replace(os.sep, "/")
```

**Do not relativize twice.** The paths reaching `norm()` here are already relative — the
parser applied `os.path.relpath` to them — so an unconditional second
`os.path.relpath(path, project_dir)` re-anchors them against the *process's* cwd rather
than `project_dir` and turns `src/bad.py` into `../../../repo/src/bad.py`. The
`os.path.isabs` guard is what makes one helper correct for both the parser's output here
and ruff's raw stdout in `step_4.md`.

Every assertion names the full relative path — `"src/bad.py"`, never a bare `"bad.py"`.

### Check mode fails on *any* `I` diagnostic, not only fixable ones

`changed` is the `fixable` subset, because that is what the fix run will actually rewrite.
`success` in check mode is keyed on `violations` — every diagnostic carrying a rule code —
so an unsorted-import violation ruff declines to autofix still reports `success=False`
rather than a clean check. Keying `success` on `changed` would report success while the
imports are unsorted, which is the silent drift this issue exists to eliminate.

### A syntax error does not suppress the fix run

A file with a syntax error yields `success=False` and a populated `unparsable_files`, and
**the fix run still executes**, so the other files are sorted on disk. This is the issue's
acceptance criterion — *"a parse error in one file yields `success=False` and a populated
`unparsable_files`, **with the other files still formatted**"* — and it matches
`ruff_format`, where ruff formats the remaining files and exits 2.

Skipping the fix would leave the rest of the tree unsorted, which is the silent drift this
issue exists to eliminate.

A `parse_error` from `parse_ruff_json_output` is different: that is **malformed JSON from
ruff itself**, not a syntax error in the source, so nothing about the tree is known. That
is an infrastructure failure — return `success=False` with the parser's message in
`output` and do **not** run the fix. This is the only case where the fix run is skipped.

## The `per-file-ignores` notice

`ruff check --select I` overrides the configured `select` but still honours
`[tool.ruff.lint.per-file-ignores]` and ruff's exclude settings. A repo that ignores `I`
for `tests/**` gets those files sorted by isort today and **silently skipped** by
`ruff_imports` after migrating — the same class of silent per-commit drift this issue
exists to eliminate.

**Do not override the project's ruff configuration.** Report the divergence instead, so
it is visible. Same rationale as reporting the version.

```python
def per_file_ignores_notice(project_dir: str, target_dirs: list[str]) -> str:
    """One line naming target directories where an `I` per-file-ignore applies."""
```

### One shared `pyproject.toml` reader — introduced here

`formatter/` must **not** hand-roll a `tomllib` read. Add one public helper to
`utils/project_config.py` in this step and call it from `per_file_ignores_notice`:

```python
def read_pyproject_tool_tables(project_root: Path) -> dict[str, object]:
    """The `[tool]` table of `project_root/pyproject.toml`, empty when absent."""
```

`per_file_ignores_notice` keeps its `project_dir: str` parameter, matching the runner
signature, and converts once: `read_pyproject_tool_tables(Path(project_dir))`. **`Path` is
the helper's parameter type.** Rewrite the existing private
`_read_mcp_tools_section(project_dir: str)` to delegate to it rather than parsing the file
a second time; it stays private, and `get_check_timeout`'s use of it is unaffected.

Step 6's `resolve_steps` is the **second** consumer of the same helper and adds no new
reader. Two consumers, one reader, introduced at the first use.

**Keep the matching literal.** The notice is advisory, not a gate, and implementing glob
semantics here would be the largest complexity in the issue for the smallest payoff:

```
tables = read_pyproject_tool_tables(Path(project_dir))
read tables["ruff"]["lint"]["per-file-ignores"] (and legacy tables["ruff"]["per-file-ignores"])
for each glob key -> take the leading literal segment before the first * ? [
    if its codes contain "ALL" or any code starting with "I":
        if that prefix and a target dir overlap -> collect the target dir
return "" when nothing collected, else one line naming the directories and the key
```

A false negative on an exotic pattern means no notice — the status quo, not a regression.
A missing `pyproject.toml` yields an empty mapping and therefore `""`. A malformed one
raises the reader's existing `ValueError`, which `per_file_ignores_notice` swallows into
`""` — the notice must never fail the step. (`resolve_steps` in step 6 deliberately lets
that same `ValueError` propagate; the two consumers differ only in how they treat it.)

## DATA

- `output` — version banner, then the notice line when non-empty, then combined output
- `success` — check mode: no `I` diagnostic at all and nothing unparsable. write mode: the
  fix run exited 0 and nothing was unparsable
- `files_changed` — fixable filenames from the pre-check run, deduplicated and sorted
- `unparsable_files` — filenames of syntax-error diagnostics

All paths are project-relative with forward slashes.

## TESTS

**Write first.**

1. Check mode: exactly one invocation, argv is
   `[ruff, "check", "--select", "I", "--output-format", "json", "src"]`.
2. Write mode: **two** invocations, the second carrying `--fix` and no `--output-format`.
3. Bogus `python_executable` does not change argv.
4. `files_changed` comes from the pre-check messages with `fixable` true, deduplicated, as
   project-relative forward-slash paths (`["src/a.py"]`, not `src\a.py` and not `a.py`).
4b. **Check mode fails on an unfixable `I` diagnostic:** a pre-check message with a rule
   code and `fix` absent → `files_changed` empty, `success is False`.
5. **Real end-to-end, no mock:** a `tmp_path` project with a file that genuinely has
   unsorted imports, write mode. The file is sorted on disk and `files_changed` names it.
   This is the acceptance criterion, and a mock cannot prove the two-invocation design is
   what makes it work.
6. A syntax-error diagnostic → `unparsable_files` populated, `success is False`, and the
   fix run **is still executed**. Assert both invocations happened. Add a real,
   unmocked `tmp_path` sibling: one file with a syntax error and one with unsorted
   imports, write mode — the good file is sorted on disk,
   `unparsable_files == ["src/bad.py"]`, `success is False`. This is the acceptance
   criterion *"with the other files still formatted"*.
7. Malformed JSON from ruff → `success=False`, parser message in `output`, and **no fix
   run**. This is the only case that suppresses the fix: ruff's own output was
   unreadable, so nothing about the tree is known.
8. **`per-file-ignores` fixture:** a `tmp_path` project whose
   `[tool.ruff.lint.per-file-ignores]` ignores `I` for a target directory produces the
   notice in `output`. Acceptance criterion.
9. No `per-file-ignores` at all, and one that ignores a non-`I` code → no notice.
9b. A **malformed** `pyproject.toml` → no notice and no exception; the step still runs.
10. Missing ruff binary → `success=False`, no subprocess.

`tests/test_project_config.py`:

11. `read_pyproject_tool_tables`: a project with `[tool.black]` and `[tool.ruff.format]`
    returns both keys; a missing `pyproject.toml` returns `{}`; a file without a `[tool]`
    table returns `{}`; a malformed file raises `ValueError`.
12. The existing `_read_mcp_tools_section` / `get_check_timeout` tests still pass
    unchanged — that is the regression on the delegation.

## DONE WHEN

pylint / pytest / mypy / tach / lint-imports pass. `run_tach_check` matters here
specifically: it is what catches an accidental `from mcp_tools_py.code_checker_ruff import ...`.

`ruff_imports` is still unreachable from `run_format_code`. Step 6 wires it.

---

## LLM PROMPT

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_5.md`.
>
> Add `run_ruff_imports` to `src/mcp_tools_py/formatter/ruff_runner.py`, matching the
> other runners' signature.
>
> Write mode is **two** invocations: a `ruff check --select I --output-format json` pre-check
> that collects the fixable filenames, then `ruff check --select I --fix`. The fix run's
> JSON lists only remaining unfixed diagnostics, so `files_changed` must come from the
> pre-check. Check mode is the JSON run alone.
>
> Detect parse errors from the JSON syntax-error diagnostics, not the exit code — `--fix`
> exits 1 for both a parse error and an ordinary violation and writes nothing to stderr.
> **Probe the real diagnostic shape in `.scratch/` first** and write the predicate against
> what you observe; delete `.scratch/` when done.
>
> A syntax error sets `success=False` and populates `unparsable_files` but **does not**
> suppress the fix run — ruff skips that file and still sorts the rest, which the issue
> requires ("with the other files still formatted"). The only case that skips the fix is
> malformed JSON from ruff itself, where nothing about the tree is known.
>
> Check-mode `success` is keyed on **every** `I` diagnostic, not only the fixable ones, so
> an unsorted import ruff declines to autofix still reports `success=False`.
> `files_changed` stays the fixable subset.
>
> Normalize every path in `files_changed` and `unparsable_files` to **project-relative with
> forward slashes** through the `relative_path(path, project_dir)` helper step 4 added to
> `formatter/common.py`. `parse_ruff_json_output` has **already** relativized `filename`,
> so the helper must relativize only when `os.path.isabs(path)` and otherwise just swap
> separators — calling `os.path.relpath` a second time re-anchors the path against the
> process's cwd and yields `"../.."` garbage.
>
> Import `parse_ruff_json_output` from `mcp_tools_py.utils.ruff_parsing`. Do **not** import
> anything from `code_checker_ruff` — tach forbids it, they are the same layer.
>
> Add a `per_file_ignores_notice` that reports, in `output`, when an `I` entry in
> `[tool.ruff.lint.per-file-ignores]` covers a target directory. Do not override the
> project's ruff config. Keep the matching literal — leading literal path segment, no glob
> engine — and never let it fail the step.
>
> Read `pyproject.toml` through a **new public**
> `read_pyproject_tool_tables(project_root: Path)` in `src/mcp_tools_py/utils/project_config.py`,
> and rewrite the existing private `_read_mcp_tools_section` to delegate to it. Do not
> hand-roll a `tomllib` read inside `formatter/`. Step 6's `resolve_steps` reuses this same
> helper and adds no second reader.
>
> Write the tests first, including the real unsorted-imports end-to-end test and the
> `per-file-ignores` fixture.
>
> Do not wire the step into `_STEP_RUNNERS`, `_VALID_STEPS` or `resolve_steps` — step 6
> does that.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check` and
> `run_lint_imports_check`. All must pass. Then make exactly one commit.
