# Step 1 — Bandit: temp-file JSON capture + empty-file guard

**Goal:** Fix the real bug (Item 1 in `summary.md`). bandit writes JSON to a temp
file via `-o <file>`; the runner reads it back instead of `result.stdout`,
immune to the Rich progress bar on stdout. Add an anomaly guard for a
missing/empty file on an otherwise-successful run.

**One commit:** reworked tests + implementation + all checks passing.

---

## WHERE
- Production:
  - `src/mcp_tools_py/code_checker_bandit/runners.py`
- Tests:
  - `tests/test_code_checker_bandit/test_runners.py`

No changes to `models.py`, `parsers.py`, `reporting.py`, or `bandit_tool.py`
(`raw_output` is informational and not consumed downstream).

## WHAT (signatures)

```python
def _build_bandit_command(
    bandit_binary: str,
    target_directories: list[str],
    output_path: str,                       # NEW
    extra_args: list[str] | None = None,
) -> list[str]: ...

@log_function_call
def run_bandit_check_impl(
    bandit_binary: str,
    project_dir: str,
    target_directories: list[str],
    extra_args: list[str] | None = None,
) -> BanditResult: ...                      # signature UNCHANGED
```

## HOW (integration points)
- Add imports `shutil`, `tempfile` (already imports `os`, `logging`) to
  `runners.py`.
- `_build_bandit_command` inserts `-o <output_path>` into argv. Chosen order:
  `[bandit_binary, "-f", "json", "-o", output_path, "-r", *dirs, *extra_args]`.
- `run_bandit_check_impl` reads the temp file with a plain
  `Path(output_file).read_text(encoding="utf-8")` and passes it to the unchanged
  `parse_bandit_json_output(...)`.
- Error/timeout/`return_code > 1` paths stay stdout/stderr-based and run
  **before** the file read (unchanged behavior).

## ALGORITHM (run_bandit_check_impl core)
```
if not isdir(project_dir): raise FileNotFoundError
temp_dir = tempfile.mkdtemp(prefix="bandit_runner_")
try:
    output_file = join(temp_dir, "bandit_result.json")
    cmd = _build_bandit_command(binary, dirs, output_file, extra_args)
    result = execute_command(cmd, cwd=project_dir)
    if result.execution_error: return BanditResult(error=...)        # before read
    if result.timed_out:       return BanditResult(error="timed out")
    if result.return_code > 1:  return BanditResult(error=result.stderr)
    if not exists(output_file) or getsize(output_file) == 0:         # GUARD
        return BanditResult(return_code=result.return_code, ...,
                            error="bandit produced no JSON output file ...")
    content = read_text(output_file)
    messages, errors, parse_error = parse_bandit_json_output(content, project_dir)
    if parse_error: return BanditResult(error=parse_error)
    return BanditResult(return_code=..., messages, errors, raw_output=content)
finally:
    shutil.rmtree(temp_dir, ignore_errors=True)
```

## DATA
- Returns `BanditResult` (NamedTuple, unchanged shape). On success
  `raw_output` = temp-file contents. The guard returns a `BanditResult` whose
  `error` is a clear explanatory string (so `bandit_tool.py` surfaces
  `bandit error: ...`).

## TESTS (TDD — write first, watch fail, then implement)
Rework `tests/test_code_checker_bandit/test_runners.py`:
- `TestBuildBanditCommand`: pass an `output_path` and assert exact argv now
  includes `-o <path>`, e.g.
  `["/usr/bin/bandit", "-f", "json", "-o", "/tmp/out.json", "-r", "src"]`
  (plus the extra-args and multi-dir variants).
- `TestRunBanditCheckImpl` (`test_no_issues`, `test_with_issues`): replace
  `mock_exec.return_value = make_command_result(..., stdout=output)` with a
  `side_effect` that writes the JSON to the `-o` path it receives, then returns a
  result with no stdout:
  ```python
  def _write(cmd, cwd=None):
      out = cmd[cmd.index("-o") + 1]
      Path(out).write_text(output, encoding="utf-8")
      return make_command_result(return_code=0)   # or 1 for with_issues
  mock_exec.side_effect = _write
  ```
- New `test_empty_output_file_is_error`: `side_effect` returns
  `return_code=0` **without** writing the file (or writes `""`); assert
  `result.error` is set and `result.messages == []` (anomaly, not "no issues").
- Keep `test_error_exit_code_gt_1`, `test_execution_error`, `test_timeout`,
  `test_invalid_project_dir` essentially unchanged (they short-circuit before the
  file read; a no-op `side_effect`/`return_value` is fine since no file is read).

## VERIFY
1. `run_pylint_check`
2. `run_pytest_check` extra_args `["-n","auto","-m","not git_integration and not claude_cli_integration and not claude_api_integration and not formatter_integration and not github_integration and not langchain_integration"]`
3. `run_mypy_check`
4. `./tools/format_all.sh`, then commit.

## LLM PROMPT
> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`. Implement Step 1
> only (Item 1, the bandit temp-file fix). Use TDD: first rework
> `tests/test_code_checker_bandit/test_runners.py` to the file seam (assert
> `-o <file>` in `_build_bandit_command` argv; make the `execute_command` mock a
> `side_effect` that writes the JSON report to the `-o` path; add a test for the
> empty/missing-file guard), then update
> `src/mcp_tools_py/code_checker_bandit/runners.py`: add an `output_path` param to
> `_build_bandit_command` inserting `-o <file>`, and rewrite `run_bandit_check_impl`
> to create `tempfile.mkdtemp(prefix="bandit_runner_")`, read the JSON back from the
> file, guard a missing/empty file on `return_code <= 1` as an explicit error, and
> clean up with `shutil.rmtree(..., ignore_errors=True)` in a `finally`. Keep the
> error/timeout/`return_code > 1` paths before the file read and unchanged. Do not
> touch `parsers.py`, `models.py`, or `bandit_tool.py`. Run pylint, pytest
> (`-n auto` with the integration-exclusion `-m`), and mypy until all pass, then
> format and commit.
