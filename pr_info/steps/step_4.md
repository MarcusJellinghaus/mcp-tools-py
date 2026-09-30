# Step 4 — `run_ruff_format`

The first of the two new steps. `ruff format` replaces black. This step adds the runner
only — it is not yet reachable through `resolve_steps` or `_STEP_RUNNERS`, which step 6
wires up.

## WHERE

**Create** `src/mcp_tools_py/formatter/ruff_runner.py` (holds both ruff runners;
`run_ruff_imports` arrives in step 5)
**Create** `tests/test_ruff_format_runner.py`
**Modify** `src/mcp_tools_py/formatter/common.py` — add the path-normalization helper
`relative_path(path, project_dir)`, which relativizes **only absolute** paths and which
`run_ruff_imports` reuses in step 5
**Modify** `tests/test_formatter_common.py` — cover that helper, including an
already-relative input passing through unchanged

## WHAT

```python
def run_ruff_format(
    python_executable: str,          # deprecated: accepted and ignored
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
    *,
    environment: PythonEnvironment | None = None,
) -> FormatterResult:
```

Signature matches `run_black` / `run_isort` exactly, so `_STEP_RUNNERS` can call all four
uniformly — including the trailing keyword-only `environment` step 2 introduced.
`python_executable` is accepted and ignored here too, for signature uniformity rather than
for a caller — nothing has ever passed it. The bare `python_executable` entry step 2 added
to `vulture_whitelist.py` already covers it; no new entry.

Command: `[ruff_binary, "format"] + (["--check"] if check_only else []) + target_dirs`,
with `ruff_binary` from the same `formatter_binary("ruff", environment)` helper step 2
introduced.

## FIRST: confirm the output format

