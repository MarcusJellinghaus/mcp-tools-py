# Step 5 — `run_ruff_imports`

The import-sorting step that replaces isort. **`ruff format` does not sort imports** —
verified against ruff 0.16.8: `import os,sys` becomes `import os, sys`, not two lines. So
this step is load-bearing, not belt-and-braces.

Named `ruff_imports`, not `ruff_check_fix`, which would read like the unrelated
`run_ruff_fix` MCP tool.

## WHERE

**Modify** `src/mcp_tools_py/formatter/ruff_runner.py` (created in step 4)
**Create** `tests/test_ruff_imports_runner.py`

## WHAT

```python
def run_ruff_imports(
    python_executable: str,          # deprecated: accepted and ignored
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> FormatterResult:
```

Same signature as the other three.

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
binary = formatter_binary("ruff");  if None -> unavailable FormatterResult
json_cmd = [binary, "check", "--select", "I", "--output-format", "json"] + target_dirs
pre = execute_command(json_cmd, cwd=project_dir, timeout_seconds=...)
timed_out / execution_error -> early return, no version banner
messages, parse_error = parse_ruff_json_output(pre.stdout, project_dir)
unparsable = sorted({m.filename for m in messages if not m.code})
changed    = sorted({m.filename for m in messages if m.fixable})
if check_only:  success = (not changed and not unparsable)
else:           run [binary, "check", "--select", "I", "--fix"] + target_dirs
                # runs even when `unparsable` is non-empty — ruff skips the
                # unparsable file and still sorts the rest
                success = (fix.return_code == 0 and not unparsable)
output = version_line("ruff") + per_file_ignores_notice(...) + combined
```

`files_changed` is populated from the **pre-check** run in both modes — that is what makes
it correct in write mode, where the fix run's JSON would report nothing.

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

**Keep the matching literal.** The notice is advisory, not a gate, and implementing glob
semantics here would be the largest complexity in the issue for the smallest payoff:

```
read [tool.ruff.lint.per-file-ignores] (and legacy [tool.ruff.per-file-ignores])
for each glob key -> take the leading literal segment before the first * ? [
    if its codes contain "ALL" or any code starting with "I":
        if that prefix and a target dir overlap -> collect the target dir
return "" when nothing collected, else one line naming the directories and the key
```

A false negative on an exotic pattern means no notice — the status quo, not a regression.
A malformed or missing `pyproject.toml` returns `""`; the notice must never fail the step.

## DATA

- `output` — version banner, then the notice line when non-empty, then combined output
- `success` — check mode: nothing to fix and nothing unparsable. write mode: the fix run
  exited 0 and nothing was unparsable
- `files_changed` — fixable filenames from the pre-check run, deduplicated and sorted
- `unparsable_files` — filenames of syntax-error diagnostics

## TESTS

**Write first.**

1. Check mode: exactly one invocation, argv is
   `[ruff, "check", "--select", "I", "--output-format", "json", "src"]`.
2. Write mode: **two** invocations, the second carrying `--fix` and no `--output-format`.
3. Bogus `python_executable` does not change argv.
4. `files_changed` comes from the pre-check messages with `fixable` true, deduplicated.
5. **Real end-to-end, no mock:** a `tmp_path` project with a file that genuinely has
   unsorted imports, write mode. The file is sorted on disk and `files_changed` names it.
   This is the acceptance criterion, and a mock cannot prove the two-invocation design is
   what makes it work.
6. A syntax-error diagnostic → `unparsable_files` populated, `success is False`, and the
   fix run **is still executed**. Assert both invocations happened. Add a real,
   unmocked `tmp_path` sibling: one file with a syntax error and one with unsorted
   imports, write mode — the good file is sorted on disk, `unparsable_files` names the
   bad one, `success is False`. This is the acceptance criterion *"with the other files
   still formatted"*.
7. Malformed JSON from ruff → `success=False`, parser message in `output`, and **no fix
   run**. This is the only case that suppresses the fix: ruff's own output was
   unreadable, so nothing about the tree is known.
8. **`per-file-ignores` fixture:** a `tmp_path` project whose
   `[tool.ruff.lint.per-file-ignores]` ignores `I` for a target directory produces the
   notice in `output`. Acceptance criterion.
9. No `per-file-ignores` at all, and one that ignores a non-`I` code → no notice.
10. Missing ruff binary → `success=False`, no subprocess.

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
> Import `parse_ruff_json_output` from `mcp_tools_py.utils.ruff_parsing`. Do **not** import
> anything from `code_checker_ruff` — tach forbids it, they are the same layer.
>
> Add a `per_file_ignores_notice` that reports, in `output`, when an `I` entry in
> `[tool.ruff.lint.per-file-ignores]` covers a target directory. Do not override the
> project's ruff config. Keep the matching literal — leading literal path segment, no glob
> engine — and never let it fail the step.
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
