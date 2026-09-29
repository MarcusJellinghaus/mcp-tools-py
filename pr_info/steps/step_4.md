# Step 4 — `run_ruff_format`

The first of the two new steps. `ruff format` replaces black. This step adds the runner
only — it is not yet reachable through `resolve_steps` or `_STEP_RUNNERS`, which step 6
wires up.

## WHERE

**Create** `src/mcp_tools_py/formatter/ruff_runner.py` (holds both ruff runners;
`run_ruff_imports` arrives in step 5)
**Create** `tests/test_ruff_format_runner.py`

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
unparsable = [path for "error: Failed to parse <path>:<line>:<col>" in result.stderr]
changed    = parse_check_markers(stdout) if check_only else []
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
eliminate. `unformatted:` contributes to `files_changed`; `invalid-syntax:` does not.

```
parse_check_markers(stdout):
    for each line:
        if line starts with "unformatted:"   -> arm, expect a path
        elif line starts with "invalid-syntax:" -> disarm, skip its path
        elif armed and line.lstrip() starts with "-->" -> take path before first ":", disarm
```

## DATA

`FormatterResult(output, success, files_changed, unparsable_files)` — unchanged shape.

- `output` — version banner line, then ruff's combined stdout and stderr, truncated
- `success` — `return_code == 0`
- `files_changed` — `[]` in write mode; `unformatted:` paths in `--check` mode
- `unparsable_files` — paths from `error: Failed to parse` on stderr

## TESTS

**Write first**, all against a mocked `execute_command` using recorded real output,
except the last:

1. Write mode argv is `[ruff, "format", "src"]` — no `--check`.
2. `check_only=True` adds `--check`.
3. Bogus `python_executable` does not change argv (acceptance criterion).
4. Write mode `files_changed` is empty even when stdout says `2 files reformatted`.
5. `--check` mode parses `unformatted:` paths into `files_changed`.
6. **`invalid-syntax:` is not counted as changed** — the marker-line regression. Feed a
   `--check` output containing both markers and assert only the `unformatted:` path
   appears in `files_changed`.
7. Exit 2 with `error: Failed to parse src/bad.py:1:7` on stderr →
   `unparsable_files == ["src/bad.py"]` and `success is False`.
8. Missing ruff binary → `success=False`, no subprocess.
9. Timed out and execution-error paths → `success=False`, no version banner.
10. **One integration test, no mock:** a `tmp_path` project with one badly formatted file
    and one syntax-error file, run in write mode. The good file is reformatted on disk,
    `unparsable_files` names the bad one, `success is False`. This is the acceptance
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
> `files_changed` stays empty in write mode, because `ruff format` never names the files
> it changed there. Parse `unparsable_files` from `error: Failed to parse <path>:<l>:<c>`
> on stderr; exit 2 means a parse error is present and the remaining files were still
> formatted.
>
> Write the tests first, including the `invalid-syntax:`-is-not-a-change regression and
> one real end-to-end test on a `tmp_path` project.
>
> Do not wire the step into `_STEP_RUNNERS`, `_VALID_STEPS` or `resolve_steps` — step 6
> does that.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check` and
> `run_lint_imports_check`. All must pass. Then make exactly one commit.