**Before writing the parser, probe the installed ruff.** The formats below were verified
against ruff 0.16.8 and re-probed against 0.16.9, and are version-sensitive — older ruff
printed `Would reformat: <path>` instead of the marker lines. `pyproject.toml` therefore
already requires `ruff>=0.16.8` (user decision, applied with the plan).

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
binary = formatter_binary("ruff", environment);  if None -> unavailable FormatterResult
cmd    = [binary, "format"] + (["--check"] if check_only else []) + target_dirs
started = time.monotonic()
result = execute_command(cmd, cwd=project_dir, timeout_seconds=...)
timed_out / execution_error -> early return, no version banner   (as the other runners)
remaining = int(timeout_seconds - (time.monotonic() - started))
stderr_bad = _FAILED_TO_PARSE.findall(result.stderr)   # see "Extract the stderr path" below
changed, marker_bad = parse_check_markers(stdout) if check_only else ([], [])
unparsable = dedup(stderr_bad + marker_bad)      # project-relative, forward slashes
return FormatterResult(output=version_line("ruff", binary, remaining) + combined,
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
invalid-syntax: Expected a parameter or the end of the parameter list
 --> src\bad.py:1:7
unformatted: File would be reformatted
 --> src\ugly.py:1:6
```

(Observed on ruff 0.16.9, Windows: native separators, each header followed by a code
snippet or diff. In `--check` mode the syntax error goes to stdout only — exit 2, stderr
empty. In write mode it goes to stderr only, as
`error: Failed to parse src\bad.py:1:7: <message>`.)

Extract the stderr path with a module-level
`_FAILED_TO_PARSE = re.compile(r"error: Failed to parse (.+?):\d+:\d+")`. Anchoring on the
`:<line>:<col>` pair, rather than splitting at the first `:`, keeps an absolute Windows
path such as `C:\repo\src\bad.py` intact — its drive-letter colon is not followed by
digits and a second colon.

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
        elif armed and (m := _ARROW_PATH.match(line)):
                append m.group(1) to the armed list, disarm
```

`_ARROW_PATH = re.compile(r"\s*-->\s*(.+?):\d+:\d+")` is module-level and uses the same
`(.+?):\d+:\d+` anchor as `_FAILED_TO_PARSE`, so an absolute Windows path in a header
(` --> C:\repo\src\bad.py:1:7`) is not cut at its drive-letter colon.

In `--check` mode `unparsable_files` is the union of the `invalid-syntax:` paths and any
`error: Failed to parse` paths on stderr — ruff may report a parse error through either
channel depending on mode, so both are read and the result deduplicated.

### Path normalization

`files_changed` and `unparsable_files` hold **project-relative paths with forward
slashes** — the single normalization shared with `run_ruff_imports` (see
`step_5.md`). Ruff prints native separators on Windows, so every parsed path goes through
one helper in `formatter/common.py`:

```python
def relative_path(path: str, project_dir: str) -> str:
    """Project-relative path with forward slashes; already-relative paths pass through."""
    if os.path.isabs(path):
        path = os.path.relpath(path, project_dir)
    return path.replace(os.sep, "/")
```

**The `os.path.isabs` guard is load-bearing.** Ruff runs with `cwd=project_dir` and
prints paths relative to it, and `parse_ruff_json_output` has already applied
`os.path.relpath` to `filename` (`step_5.md`). Calling `os.path.relpath` on a path that
is *already* relative re-anchors it against the **process's** cwd, not `project_dir`, so
`"src/bad.py"` becomes something like `"../../../repo/src/bad.py"` whenever the test
process's cwd differs from the tmp project — which it always does. Relativize only when
the path is absolute; otherwise just normalize the separators.

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
except the last. As in steps 2 and 3's runner tests, two autouse fixtures:
`_fixed_formatter_binary` patches `ruff_runner.formatter_binary` to a fixed path, and
`_fixed_version_line` patches `ruff_runner.version_line` so the mocked tests spawn no
`--version` subprocess. Keep those exact names: the `vulture_whitelist.py` entries from
steps 2 and 3 cover them, so no new entry is needed. Test 10 overrides
`_fixed_formatter_binary` to return `None`; the unmocked test 12 restores the real
function with `monkeypatch.setattr(ruff_runner, "formatter_binary",
common.formatter_binary)`.

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
7b. `_FAILED_TO_PARSE` keeps a drive-letter path whole:
   `_FAILED_TO_PARSE.findall(r"error: Failed to parse C:\repo\src\bad.py:1:7: msg")`
   returns `[r"C:\repo\src\bad.py"]`. Test the pattern directly, not the runner's
   normalized result — `relative_path` on a Windows path is platform-dependent and CI runs
   on Linux.
7c. The check-mode marker parser keeps a drive-letter path whole: feed
   `"unformatted: File would be reformatted\n --> C:\\repo\\src\\ugly.py:1:6\n"` to
   `parse_check_markers` and assert `changed == [r"C:\repo\src\ugly.py"]`. Same reason as
   7b: test the parser's raw output, not the normalized runner result.
8. **`check_only=True` against an unparsable file** — exit 2, an `invalid-syntax:` marker
   in stdout, and a `--check` run that writes nothing to stderr. Assert `success is False`
   **and** `"src/bad.py" in unparsable_files`. This is the case a marker parser that
   discarded the path would report as failed-but-with-nothing-named.
9. `relative_path`: a native-separator relative path, built with
   `os.path.join("src", "bad.py")` (never a hard-coded `"src\\bad.py"` — CI runs on Linux,
   where `os.sep` is `/` and a backslash is a legal filename character, not a separator),
   normalizes to `"src/bad.py"` **unchanged in depth** — run the test from a cwd that is
   not `project_dir` so a missing `os.path.isabs` guard shows up as a `"../"` prefix. An
   absolute path under `project_dir`, built with `os.path.join(project_dir, "src",
   "bad.py")`, normalizes to `"src/bad.py"` too.
10. Missing ruff binary → `success=False`, no subprocess.
11. Timed out and execution-error paths → `success=False`, no version banner, and
    `version_line` not called.
12. **One integration test, no mock:** a `tmp_path` project with one badly formatted file
    and one syntax-error file, run in write mode. The good file is reformatted on disk,
    `unparsable_files == ["src/bad.py"]`, `success is False`. This is the acceptance
    criterion "the other files still formatted". Mark it `integration` only if it needs
    ruff to be present — it is a declared dependency, so a plain test is fine.

## DONE WHEN

pylint / pytest / mypy / tach / lint-imports / ruff / vulture pass. `formatter/ruff_runner.py` imports from
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
> `success=False` with nothing named. Take the path from the ` --> ` header with a
> module-level `_ARROW_PATH = re.compile(r"\s*-->\s*(.+?):\d+:\d+")`, the same anchor as
> `_FAILED_TO_PARSE`, never by splitting at the first `:`. `files_changed` stays empty in write mode, because
> `ruff format` never names the files it changed there. Also parse `unparsable_files` from
> `error: Failed to parse <path>:<l>:<c>` on stderr with a module-level
> `_FAILED_TO_PARSE = re.compile(r"error: Failed to parse (.+?):\d+:\d+")` — so a
> drive-letter colon does not cut the path — and deduplicate against the markers;
> exit 2 means a parse error is present and the remaining files were still formatted.
>
> Every path in `files_changed` and `unparsable_files` is **project-relative with forward
> slashes**, via one `relative_path(path, project_dir)` helper in `formatter/common.py`
> that `run_ruff_imports` reuses in step 5. It must relativize **only when the path is
> absolute** (`os.path.isabs`): ruff runs with `cwd=project_dir` and already prints
> relative paths, so an unconditional `os.path.relpath` re-anchors them against the
> process's cwd and produces `"../.."` garbage.
>
> Write the tests first, including the `invalid-syntax:`-is-not-a-change regression, a
> `check_only=True` run against an unparsable file asserting `success is False` and
> `"src/bad.py" in unparsable_files`, and one real end-to-end test on a `tmp_path` project.
>
> Name the autouse patch fixtures `_fixed_formatter_binary` and `_fixed_version_line`, as
> in steps 2 and 3, so the existing vulture whitelist entries cover them. The unmocked
> end-to-end test restores the real `formatter_binary`.
>
> Do not wire the step into `_STEP_RUNNERS`, `_VALID_STEPS` or `resolve_steps` — step 6
> does that.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check`,
> `run_lint_imports_check`, `run_ruff_check` and `run_vulture_check`. All must pass. Then
> make exactly one commit.
