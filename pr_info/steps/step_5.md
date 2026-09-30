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
The unread `python_executable` is covered by step 2's bare vulture whitelist entry.

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
2 × `ruff-timeout` — exactly as `docs/pyproject-configuration.md:46` already records for
`run_ruff_fix`. Step 8 documents it.

## Why parse errors come from JSON, not the exit code

`ruff check --select I --fix` exits **1** both for a parse error and for ordinary unfixed
violations, and writes nothing to stderr. The exit code cannot discriminate. So syntax
errors are detected from `--output-format json` syntax-error diagnostics instead.

**Verified shape (probed against ruff 0.16.9):** a syntax-error diagnostic carries
`code == "invalid-syntax"` — **not** `null` — with no `fix`, and ruff may emit several
for one file (`def f(:` yields two). The filename comes from `filename`. The
discriminator is the `_is_syntax_error` helper step 4 defined in `ruff_runner.py` —
reuse it, do not define a second one:

```python
def _is_syntax_error(m: RuffMessage) -> bool:
    return not m.code or m.code == "invalid-syntax"
```

The `not m.code` arm is defensive: an earlier note recorded a `null` code, which 0.16.9
does not produce, and a code-less diagnostic cannot be an import-sorting violation.
Every mocked syntax-error diagnostic in the tests uses `"code": "invalid-syntax"`, except
the one `null` repeat in test 6.

## ALGORITHM

```
env    = environment or PythonEnvironment.resolve()   # once, as in step 2
binary = formatter_binary("ruff", env);  if None -> unavailable FormatterResult naming env.bin_dir
json_cmd = [binary, "check", "--select", "I", "--output-format", "json"] + target_dirs
started = time.monotonic()
pre = execute_command(json_cmd, cwd=project_dir, timeout_seconds=...)
timed_out / execution_error -> early return, no version banner
if pre.return_code == 2:  success=False, combined = pre.stderr, files_changed=[], no fix run
messages, parse_error = parse_ruff_json_output(pre.stdout, project_dir)
parse_error -> success=False, output = parse_error, no fix run
unparsable = sorted({norm(m.filename) for m in messages if _is_syntax_error(m)})
violations = sorted({norm(m.filename) for m in messages if not _is_syntax_error(m)})   # any I diagnostic
changed    = sorted({norm(m.filename) for m in messages if m.fixable})
if check_only:  success = (not violations and not unparsable)
                combined = _render_diagnostics(messages, project_dir)   # step 4 helper
else:           started = time.monotonic()
                fix = execute_command([binary, "check", "--select", "I", "--fix"] + target_dirs, ...)
                timed_out / execution_error -> early return, no version banner
                if fix.return_code == 2:  success=False, combined = fix.stderr, files_changed=[],
                                          unparsable_files=[]   # even if the pre-check found some
                # runs even when `unparsable` is non-empty — ruff skips the
                # unparsable file and still sorts the rest
                success = (fix.return_code == 0 and not unparsable)
                combined = combine_output(fix)         # step 3 helper; ruff's text output
remaining = int(timeout_seconds - (time.monotonic() - started))   # budget of the last invocation
output = version_line("ruff", binary, remaining) + per_file_ignores_notice(...) + combined
```

### Exit code 2 is a ruff error, not a result

Ruff exits 2 when it cannot run at all — an invalid `[tool.ruff]` config, an unknown
option. stdout is then empty, so `parse_ruff_json_output` returns `([], None)` and, left
unchecked, check mode would report `success=True` over a tree nobody looked at. Mirror
`run_ruff_fix_impl` (`code_checker_ruff/runners.py:129` and `:159`): after each
invocation, exit 2 means `success=False` with ruff's `stderr` as `combined`. After the
pre-check, the fix run is skipped. `files_changed` is `[]` in both cases. The version
banner and notice are still prepended — ruff ran, it rejected its input.

Exit 2 from the pre-check is checked before parsing. A source syntax error does **not**
produce exit 2 under `ruff check` — verified against ruff 0.16.9: over a tree with one
syntax-error file and one unsorted file, the JSON pre-check exits **1** (stderr empty) and
`--fix` exits **1**, sorts the good file, and prints `Found 3 errors (1 fixed, 2
remaining).` So this does not conflict with "a syntax error does not suppress the fix run"
below.

### Where `combined` comes from

- **Write mode:** the `--fix` run's text output (stdout, then stderr) — ruff's own
  summary of what remains.
- **Check mode:** the only invocation is the JSON pre-check, whose stdout is a raw JSON
  array and not fit for `output`. Render a short readable list from the already-parsed
  `messages` instead with step 4's `_render_diagnostics` — one line per diagnostic, file
  path normalised as below. **No second invocation.** Empty when there are no diagnostics.

The `--fix` run gets the **same** timed-out / execution-error early return as the
pre-check: `success=False`, the bare `ruff timed out …` / `ruff failed to run: …` message,
no version banner and no version subprocess. `files_changed` is `[]` on that return — the
fix may not have been applied, so the pre-check's fixable list is not a claim it can make.

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
and ruff's raw write-mode stderr in `step_4.md`.

