# Step 2: Extract `run_format_code` into `runner.py` + update MCP wrapper

> **Context**: See [summary.md](summary.md) for architecture overview and full file list.

## Objective

Extract the orchestration logic (step validation, runner loop, fail-fast) from
the MCP closure in `formatter_tools.py` into a plain module-level function in
`formatter/runner.py`. The MCP wrapper becomes a thin shell: resolve dirs,
check tool availability, call `run_format_code()`, format result to string.

## Commit message

```
refactor(formatter): extract run_format_code into runner.py
```

---

## Part A: Create `formatter/runner.py`

### WHERE
- **Create**: `src/mcp_tools_py/formatter/runner.py`
- **Create**: `tests/test_formatter_runner.py`

### WHAT
```python
from pathlib import Path
from mcp_tools_py.formatter.models import FormatterResult

_VALID_STEPS: set[str] = {"isort", "black"}

def run_format_code(
    python_executable: str,
    project_root: Path,
    target_dirs: list[str],
    steps: list[str] | None = None,
    check_only: bool = False,
) -> dict[str, FormatterResult]:
```

### ALGORITHM
```
resolved_steps = steps or ["isort", "black"]
validate steps against _VALID_STEPS → raise ValueError if invalid
results = {}
for step in resolved_steps:
    result = _STEP_RUNNERS[step](python_executable, target_dirs, str(project_root), check_only)
    results[step] = result
    if not result.success and not check_only → break (fail-fast)
return results
```

### DATA
- **Input**: `python_executable` (str), `project_root` (Path), `target_dirs` (list[str]), `steps` (optional), `check_only` (bool)
- **Output**: `dict[str, FormatterResult]` — keyed by step name, ordered by execution
- **Error**: `ValueError` for invalid step names (not a string error — callers handle it)
- Moves `_STEP_RUNNERS` dict and `_VALID_STEPS` set from `formatter_tools.py` to `runner.py`

### HOW
- Imports `run_black` from `formatter.black_runner`, `run_isort` from `formatter.isort_runner`
- `_STEP_RUNNERS: dict[str, Callable[..., FormatterResult]]` maps step names to runners
- No tool availability check (MCP wrapper's responsibility)
- No directory resolution (caller's responsibility)

### TESTS (`tests/test_formatter_runner.py`)
- `test_default_steps_runs_isort_then_black` — mock both runners, verify call order
- `test_custom_steps_runs_only_requested` — `steps=["black"]`, verify only black called
- `test_invalid_step_raises_valueerror` — `steps=["ruff"]`, assert `ValueError`
- `test_fail_fast_stops_on_failure` — isort fails, verify black not called
- `test_check_only_continues_on_failure` — isort fails with check_only=True, verify black still called
- `test_returns_dict_keyed_by_step` — verify keys match requested steps
- `test_passes_check_only_to_runners` — verify check_only forwarded

---

## Part B: Update `formatter_tools.py` to delegate

### WHERE
- **Modify**: `src/mcp_tools_py/formatter/formatter_tools.py`
- **Modify**: `tests/test_formatter_tools.py`

### WHAT
The MCP closure becomes a thin wrapper:

```python
def run_format_code(
    steps: list[str] | None = None,
    target_directories: list[str] | None = None,
    check_only: bool = False,
) -> str:
    # 1. Resolve target directories
    # 2. Check tool availability for requested steps
    # 3. Call runner.run_format_code(...)
    # 4. Format dict[str, FormatterResult] → string
```

### ALGORITHM
```
resolve target_directories → dirs (or return error string)
resolved_steps = steps or ["isort", "black"]
for step in resolved_steps:
    if tool not available → return error string
try:
    results = runner.run_format_code(python_exec, project_root, dirs, steps, check_only)
except ValueError as e:
    return str(e)
return _format_results(results, resolved_steps, check_only)
```

### HOW
- Import `run_format_code as _run_format_code` from `formatter.runner` (or use qualified name)
- Remove `_STEP_RUNNERS` dict and `_VALID_STEPS` from this file (moved to runner.py)
- Remove `run_black` / `run_isort` direct imports (no longer needed here)
- Add `_format_results(results: dict[str, FormatterResult], steps: list[str], check_only: bool) -> str` helper
- `_format_results` algorithm:
  - for step in steps:
      - if step in results: append `## {step}\n{result.output}`
      - (if step not in results, runner stopped before reaching it)
  - if not check_only and any result has success=False and len(results) < len(steps):
      append `\nFormatting stopped due to errors in {failed_step} step.`
  - return joined output

### TEST CHANGES (`tests/test_formatter_tools.py`)
- Tests now mock `mcp_tools_py.formatter.formatter_tools._run_format_code` (or the runner module)
  instead of `_STEP_RUNNERS`
- `TestRegistration` — unchanged
- `TestStepOrdering` — mock `runner.run_format_code`, verify steps passed through
- `TestValidation` — mock `runner.run_format_code` to raise `ValueError`, verify error string
- `TestTargetDirectories` — unchanged (still tests resolve_target_directories)
- `TestCheckOnlyMode` — mock `runner.run_format_code` returning failed results, verify string output
- `TestOutput` — mock `runner.run_format_code`, verify markdown headers
- `TestToolAvailability` — unchanged (tests wrapper's own availability check)

---

## Part C: Update `formatter/__init__.py`

### WHERE
- **Modify**: `src/mcp_tools_py/formatter/__init__.py`

### WHAT
Add exports for external callers:
```python
from mcp_tools_py.formatter.models import FormatterResult
from mcp_tools_py.formatter.runner import run_format_code

__all__ = ["FormatterTools", "FormatterResult", "run_format_code"]
```

---

## Verification

Run all checks — pytest, pylint, mypy, ruff, lint-imports, vulture must pass.

---

## LLM Prompt

```
You are implementing Step 2 of issue #151 for the mcp-tools-py project.
Read pr_info/steps/summary.md for full context, then pr_info/steps/step_2.md
for this step's details.

Tasks:
1. Create src/mcp_tools_py/formatter/runner.py with plain run_format_code()
2. Create tests/test_formatter_runner.py with tests (TDD: write tests first)
3. Update formatter_tools.py to be a thin MCP wrapper delegating to runner.py
4. Update tests/test_formatter_tools.py for the new delegation pattern
5. Update formatter/__init__.py exports
6. Run all quality checks and fix any issues

The orchestration logic moves from formatter_tools.py to runner.py.
formatter_tools.py keeps only MCP-specific concerns: tool availability,
dir resolution, result→string formatting.
```
