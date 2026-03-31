# Step 1: Add `resolve_target_directories()` helper + tests

> **Context**: See `pr_info/steps/summary.md` for full issue context and architecture.

## Goal

Add a shared helper function to `utils/project_config.py` that wraps `get_target_directories()` with logging and error handling. This will be used by all three checker tools in Step 3.

## WHERE

- `tests/test_project_config.py` — add tests (TDD: tests first)
- `src/mcp_tools_py/utils/project_config.py` — add helper function

## WHAT

### Function signature

```python
def resolve_target_directories(
    project_dir: str,
    target_directories: list[str] | None,
) -> list[str] | str:
```

**Returns**: `list[str]` of directories on success, or `str` error message on failure.

## HOW

- Import `logging` (already available in module — add `logger = logging.getLogger(__name__)`)
- No new dependencies needed
- Consumed by `checker_tools.py` in Step 3

## ALGORITHM

```
if target_directories is not None:
    return target_directories  # skip pyproject.toml lookup
try:
    result = get_target_directories(project_dir)
    for warning in result.warnings:
        logger.warning(warning)
    return result.directories
except ValueError as exc:
    return f"Error resolving target directories: {exc}"
```

## DATA

- **Input**: `project_dir: str`, `target_directories: list[str] | None`
- **Output**: `list[str]` (resolved dirs) or `str` (error message)
- Uses existing `TargetDirs` dataclass internally

## Tests to write (in `tests/test_project_config.py`)

Add a new `TestResolveTargetDirectories` class with these tests:

1. **`test_explicit_dirs_returned_as_is`** — when `target_directories=["custom"]`, returns `["custom"]` without calling `get_target_directories`
2. **`test_auto_detects_from_pyproject`** — when `target_directories=None` and valid pyproject.toml exists with `src/` and `tests/` dirs, returns `["src", "tests"]`
3. **`test_logs_fallback_warnings`** — when `target_directories=None` and pyproject.toml has no setuptools section, verify `logger.warning` is called
4. **`test_returns_error_string_on_valueerror`** — when `target_directories=None` and no directories exist on disk, returns a string starting with `"Error resolving target directories:"`

## Commit

```
refactor: add shared resolve_target_directories helper
```

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_1.md for full context.

Implement Step 1: Add resolve_target_directories() helper to utils/project_config.py.

1. First, write the tests in tests/test_project_config.py (new TestResolveTargetDirectories class)
2. Then implement the function in src/mcp_tools_py/utils/project_config.py
3. Run all three quality checks (pylint, mypy, pytest) and fix any issues
4. Commit with message: "refactor: add shared resolve_target_directories helper"

Use MCP tools for all file operations and quality checks per CLAUDE.md.
```
