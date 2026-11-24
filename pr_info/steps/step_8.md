# Step 8 — Wire the workers note into the MCP tool `run_pytest_check`

## LLM prompt
Read `pr_info/steps/summary.md`, then implement **this step only** (`pr_info/steps/step_8.md`).
First write `tests/test_pytest_tool_workers.py` and update `tests/test_server_params.py`, then change `src/mcp_tools_py/checker_tools/pytest_tool.py`.
Run `run_format_code`, pylint, pytest (`markers=["not integration"]`) and mypy; all must pass. Make one commit.

## WHERE
- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `tests/test_server_params.py`
- Create `tests/test_pytest_tool_workers.py`

## WHAT / HOW
In `run_pytest_check`:
1. Before the `try`: `workers_note: str | None = None`.
2. Call `check_code_with_pytest(..., effective=effective)`.
3. Right after it:
   ```python
   workers_note = test_results.get("workers_note")
   if test_results.get("workers_serial"):
       effective = replace(effective, numprocesses=False)   # from dataclasses
   ```
   `_defaults_may_explain` and `marker_notes` then treat a run sized to serial as serial. Their signatures don't change.
4. Notes list: put the workers note first:
   `notes = [*([workers_note] if workers_note else []), *top, *([test_paths_note] ...), *sanitized.notes]`.
5. Outer `except`: `return f"{workers_note}\n\n{error_msg}" if workers_note else error_msg`.
6. Docstring: under `extra_args`, add a short pointer:
   "The worker count of `-n auto` follows `[mcp_tools_py] pytest_workers` in `~/.mcp_coder/config.toml` (see docs/user-config.md); `-n auto` here does not bypass it, a numeric `-n N` does."
   Keep the existing sentence "The project's `addopts` apply first (e.g. `-n auto`), so don't add them again." It is still true.

Use `.get(...)`, because `tests/_pytest_results.make_pytest_results` has no workers keys.

## ALGORITHM
```
workers_note = None
try:
    ... test_results = check_code_with_pytest(..., effective=effective)
    workers_note = test_results.get("workers_note")
    if test_results.get("workers_serial"): effective = replace(effective, numprocesses=False)
    ... notes = [workers_note?, *top, test_paths_note?, *sanitized.notes]
except Exception: return (workers_note + "\n\n" if workers_note else "") + error_msg
```

## Tests (write first)
- `tests/test_server_params.py`: add `effective=ANY` (from `unittest.mock`) to every `assert_called_once_with` on `check_code_with_pytest` that lists all keyword arguments (e.g. `test_run_pytest_check_parameters`). Search the file for `assert_called_once_with(` and `call_args`.
- `tests/test_pytest_tool_workers.py`: patch `mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest` (as `tests/test_pytest_tool_reuse.py` does). Then:
  - `workers_note="workers: 4 (config.toml)"` → the reply starts with that line.
  - The note is followed by the other notes, e.g. a `test_paths_note` comes after it.
  - `workers_note=None` → the reply is unchanged.
  - A run with an `-m` from the project addopts, `-n auto` addopts, a passing result: with `workers_serial=False` the `addopts` line is shown (xdist case); with `workers_serial=True` it is not.
  - An exception raised after `check_code_with_pytest` returned (e.g. patch `checker_tools._format_pytest_result_with_details` to raise) → the reply starts with the workers note and contains "Unexpected error running pytest".
