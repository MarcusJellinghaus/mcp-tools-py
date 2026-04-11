# Step 1: FormatterResult model + update both runners

> **Context**: See [summary.md](summary.md) for architecture overview and full file list.

## Objective

Introduce `FormatterResult` dataclass and update `run_black` / `run_isort` to
return it instead of `tuple[str, bool]`. Parse `files_changed` from formatter
output.

## Commit message

```
refactor(formatter): add FormatterResult model, update runners
```

---

## Part A: Create `formatter/models.py`

### WHERE
- **Create**: `src/mcp_tools_py/formatter/models.py`

### WHAT
```python
@dataclasses.dataclass
class FormatterResult:
    output: str           # raw text output (for MCP display)
    success: bool         # True when return_code == 0
    files_changed: list[str]  # parsed file paths that were (or would be) changed
```

### DATA
- Used by `black_runner.py`, `isort_runner.py`, `runner.py` (step 2), `formatter_tools.py` (step 2)
- Mirrors mcp_coder's interface with added `output` field (issue decision #12)

---

## Part B: Update `black_runner.py`

### WHERE
- **Modify**: `src/mcp_tools_py/formatter/black_runner.py`
- **Modify**: `tests/test_black_runner.py`

### WHAT
Change `run_black` return type from `tuple[str, bool]` to `FormatterResult`.
Add `_parse_black_changed_files()` helper.

```python
def run_black(
    python_executable: str,
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
) -> FormatterResult:
```

### ALGORITHM — `_parse_black_changed_files`
```
for each line in combined output:
    if line starts with "reformatted " → extract path, add to list
    if line starts with "would reformat " → extract path, add to list
return list
```

Black output examples:
- Normal mode: `reformatted src/foo.py`
- Check mode: `would reformat src/foo.py`

### HOW
- Import `FormatterResult` from `formatter.models`
- Replace `return _truncate_output(output), result.return_code == 0` with
  `return FormatterResult(output=..., success=..., files_changed=...)`

### TEST CHANGES (`tests/test_black_runner.py`)
- Update all existing tests: unpack `result.output` / `result.success` instead of `output, success`
- Add test: `test_run_black_parses_reformatted_files` — mock `CommandResult` with `stderr` containing `reformatted src/foo.py` (combined into output for parsing), assert `files_changed == ["src/foo.py"]`
- Add test: `test_run_black_parses_would_reformat_files` — check_only mode, mock `CommandResult` with `stderr` containing `would reformat src/foo.py`, assert `files_changed == ["src/foo.py"]`
- Add test: `test_run_black_no_files_changed` — clean output, assert `files_changed == []`

---

## Part C: Update `isort_runner.py`

### WHERE
- **Modify**: `src/mcp_tools_py/formatter/isort_runner.py`
- **Modify**: `tests/test_isort_runner.py`

### WHAT
Change `run_isort` return type from `tuple[str, bool]` to `FormatterResult`.
Add `_parse_isort_changed_files()` helper.

```python
def run_isort(
    python_executable: str,
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
) -> FormatterResult:
```

### ALGORITHM — `_parse_isort_changed_files`
```
for each line in combined output:
    if line starts with "Fixing " → extract path, add to list
    if line starts with "ERROR: " and contains " Imports are incorrectly sorted":
        path = line[len("ERROR: "):line.index(" Imports are incorrectly sorted")]
        add path to list
return list
```

isort output examples:
- Normal mode: `Fixing src/foo.py`
- Check mode: `ERROR: src/foo.py Imports are incorrectly sorted and/or formatted.`

### HOW
- Import `FormatterResult` from `formatter.models`
- Replace `return _truncate_output(output), result.return_code == 0` with
  `return FormatterResult(output=..., success=..., files_changed=...)`

### TEST CHANGES (`tests/test_isort_runner.py`)
- Update all existing tests: unpack `result.output` / `result.success` instead of `output, success`
- Add test: `test_run_isort_parses_fixing_files` — stdout contains `Fixing src/foo.py`, assert `files_changed == ["src/foo.py"]`
- Add test: `test_run_isort_parses_check_mode_errors` — check_only, stderr contains `ERROR: src/foo.py Imports are incorrectly sorted`, assert `files_changed == ["src/foo.py"]`
- Add test: `test_run_isort_no_files_changed` — clean output, assert `files_changed == []`

---

## Temporary compatibility note

After this step, `formatter_tools.py` still references `tuple[str, bool]` in
`_STEP_RUNNERS` type hint and unpacks runner results as `output, success`.
This will be updated in Step 2. To keep this step passing, update the
unpacking in `formatter_tools.py` to use `result.output` / `result.success`
and fix the `_STEP_RUNNERS` type annotation. The `test_formatter_tools.py`
fake runners must also return `FormatterResult` instead of tuples.

### Minimal changes in `formatter_tools.py` for compatibility
- Update `_STEP_RUNNERS` type: `dict[str, Callable[..., FormatterResult]]`
- Update loop: `result = runner(...)` then use `result.output`, `result.success`
- Import `FormatterResult`

### Minimal changes in `test_formatter_tools.py` for compatibility
- All fake runners return `FormatterResult(output=..., success=..., files_changed=[])`
  instead of `tuple[str, bool]`

---

## Verification

Run all checks — pytest, pylint, mypy, ruff, lint-imports, vulture must pass.

---

## LLM Prompt

```
You are implementing Step 1 of issue #151 for the mcp-tools-py project.
Read pr_info/steps/summary.md for full context, then pr_info/steps/step_1.md
for this step's details.

Tasks:
1. Create src/mcp_tools_py/formatter/models.py with FormatterResult dataclass
2. Update black_runner.py to return FormatterResult with files_changed parsing
3. Update isort_runner.py to return FormatterResult with files_changed parsing
4. Update formatter_tools.py minimally for compatibility (type hint + unpacking)
5. Update all affected tests (test_black_runner.py, test_isort_runner.py, test_formatter_tools.py)
6. Run all quality checks and fix any issues

Follow TDD: write/update tests first, then implement.
Keep changes minimal — runner.py extraction happens in Step 2.
```
