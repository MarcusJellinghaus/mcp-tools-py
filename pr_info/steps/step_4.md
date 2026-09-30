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

Command:

| mode | argv |
|---|---|
| write | `[ruff_binary, "format"] + target_dirs` |
| check | `[ruff_binary, "format", "--check", "--output-format", "json"] + target_dirs` |

`ruff_binary` comes from the same `formatter_binary("ruff", env)` helper step 2
introduced, `env` resolved once as step 2 specifies.

## Observed output (probed, ruff 0.16.9, Windows)

A tmp project with `src/ugly.py` (unformatted), `src/bad.py` (`def f(:`) and `src/ok.py`
(formatted):

- **`--check --output-format json`** — exit 2 (1 when only `ugly.py` is present), stderr
  empty, stdout a JSON array with one entry per affected file and nothing for `ok.py`.
  Entries carry `code == "unformatted"` (`message` "File would be reformatted", `fix`
  present) or `code == "invalid-syntax"` (`fix` null), and an **absolute** `filename`.
  No "N files would be reformatted" summary line. `parse_ruff_json_output` parses it
  without error into `RuffMessage(code="unformatted", filename="src\\ugly.py", …)` and
  `RuffMessage(code="invalid-syntax", filename="src\\bad.py", …)` — it relativizes the
  path itself.
- **Default text output is not stable.** With `[tool.ruff] output-format = "concise"` in
  `pyproject.toml`, or `RUFF_OUTPUT_FORMAT=concise` in the environment, plain `--check`
  prints `src\bad.py:1:7: invalid-syntax: …` — no line-leading marker and no ` --> `
  header. A text parser would silently find nothing.
- **An explicit `--output-format` wins** over both the config key and the env var (`json`
  and `full` alike).
- **Write mode** reports a syntax error on stderr only, as
  `error: Failed to parse src\bad.py:1:7: <message>`, and still formats the other files.

`pyproject.toml` already requires `ruff>=0.16.8` (user decision, applied with the plan).

## ALGORITHM

```
env    = environment or PythonEnvironment.resolve()   # once, as in step 2
binary = formatter_binary("ruff", env);  if None -> unavailable FormatterResult naming env.bin_dir
cmd    = [binary, "format"] + (["--check", "--output-format", "json"] if check_only else []) + target_dirs
started = time.monotonic()
result = execute_command(cmd, cwd=project_dir, timeout_seconds=...)
timed_out / execution_error -> early return, no version banner   (as the other runners)
remaining = int(timeout_seconds - (time.monotonic() - started))
stderr_bad = _FAILED_TO_PARSE.findall(result.stderr)   # see `_FAILED_TO_PARSE` below
if check_only:
    messages, parse_error = parse_ruff_json_output(result.stdout, project_dir)
    parse_error -> success=False, output = banner + parse_error + stderr,
                   files_changed=[], unparsable_files=[]
    changed   = [m.filename for m in messages if m.code == "unformatted"]
    json_bad  = [m.filename for m in messages if _is_syntax_error(m)]
    combined  = _render_diagnostics(messages, project_dir) + result.stderr
else:
    changed, json_bad = [], []
    combined  = combine_output(result)
unparsable = dedup(stderr_bad + json_bad)      # every path through relative_path
return FormatterResult(output=version_line("ruff", binary, remaining) + combined,
                       success=(return_code == 0), files_changed=relative(changed),
                       unparsable_files=unparsable)
```

Two module-level helpers in `ruff_runner.py`, defined here and reused by
`run_ruff_imports` in step 5 — one definition each:

```python
def _is_syntax_error(m: RuffMessage) -> bool:
    return not m.code or m.code == "invalid-syntax"

def _render_diagnostics(messages: list[RuffMessage], project_dir: str) -> str:
    """One line per diagnostic: '<relative_path>: <code or invalid-syntax> <message>'."""
```

The `not m.code` arm is defensive (see `step_5.md`). The JSON stdout itself never goes
into `output` — it is a raw array, not fit to read.

### Exit codes

| code | meaning |
|---|---|
| 0 | everything formatted |
| 1 | would reformat (`--check` only) |
| 2 | a parse error is present — **2 wins over 1** |

