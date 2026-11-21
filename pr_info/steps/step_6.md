# Step 6 — `Command:` line in pytest error replies

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_6.md`).
> Step 5 (auto-install removed) is already done.
> Implement only this step, test first. Then run `run_format_code`, pylint, mypy and
> pytest (`extra_args=["-n", "auto", "-m", "not integration"]`); all must pass.
> This step is exactly one commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/runners.py` — `run_tests`, `check_code_with_pytest`
- `tests/test_code_checker/test_runners.py`

## WHAT

```python
# runners.py, module level
# Attribute run_tests sets on an exception it re-raises: the command, for the error reply.
_COMMAND_ATTR = "pytest_command"
```

`run_tests`:
- `report_file_arg = f"--json-report-file={temp_report_file}"`; use it in the existing
  `command.extend([... "--json-report", report_file_arg])`.
- After `extra_args` are appended: `shown_command = " ".join(arg for arg in command if arg != report_file_arg)`.
- Inner `except Exception as e:` (the one that logs `"Pytest execution failed"`): add
  `setattr(e, _COMMAND_ATTR, shown_command)` before `raise e`; keep the existing logging
  (full `command_line`) unchanged.
- Timeout raise: `TimeoutError(f"Subprocess timed out after {timeout_seconds} seconds.{detail}")`
  — the inline command is removed. The `logger.warning("Command timed out …")` stays.

`check_code_with_pytest` `except Exception as e:` branch:

## ALGORITHM

```
problems = [str(e)]
command = getattr(e, _COMMAND_ATTR, None)
if command:
    problems.append(f"Command: {command}")
return {"verdict": RunVerdict(RunStatus.ERROR, problems, 0), "test_paths_note": note}
```

## HOW

- Use the named constant with `setattr`/`getattr` (ruff B009/B010 only flag literal names;
  mypy would reject `e.pytest_command = …`).
- Exception type and `str(e)` stay unchanged, so the `Raises:` docs and the existing
  `pytest.raises(...)` tests keep passing.
- Exceptions raised before the inner `try` (e.g. `tempfile.mkdtemp`, `resolve_test_paths`)
  carry no attribute → no `Command:` line (out of scope).
- `test_check_code_with_pytest_with_error` stays unchanged.

## DATA

`verdict.problems == [<exception message>, "Command: <python> -m pytest … --json-report …"]`.

## Tests (write first) — `tests/test_code_checker/test_runners.py`

One parametrized test driving the real `run_tests` through `check_code_with_pytest`
with `execute_command` patched (pattern: `test_path_args_skip_default_folder_integration`):

| case | mock / patches | expected `problems[0]` contains |
|---|---|---|
| no tests | `return_code=5`, `stdout="collected 0 items"` | `"No Tests Found"` |
| timeout | `timed_out=True`, `execution_error="Process timed out after 300 seconds"` | `"Subprocess timed out after 300 seconds"` |
| unparsable report | `return_code=0`; patch `runners.os.path.isfile` → `True`, `runners.read_file` → `"{}"`, `runners.parse_pytest_report` → `side_effect=json.JSONDecodeError("x", "", 0)` | `"x"` |

Assertions for every case:
- `verdict.status is RunStatus.ERROR`;
- `command_lines = [l for p in verdict.problems for l in p.splitlines() if l.startswith("Command: ")]`
  has length 1;
- that line contains `"-m pytest"` and `"--json-report"`, and not `"--json-report-file"`;
- for the timeout case, `problems[0]` does not contain `"-m pytest"`.

If `setattr` on any of these exceptions raises (attaching fails), write one line to
`pr_info/.blocked.txt` and stop.
