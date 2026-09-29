# Step 4 — `run_ruff_format`

The first of the two new steps. `ruff format` replaces black. This step adds the runner
only — it is not yet reachable through `resolve_steps` or `_STEP_RUNNERS`, which step 6
wires up.

## WHERE

**Create** `src/mcp_tools_py/formatter/ruff_runner.py` (holds both ruff runners;
`run_ruff_imports` arrives in step 5)
**Create** `tests/test_ruff_format_runner.py`
**Modify** `src/mcp_tools_py/formatter/common.py` — add the one-line path-normalization
helper (`relative_path(path, project_dir)`), which `run_ruff_imports` reuses in step 5
**Modify** `tests/test_formatter_common.py` — cover that helper

## WHAT

```python
def run_ruff_format(
    python_executable: str,          # deprecated: accepted and ignored
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> FormatterResult:
```

Signature matches `run_black` / `run_isort` exactly, so `_STEP_RUNNERS` can call all four
uniformly. `python_executable` is accepted and ignored here too, for signature uniformity
rather than for a caller — nothing has ever passed it.

Command: `[ruff_binary, "format"] + (["--check"] if check_only else []) + target_dirs`,
with `ruff_binary` from the same `formatter_binary("ruff")` helper step 2 introduced.

## FIRST: confirm the output format

**Before writing the parser, probe the installed ruff.** The formats below were verified
against ruff 0.16.8 and are version-sensitive.

```
save_file(".scratch/fmt/pyproject.toml", ...)      # minimal project
save_file(".scratch/fmt/src/bad.py", "def f(:\n")   # syntax error
save_file(".scratch/fmt/src/ugly.py", "x = { 'a':1 }\n")
```

Run `ruff format --check` against it and record the real stdout and stderr. Write the
parser against what you observed, not against this document. Delete `.scratch/` when
done — CI blocks a PR carrying one.

## ALGORITHM

```
binary = formatter_binary("ruff");  if None -> unavailable FormatterResult
cmd    = [binary, "format"] + (["--check"] if check_only else []) + target_dirs
result = execute_command(cmd, cwd=project_dir, timeout_seconds=...)
timed_out / execution_error -> early return, no version banner   (as the other runners)
stderr_bad = [path for "error: Failed to parse <path>:<line>:<col>" in result.stderr]
changed, marker_bad = parse_check_markers(stdout) if check_only else ([], [])
unparsable = dedup(stderr_bad + marker_bad)      # project-relative, forward slashes
return FormatterResult(output=version_line("ruff") + combined,
                       success=(return_code == 0), files_changed=changed,
                       unparsable_files=unparsable)
```

### Exit codes

| code | meaning |
|---|---|
| 0 | everything formatted |
| 1 | would reformat (`--check` only) |
| 2 | a parse error is present — **2 wins over 1** |

On a parse error ruff writes `error: Failed to parse <path>:<l>:<c>` to stderr **and
still formats the remaining files**. So a populated `unparsable_files` coexists with real
work having been done. `success = return_code == 0` therefore already yields
`success=False` on both 1 and 2; no extra `and not unparsable` clause is needed, unlike
isort which exits 0 and skips silently.

### `files_changed`

**Empty in write mode. Parsed in `--check` mode only.** Write mode prints only
`N files reformatted` and never names a file — there is nothing to parse, and inventing
an answer would be worse than an empty list.

`--check` mode prints, per file, a **marker line** followed by its own ` --> path:line:col`
header and an inline diff:

```
unformatted: File would be reformatted
 --> src/ugly.py:1:1
invalid-syntax: ...
 --> src/bad.py:1:7
```

**Key on the marker line, never on `-->`.** Keying on `-->` records an unparsable file as
"would be reformatted", which is exactly the silent-drift class this issue exists to
eliminate. `unformatted:` contributes to `files_changed`; `invalid-syntax:` contributes to
**`unparsable_files`** — its path is recorded, not discarded. Discarding it would leave
`--check` mode reporting `success=False` with an empty `unparsable_files`, so
`_unparsable_block` never tells the caller which files went unchecked: the same silent skip
in a different place.

```
parse_check_markers(stdout) -> (changed, unparsable):
    for each line:
        if line starts with "unformatted:"      -> arm as changed
        elif line starts with "invalid-syntax:" -> arm as unparsable
        elif armed and line.lstrip() starts with "-->":
                take the path before the first ":", append to the armed list, disarm
```

In `--check` mode `unparsable_files` is the union of the `invalid-syntax:` paths and any
`error: Failed to parse` paths on stderr — ruff may report a parse error through either
channel depending on mode, so both are read and the result deduplicated.

### Path normalization

