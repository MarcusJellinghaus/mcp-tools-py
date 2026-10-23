# Step 3 — `code_checker_deptry/runners.py`: model, parser, runner

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_3.md`. Write the tests first, then the code. Use `code_checker_bandit/runners.py` (temp-dir JSON) and `code_checker_mypy/runners.py` (`python -m`, `check_tool_missing_error`) as models. Run the checks listed in the summary, including lint-imports and tach, and commit once.

## WHERE

- `src/mcp_tools_py/code_checker_deptry/__init__.py` (new; one-line docstring, re-exports `DeptryMessage`, `DeptryResult`, `run_deptry_check_impl`)
- `src/mcp_tools_py/code_checker_deptry/runners.py` (new)
- `.importlinter`: add `mcp_tools_py.code_checker_deptry` to the code_checker layer line and to the `forbidden_modules` list.
- `tach.toml`: a new `[[modules]]` entry (layer `tool_implementation`, depends on `utils` and `log_utils`), and add it to `mcp_tools_py.checker_tools`' `depends_on`.
- `tests/test_code_checker_deptry/__init__.py`, `tests/test_code_checker_deptry/test_runners.py` (new)

## WHAT

```python
class DeptryMessage(NamedTuple):
    code: str            # "DEP001"
    message: str
    module: str
    file: str            # as deptry reports it; "pyproject.toml" for DEP002
    line: int | None
    column: int | None

class DeptryResult(NamedTuple):
    return_code: int
    messages: list[DeptryMessage]
    error: str | None = None
    raw_output: str | None = None

def parse_deptry_json_output(content: str) -> tuple[list[DeptryMessage], str | None]: ...

@log_function_call
def run_deptry_check_impl(
    python_executable: str,
    project_dir: str,
    target_directories: list[str],
    extra_args: list[str] | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> DeptryResult: ...
```

## HOW

- Imports: `execute_command`, `check_tool_missing_error`, `truncate_stderr` from `mcp_tools_py.utils.subprocess_runner`; `DEFAULT_CHECK_TIMEOUT` from `utils.project_config`; `log_function_call` from `mcp_tools_py.log_utils`.
- Command: `[python_executable, "-m", "deptry", *target_directories, "--json-output", output_file, *(extra_args or [])]` with `cwd=project_dir`.
- Rejected `extra_args`: a token equal to `--json-output` or `-o`, or starting with `--json-output=`. The rejection returns `DeptryResult(return_code=-1, messages=[], error="<flag> changes where deptry writes its report and is not supported; run_deptry_check reads the JSON report itself.")` and does not run deptry.

## ALGORITHM

```
if not isdir(project_dir): raise FileNotFoundError; if rejected flag: return error result
temp_dir = mkdtemp(prefix="deptry_runner_"); try: run command
  missing = check_tool_missing_error(stderr, "deptry", python) -> error; timed_out -> "timed out after N seconds"
  execution_error -> error (+ stderr snippet); return_code not in (0, 1) -> f"deptry exited with code {rc}: {snippet}"
  file missing/empty -> f"deptry produced no JSON output file (exit code {rc}): {snippet}"
  messages, parse_error = parse(content); parse_error -> error (+ snippet); else DeptryResult(rc, messages, raw_output=content)
finally: shutil.rmtree(temp_dir, ignore_errors=True)
```

`snippet` is `truncate_stderr(stderr.strip())`, and is omitted when stderr is empty.

Parser: `json.loads`. The top level must be a list. Inside one `try` (catching `KeyError`, `TypeError`, `ValueError`), build each `DeptryMessage` from `item["error"]["code"]`, `item["error"]["message"]`, `item["module"]`, `item["location"]["file"]`, `item["location"]["line"]` and `item["location"]["column"]`. `line` and `column` must be `int` or `None`, and the strings must be `str`. Any mismatch returns `([], "Could not parse deptry JSON output: <reason>")`.

## DATA

`DeptryResult` with `error` set (and `messages == []`), or with `messages` (possibly empty) and `raw_output`.

## Tests (write first; mock `execute_command` in `mcp_tools_py.code_checker_deptry.runners` and write the JSON file from the mock's side effect)

- Parser: valid list → messages, DEP002 with `null` line/column → `None`, `[]` → no messages, invalid JSON, non-list, missing key, wrong type.
- Runner:
  - the command contains `-m deptry`, the targets, `--json-output <file in temp dir>` and the extra args, and `cwd=project_dir`
  - exit 0 + `[]` → clean; exit 1 + findings → messages
  - **exit 1 with no file → error** (the crash case)
  - exit 2 → error containing a stderr snippet
  - unparsable file → error
  - timeout, execution error, and `"No module named deptry"` → `check_tool_missing_error` message
  - each of `--json-output`, `--json-output=x.json` and `-o` is rejected without running
  - `--config other.toml` is allowed
  - the temp dir is removed afterwards (also on error)
  - a missing project dir raises `FileNotFoundError`.