Every assertion names the full relative path — `"src/bad.py"`, never a bare `"bad.py"`.

### Check mode fails on *any* `I` diagnostic, not only fixable ones

`changed` is the `fixable` subset, because that is what the fix run will actually rewrite.
`success` in check mode is keyed on `violations` — every diagnostic that is not a syntax
error —
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
`output` and do **not** run the fix. The fix run is skipped only here and on a pre-check
exit 2 (above) — both mean ruff's own output says nothing about the tree.

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
    if that prefix is empty ("*.py", "**/test_*.py") -> skip the key
    if any code is "ALL" or matches ^I\d*$ ("I", "I001"):
        if that prefix and a target dir overlap -> collect the target dir
return "" when nothing collected, else one line naming the directories and the key
```

**Overlap is by path component, not by string.** Normalise both the prefix and the target
dir — backslashes to `/`, trailing `/` stripped — then split each on `/`. They overlap when
either component list is a leading run of the other: `src/sub/**` overlaps target `src`,
and `src/**` overlaps target `src/sub`. A string `startswith` would wrongly match
`tests2/**` against target `tests`; component comparison does not.

**Match codes exactly, not by prefix.** A bare "starts with `I`" also matches unrelated
rule families — `INP001`, `ICN`, `ISC`, `INT` — and would emit a false notice. Only
`"ALL"`, `"I"`, or `I` followed by digits names the isort rules.

A false negative on an exotic pattern means no notice — the status quo, not a regression.
**Known false negatives** (documented, not bugs):

- a key with no leading literal segment (below);
- entries under `extend-per-file-ignores` — not read; the notice covers
  `per-file-ignores` only.

A key with **no** leading literal segment (`"*.py"`, `"**/test_*.py"`) is skipped
because an empty prefix would overlap every target directory, and deciding whether
it really matches would need the glob engine this notice avoids. It is a documented
false negative, not a bug.
A missing `pyproject.toml` yields an empty mapping and therefore `""`. A malformed one
raises the reader's existing `ValueError`, which `per_file_ignores_notice` swallows into
`""` — the notice must never fail the step. (`resolve_steps` in step 6 deliberately lets
that same `ValueError` propagate; the two consumers differ only in how they treat it.)

## DATA

- `output` — version banner, then the notice line when non-empty, then `combined`: the
  `--fix` run's text output in write mode, a per-diagnostic list rendered from the parsed
  pre-check messages in check mode. On exit 2 from either run, ruff's stderr in place of
  `combined`
- `success` — `False` on exit 2 from either run. Otherwise, check mode: no `I` diagnostic
  at all and nothing unparsable. write mode: the fix run exited 0 and nothing was
  unparsable
- `files_changed` — fixable filenames from the pre-check run, deduplicated and sorted;
  `[]` on exit 2 from either run
- `unparsable_files` — filenames of syntax-error diagnostics; `[]` on exit 2 from either
  run, on malformed JSON, and on every early return (missing binary, timed out, execution
  error), including those after the pre-check already found syntax errors

All paths are project-relative with forward slashes. Step 6's write-mode loop relies on
the empty `unparsable_files` above: only a step that reported unparsable files continues
the run, so a ruff error or an early return must still stop it.

## TESTS

**Write first.** The mocked tests use the same two autouse fixtures as step 4, under the
same names: `_fixed_formatter_binary` patching `ruff_runner.formatter_binary` to a fixed
path, and `_fixed_version_line` patching `ruff_runner.version_line` — the
`vulture_whitelist.py` entries from steps 2 and 3 cover them. Test 10 overrides
`_fixed_formatter_binary` to return `None`; the unmocked tests (5, the real sibling in 6,
and 8 if it runs ruff) restore the real function with
`monkeypatch.setattr(ruff_runner, "formatter_binary", common.formatter_binary)`.

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
6. A syntax-error diagnostic (`"code": "invalid-syntax"`, no `fix`) → `unparsable_files`
   populated, the file **not** in `files_changed`, `success is False`, and the fix run
   **is still executed**. Repeat with `"code": null` → same result. Assert both
   invocations happened. Add a real, unmocked `tmp_path` sibling: one file with a
   syntax error and one with unsorted imports, write mode — the good file is sorted on disk,
   `unparsable_files == ["src/bad.py"]`, `success is False`. This is the acceptance
   criterion *"with the other files still formatted"*.
7. Malformed JSON from ruff → `success=False`, parser message in `output`, and **no fix
   run**: ruff's own output was unreadable, so nothing about the tree is known.
7b. **Exit 2, check mode:** pre-check returns exit 2, empty stdout, `stderr` naming an
   invalid `[tool.ruff]` option → `success is False` (not `True` from the empty parse),
   the stderr text in `output`, `files_changed == []`, exactly one invocation.
7c. **Exit 2, write mode:** pre-check exits 1 with one fixable message and one
   syntax-error diagnostic, the `--fix` run exits 2 with stderr → `success is False`, the
   fix run's stderr in `output`, `files_changed == []`, `unparsable_files == []`.
   Separately, a pre-check exit 2 in write mode → exactly one invocation (no fix run).