On a parse error in write mode ruff writes `error: Failed to parse <path>:<l>:<c>` to
stderr **and still formats the remaining files**. So a populated `unparsable_files` coexists with real
work having been done. `success = return_code == 0` therefore already yields
`success=False` on both 1 and 2; no extra `and not unparsable` clause is needed, unlike
isort which exits 0 and skips silently.

### `files_changed`

**Empty in write mode. Parsed in `--check` mode only.** Write mode prints only
`N files reformatted` and never names a file — there is nothing to parse, and inventing
an answer would be worse than an empty list.

`--check` mode reads the JSON diagnostics (see "Observed output"): `code == "unformatted"`
contributes to `files_changed`; a `_is_syntax_error` diagnostic contributes to
**`unparsable_files`** — its path is recorded, not discarded. Discarding it would leave
`--check` mode reporting `success=False` with an empty `unparsable_files`, so
`_unparsable_block` never tells the caller which files went unchecked: the same silent skip
in a different place. Keying on the diagnostic `code` also keeps an unparsable file out of
`files_changed`, which is what the issue's "key on the marker line" warning guards against.

Malformed JSON (`parse_error`) says nothing about the tree: `success=False`, the parser's
message in `output`, and both lists empty.

Extract the write-mode stderr path with a module-level
`_FAILED_TO_PARSE = re.compile(r"error: Failed to parse (.+?):\d+:\d+")`. Anchoring on the
`:<line>:<col>` pair, rather than splitting at the first `:`, keeps an absolute Windows
path such as `C:\repo\src\bad.py` intact — its drive-letter colon is not followed by
digits and a second colon.

`unparsable_files` is the union of the JSON syntax-error paths and any
`error: Failed to parse` paths on stderr — ruff reports a parse error through a different
channel in each mode, so both are read in both modes and the result deduplicated.

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
prints write-mode stderr paths relative to it, and `parse_ruff_json_output` has already
applied `os.path.relpath` to the absolute JSON `filename`. Calling `os.path.relpath` on a path that
is *already* relative re-anchors it against the **process's** cwd, not `project_dir`, so
`"src/bad.py"` becomes something like `"../../../repo/src/bad.py"` whenever the test
process's cwd differs from the tmp project — which it always does. Relativize only when
the path is absolute; otherwise just normalize the separators.

Assert against `"src/bad.py"`, never a bare `"bad.py"`.

## DATA

`FormatterResult(output, success, files_changed, unparsable_files)` — unchanged shape.
Paths in both lists are project-relative with forward slashes.

- `output` — version banner line, then, truncated: write mode, ruff's combined stdout
  and stderr (`combine_output`); check mode, `_render_diagnostics` lines plus stderr, or
  the parser's message on malformed JSON
- `success` — `return_code == 0`; `False` on malformed JSON
- `files_changed` — `[]` in write mode; `code == "unformatted"` paths in `--check` mode
- `unparsable_files` — `_is_syntax_error` JSON paths plus `error: Failed to parse` paths
  from stderr, deduplicated

Every early return — missing binary, timed out, execution error — leaves
`unparsable_files` empty, and so do malformed JSON and exit 2 from a config error (no
syntax-error diagnostic, no `error: Failed to parse` on stderr). Step 6's write-mode loop relies on this: only a step
that reported unparsable files continues the run.

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
2. `check_only=True` argv is exactly
   `[ruff, "format", "--check", "--output-format", "json", "src"]` — the explicit flag is
   what overrides a project's `output-format` config or `RUFF_OUTPUT_FORMAT`.
3. Bogus `python_executable` does not change argv (acceptance criterion).
4. Write mode `files_changed` is empty even when stdout says `2 files reformatted`.
5. `--check` mode maps `"code": "unformatted"` diagnostics into `files_changed`, as
   `["src/ugly.py"]` — project-relative, forward slashes. Mocked JSON uses an absolute
   `filename` built with `os.path.join(project_dir, "src", "ugly.py")`, as ruff emits.
6. **`invalid-syntax` is not counted as changed, and is not dropped either.** Feed JSON
   with one `unformatted` and one `invalid-syntax` diagnostic and assert
   `files_changed == ["src/ugly.py"]` **and** `unparsable_files == ["src/bad.py"]`.
