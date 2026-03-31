# Step 3: Wire up all 3 tools in `checker_tools.py` + update runners + update tests

> **Context**: See `pr_info/steps/summary.md` for full issue context and architecture.

## Goal

Connect everything together: use `resolve_target_directories()` in `checker_tools.py` for pylint, mypy, and vulture. Remove hardcoded fallbacks from pylint/mypy runners. Update vulture to call the new runner module. Update all affected tests.

## WHERE

- `src/mcp_tools_py/checker_tools.py` — add directory resolution for all 3 tools
- `src/mcp_tools_py/code_checker_pylint/runners.py` — remove fallback logic
- `src/mcp_tools_py/code_checker_mypy/runners.py` — remove fallback logic
- `tests/test_checker_tools.py` — update tests for new behavior

## WHAT

### Changes to `checker_tools.py`

**New import** at top:
```python
from mcp_tools_py.code_checker_vulture import run_vulture_check as run_vulture
from mcp_tools_py.utils.project_config import resolve_target_directories
```

**For each of pylint, mypy, vulture** — add at start of tool handler (after availability check):
```python
resolved = resolve_target_directories(str(self._server.project_dir), target_directories)
if isinstance(resolved, str):
    return resolved
```

Then pass `resolved` instead of `target_directories` to the runner.

**For vulture specifically** — replace the inline subprocess logic with a call to:
```python
from mcp_tools_py.code_checker_vulture import run_vulture_check
```

Remove the `execute_command` import if no longer used by any tool in this file (lint-imports still uses it — keep it).

### Changes to `code_checker_pylint/runners.py`

**Remove** the fallback block (lines ~47-50):
```python
# DELETE THIS:
if target_directories is None:
    target_directories = ["src"]
    if os.path.exists(os.path.join(project_dir, "tests")):
        target_directories.append("tests")
```

**Change** parameter type from `Optional[List[str]]` to `List[str]` (remove `Optional` and `None` default).

### Changes to `code_checker_mypy/runners.py`

**Remove** the fallback block (lines ~72-76):
```python
# DELETE THIS:
if target_directories is None:
    target_directories = []
    for default_dir in ["src", "tests"]:
        dir_path = os.path.join(project_dir, default_dir)
        if os.path.exists(dir_path):
            target_directories.append(default_dir)
```

**Change** parameter type from `list[str] | None` to `list[str]` (remove `None` default).

## HOW

### Pylint call chain (after change)
```
checker_tools._register_pylint
  → resolve_target_directories(project_dir, target_directories)
  → get_pylint_prompt(project_dir, ..., target_directories=resolved, ...)
    → get_pylint_results(project_dir, ..., target_directories=resolved)  # always list[str]
```

### Mypy call chain (after change)
```
checker_tools._register_mypy
  → resolve_target_directories(project_dir, target_directories)
  → get_mypy_prompt(project_dir, ..., target_directories=resolved, ...)
    → run_mypy_check(project_dir, ..., target_directories=resolved)  # always list[str]
```

### Vulture call chain (after change)
```
checker_tools._register_vulture
  → resolve_target_directories(project_dir, target_directories)
  → run_vulture_check(binary, project_dir, resolved, ...)  # new runner
```

## Tests to update (in `tests/test_checker_tools.py`)

### Update existing vulture tests
- `test_vulture_success_returns_raw_output` — patch `mcp_tools_py.checker_tools.run_vulture` instead of `execute_command`
- `test_vulture_failure_returns_raw_output` — same patch change
- `test_vulture_whitelist_auto_included` — remove (whitelist is now handled inside the runner, tested in Step 2)
- `test_vulture_default_directories` — replace with auto-detection test (see below)

### Add new auto-detection tests for all 3 tools
For each tool (pylint, mypy, vulture), add two tests:

1. **`test_{tool}_auto_detects_directories`** — patch `resolve_target_directories` to return `["src", "tests"]`, verify the runner receives those dirs
2. **`test_{tool}_resolution_error_returns_message`** — patch `resolve_target_directories` to return an error string, verify the tool returns that string directly

### Intermediate functions
For pylint and mypy, `resolve_target_directories` is patched at `mcp_tools_py.checker_tools.resolve_target_directories`. The resolved dirs flow through `get_pylint_prompt`/`get_mypy_prompt` to the runners.

## Commit

```
refactor: use pyproject.toml auto-detection in checker tools
```

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_3.md for full context.

Implement Step 3: Wire up resolve_target_directories in checker_tools.py for all 3 tools.

1. Update tests/test_checker_tools.py first:
   - Update existing vulture tests to patch the new runner
   - Add auto-detection tests for pylint, mypy, and vulture
   - Add error-returns-message tests for all 3
2. Update src/mcp_tools_py/checker_tools.py:
   - Import resolve_target_directories and run_vulture_check
   - Add resolution logic at start of each tool handler
   - Replace inline vulture logic with runner call
3. Update src/mcp_tools_py/code_checker_pylint/runners.py:
   - Remove fallback block, change target_directories to list[str]
4. Update src/mcp_tools_py/code_checker_mypy/runners.py:
   - Remove fallback block, change target_directories to list[str]
5. Run all three quality checks (pylint, mypy, pytest) and fix any issues
6. Commit with message: "refactor: use pyproject.toml auto-detection in checker tools"

Use MCP tools for all file operations and quality checks per CLAUDE.md.
```