`files_changed` and `unparsable_files` hold **project-relative paths with forward
slashes** — the single normalization shared with `run_ruff_imports` (see
`step_5.md`). Ruff prints native separators on Windows, so every parsed path goes through
one helper: `os.path.relpath(path, project_dir)` followed by `.replace(os.sep, "/")`.
Assert against `"src/bad.py"`, never a bare `"bad.py"`.

## DATA

`FormatterResult(output, success, files_changed, unparsable_files)` — unchanged shape.
Paths in both lists are project-relative with forward slashes.

- `output` — version banner line, then ruff's combined stdout and stderr, truncated
- `success` — `return_code == 0`
- `files_changed` — `[]` in write mode; `unformatted:` paths in `--check` mode
- `unparsable_files` — `invalid-syntax:` marker paths from stdout plus
  `error: Failed to parse` paths from stderr, deduplicated

## TESTS

**Write first**, all against a mocked `execute_command` using recorded real output,
except the last:

1. Write mode argv is `[ruff, "format", "src"]` — no `--check`.
2. `check_only=True` adds `--check`.
3. Bogus `python_executable` does not change argv (acceptance criterion).
4. Write mode `files_changed` is empty even when stdout says `2 files reformatted`.
5. `--check` mode parses `unformatted:` paths into `files_changed`, as `["src/ugly.py"]` —
   project-relative, forward slashes.
6. **`invalid-syntax:` is not counted as changed, and is not dropped either** — the
   marker-line regression. Feed a `--check` output containing both markers and assert
   `files_changed == ["src/ugly.py"]` **and** `unparsable_files == ["src/bad.py"]`.
7. Exit 2 with `error: Failed to parse src/bad.py:1:7` on stderr →
   `unparsable_files == ["src/bad.py"]` and `success is False`.
8. **`check_only=True` against an unparsable file** — exit 2, an `invalid-syntax:` marker
   in stdout, and a `--check` run that writes nothing to stderr. Assert `success is False`
   **and** `"src/bad.py" in unparsable_files`. This is the case a marker parser that
   discarded the path would report as failed-but-with-nothing-named.
9. A path reported with native separators normalizes to `"src/bad.py"`.
10. Missing ruff binary → `success=False`, no subprocess.
11. Timed out and execution-error paths → `success=False`, no version banner.
12. **One integration test, no mock:** a `tmp_path` project with one badly formatted file
    and one syntax-error file, run in write mode. The good file is reformatted on disk,
    `unparsable_files == ["src/bad.py"]`, `success is False`. This is the acceptance
    criterion "the other files still formatted". Mark it `integration` only if it needs
    ruff to be present — it is a declared dependency, so a plain test is fine.

## DONE WHEN

pylint / pytest / mypy / tach / lint-imports pass. `formatter/ruff_runner.py` imports from
`formatter/common.py` and `utils/` only.

`ruff_format` is still unreachable from `run_format_code` at the end of this step. That is
correct — step 6 wires it.

---

## LLM PROMPT

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_4.md`.
>
> Create `src/mcp_tools_py/formatter/ruff_runner.py` with `run_ruff_format`, matching the
> `run_black` signature exactly (including the accepted-and-ignored `python_executable`
> first parameter) so all four steps can be called uniformly later.
>
> **Before writing the check-mode parser, probe the installed ruff in `.scratch/` and
> write the parser against the output you actually observe.** Delete `.scratch/` when
> done.
>
> The parser must key on the marker line — `unformatted:` / `invalid-syntax:` — and never
> on `-->`. Keying on `-->` silently records unparsable files as "would be reformatted".
> `unformatted:` paths go to `files_changed`; `invalid-syntax:` paths go to
> `unparsable_files` — **record them, do not discard them**, or `--check` mode returns
> `success=False` with nothing named. `files_changed` stays empty in write mode, because
> `ruff format` never names the files it changed there. Also parse `unparsable_files` from
> `error: Failed to parse <path>:<l>:<c>` on stderr and deduplicate against the markers;
> exit 2 means a parse error is present and the remaining files were still formatted.
>
> Every path in `files_changed` and `unparsable_files` is **project-relative with forward
> slashes** — the same normalization `run_ruff_imports` uses in step 5.
>
> Write the tests first, including the `invalid-syntax:`-is-not-a-change regression, a
> `check_only=True` run against an unparsable file asserting `success is False` and
> `"src/bad.py" in unparsable_files`, and one real end-to-end test on a `tmp_path` project.
>
> Do not wire the step into `_STEP_RUNNERS`, `_VALID_STEPS` or `resolve_steps` — step 6
> does that.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check` and
> `run_lint_imports_check`. All must pass. Then make exactly one commit.