6b. **Check-mode `output`:** contains one readable line per diagnostic naming
   `src/ugly.py` and `unformatted`, and not the raw JSON (no `"filename"` key).
6c. **Malformed JSON** on stdout → `success is False`, the parser's message in `output`,
   `files_changed == []`, `unparsable_files == []`.
7. Exit 2 with `error: Failed to parse src/bad.py:1:7` on stderr →
   `unparsable_files == ["src/bad.py"]` and `success is False`.
7b. `_FAILED_TO_PARSE` keeps a drive-letter path whole:
   `_FAILED_TO_PARSE.findall(r"error: Failed to parse C:\repo\src\bad.py:1:7: msg")`
   returns `[r"C:\repo\src\bad.py"]`. Test the pattern directly, not the runner's
   normalized result — `relative_path` on a Windows path is platform-dependent and CI runs
   on Linux.
7c. Exit 2 with empty stdout and a config error on stderr (no `Failed to parse`) →
   `success is False`, `unparsable_files == []`, the stderr text in `output`.
8. **`check_only=True` against an unparsable file** — exit 2, only an `invalid-syntax`
   diagnostic in the JSON, and nothing on stderr. Assert `success is False` **and**
   `"src/bad.py" in unparsable_files`. This is the case a parser that discarded the path
   would report as failed-but-with-nothing-named.
9. `relative_path`: a native-separator relative path, built with
   `os.path.join("src", "bad.py")` (never a hard-coded `"src\\bad.py"` — CI runs on Linux,
   where `os.sep` is `/` and a backslash is a legal filename character, not a separator),
   normalizes to `"src/bad.py"` **unchanged in depth** — run the test from a cwd that is
   not `project_dir` so a missing `os.path.isabs` guard shows up as a `"../"` prefix. An
   absolute path under `project_dir`, built with `os.path.join(project_dir, "src",
   "bad.py")`, normalizes to `"src/bad.py"` too.
10. Missing ruff binary → `success=False`, `unparsable_files == []`, no subprocess.
11. Timed out and execution-error paths → `success=False`, `unparsable_files == []`, no
    version banner, and `version_line` not called.
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
> Check mode runs `ruff format --check --output-format json` — the explicit flag overrides
> a project's `output-format` setting or `RUFF_OUTPUT_FORMAT`, which change the text
> output. Parse stdout with `parse_ruff_json_output` from `mcp_tools_py.utils.ruff_parsing`.
> `code == "unformatted"` paths go to `files_changed`; syntax-error paths go to
> `unparsable_files` through a module-level `_is_syntax_error(m)`
> (`not m.code or m.code == "invalid-syntax"`) — **record them, do not discard them**, or
> `--check` mode returns `success=False` with nothing named. Render check-mode `output`
> with a module-level `_render_diagnostics(messages, project_dir)`, one line per
> diagnostic, never the raw JSON. Step 5 reuses both helpers. Malformed JSON →
> `success=False`, the parser's message in `output`, both lists empty.
>
> `files_changed` stays empty in write mode, because `ruff format` never names the files
> it changed there. In both modes also parse `unparsable_files` from
> `error: Failed to parse <path>:<l>:<c>` on stderr with a module-level
> `_FAILED_TO_PARSE = re.compile(r"error: Failed to parse (.+?):\d+:\d+")` — so a
> drive-letter colon does not cut the path — and deduplicate; exit 2 means a parse error
> is present and the remaining files were still formatted. Write-mode `output` uses
> step 3's `combine_output`.
>
> Every path in `files_changed` and `unparsable_files` is **project-relative with forward
> slashes**, via one `relative_path(path, project_dir)` helper in `formatter/common.py`
> that `run_ruff_imports` reuses in step 5. It must relativize **only when the path is
> absolute** (`os.path.isabs`): ruff's stderr paths and `parse_ruff_json_output`'s
> filenames are already relative, so an unconditional `os.path.relpath` re-anchors them
> against the process's cwd and produces `"../.."` garbage.
>
> Write the tests first, including the check-mode argv carrying `--output-format json`,
> the `invalid-syntax`-is-not-a-change regression, a
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