7d. **`combined` source:** check mode with two diagnostics → `output` contains one
   readable line per diagnostic naming `src/a.py` and the rule code, and does not contain
   the raw JSON (no `"filename"` key); still exactly one invocation. Write mode → `output` contains
   the mocked `--fix` run's stdout text.
8. **`per-file-ignores` fixture:** a `tmp_path` project whose
   `[tool.ruff.lint.per-file-ignores]` ignores `I` for a target directory produces the
   notice in `output`. Acceptance criterion.
9. No `per-file-ignores` at all, and one that ignores a non-`I` code → no notice.
   Include an `INP001` entry on a target directory (`"src/**" = ["INP001"]`) → no notice:
   codes match `ALL` or `^I\d*$`, not a bare `I` prefix.
9a. Keys with no leading literal segment — `"*.py" = ["I001"]` and
   `"**/test_*.py" = ["I"]` — → no notice (documented false negative), no exception.
9b. A **malformed** `pyproject.toml` → no notice and no exception; the step still runs.
9c. **Component overlap, not string prefix:** `"tests2/**" = ["I"]` with target dir
   `tests` → no notice. `"src/sub/**" = ["I"]` with target `src` → notice.
10. Missing ruff binary → `success=False`, no subprocess.
10b. Write mode, pre-check reports a syntax-error diagnostic, **`--fix` run times out**
    (and, separately, returns an `execution_error`) → `success=False`,
    `unparsable_files == []`, the bare timeout / failure message, no version banner,
    `version_line` not called.

`tests/test_project_config.py`:

11. `read_pyproject_tool_tables`: a project with `[tool.black]` and `[tool.ruff.format]`
    returns both keys; a missing `pyproject.toml` returns `{}`; a file without a `[tool]`
    table returns `{}`; a malformed file raises `ValueError`.
12. The existing `_read_mcp_tools_section` / `get_check_timeout` tests still pass
    unchanged — that is the regression on the delegation.

## DONE WHEN

pylint / pytest / mypy / tach / lint-imports / ruff / vulture pass. `run_tach_check` matters here
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
> On ruff 0.16.9 a syntax-error diagnostic has `code == "invalid-syntax"`, **not** `null`;
> reuse step 4's `_is_syntax_error(m)` predicate (`not m.code or m.code == "invalid-syntax"`)
> for both `unparsable` and its complement `violations`.
>
> A syntax error sets `success=False` and populates `unparsable_files` but **does not**
> suppress the fix run — ruff skips that file and still sorts the rest, which the issue
> requires ("with the other files still formatted"). The fix is skipped only on malformed
> JSON from ruff itself or a pre-check exit 2, where nothing about the tree is known.
>
> Check the exit code after **each** invocation, mirroring `run_ruff_fix_impl`
> (`code_checker_ruff/runners.py:129`, `:159`): exit 2 (e.g. an invalid `[tool.ruff]`
> config, empty stdout) means `success=False` with ruff's stderr in `output` and
> `files_changed=[]` — otherwise the empty parse would report a clean check. That return,
> malformed JSON and every early return also carry `unparsable_files=[]`, even when the
> pre-check found syntax errors: step 6's loop continues past any step that reports
> unparsable files, and these failures must stop it.
>
> In write mode, `output` carries the `--fix` run's text output via `combine_output`. In
> check mode, render the already-parsed messages with step 4's `_render_diagnostics` —
> never the raw JSON, and no second invocation.
>
> Both invocations get the same timed-out / execution-error early return — no version
> banner, no version subprocess. The version banner otherwise comes from
> `version_line("ruff", binary, remaining)` with what is left of the last invocation's
> budget.
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
> engine — and never let it fail the step. Compare the prefix and each target dir by path
> component, not string `startswith` (`tests2/**` must not match `tests`). Match codes
> `"ALL"` or `^I\d*$` only — a bare `I` prefix would also catch `INP001`, `ICN`, `ISC`, `INT`. A key with no leading literal
> segment (`"*.py"`, `"**/test_*.py"`) is skipped, and `extend-per-file-ignores` is not
> read: both are documented false negatives.
>
> Read `pyproject.toml` through a **new public**
> `read_pyproject_tool_tables(project_root: Path)` in `src/mcp_tools_py/utils/project_config.py`,
> and rewrite the existing private `_read_mcp_tools_section` to delegate to it. Do not
> hand-roll a `tomllib` read inside `formatter/`. Step 6's `resolve_steps` reuses this same
> helper and adds no second reader.
>
> Write the tests first, including the real unsorted-imports end-to-end test and the
> `per-file-ignores` fixture. Name the autouse patch fixtures `_fixed_formatter_binary`
> and `_fixed_version_line`, as in steps 2–4; the unmocked tests restore the real
> `formatter_binary`.
>
> Do not wire the step into `_STEP_RUNNERS`, `_VALID_STEPS` or `resolve_steps` — step 6
> does that.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check`,
> `run_lint_imports_check`, `run_ruff_check` and `run_vulture_check`. All must pass. Then
> make exactly one commit.
