# Step 3: Add `check_line_length_conflicts` + wire into MCP wrapper

> **Context**: See [summary.md](summary.md) for architecture overview and full file list.

## Objective

Add a function that compares line-length settings across black, isort, and ruff
in `pyproject.toml`. Called by the MCP wrapper before formatting. Returns
non-blocking warnings only.

## Commit message

```
feat(formatter): add line-length conflict pre-check
```

---

## Part A: Add `check_line_length_conflicts` in `utils/project_config.py`

### WHERE
- **Modify**: `src/mcp_tools_py/utils/project_config.py`
- **Modify**: `tests/test_project_config.py`

### WHAT
```python
def check_line_length_conflicts(
    project_dir: str,
    used_tools: list[str],
) -> list[str]:
```

### ALGORITHM
```
load pyproject.toml (reuse existing pattern from get_target_directories)
for tool in ["black", "isort", "ruff"]:
    read [tool.{name}].line-length (isort uses line_length)
    if configured → store value
    elif tool in used_tools → store default 88
    else → store None (skip)
filter out None entries
if all remaining values are equal → return []
else → return list of warning strings describing mismatches
```

### DATA
- **Input**: `project_dir` (str), `used_tools` (list[str]) — e.g. `["isort", "black"]`
- **Output**: `list[str]` — warning messages, empty if no conflicts
- **Config paths**:
  - `[tool.black].line-length` (int)
  - `[tool.isort].line_length` (int, note underscore)
  - `[tool.ruff].line-length` (int)  
  - Also check `[tool.ruff.format].line-length` as override
- **Default**: 88 for all three tools (only applied when tool is in `used_tools`)

### HOW
- Pure function, no formatter imports (import-linter clean)
- Reuses the existing `tomllib.load` / `os.path.join` pattern already in this file
- Returns warnings like: `"Line-length mismatch: black=88, isort=120. Formatting may be inconsistent."`

### TESTS (`tests/test_project_config.py`) — new class `TestCheckLineLengthConflicts`
- `test_all_match_no_warnings` — black=88, isort=88, ruff=88 → `[]`
- `test_mismatch_returns_warning` — black=88, isort=120 → warning string
- `test_unconfigured_unused_tool_skipped` — ruff not configured, not in `used_tools` → no warning about ruff
- `test_unconfigured_used_tool_defaults_to_88` — isort not configured but in `used_tools` → treated as 88, compared
- `test_no_pyproject_no_warnings` — no file at all → `[]`
- `test_only_one_tool_configured_no_comparison` — only black=88, nothing else → `[]`

---

## Part B: Wire into MCP wrapper

### WHERE
- **Modify**: `src/mcp_tools_py/formatter/formatter_tools.py`

### WHAT
Call `check_line_length_conflicts` before invoking `run_format_code`.
Prepend any warnings to the output string.

### ALGORITHM
```
# after resolving dirs, before calling run_format_code:
warnings = check_line_length_conflicts(str(self._server.project_dir), resolved_steps)
# after formatting results to string:
if warnings:
    prepend "\n".join(warnings) + "\n\n" to output
return output
```

### HOW
- Import `check_line_length_conflicts` from `utils.project_config`
- `resolved_steps` serves as `used_tools` — the steps being run are the tools in use
- Warnings are informational only, never block execution

### TEST ADDITIONS (`tests/test_formatter_tools.py`)
- `test_line_length_warnings_prepended` — mock `check_line_length_conflicts` returning
  `["Line-length mismatch: ..."]`, verify it appears in output before `## isort`
- `test_no_line_length_warnings` — mock returning `[]`, verify no extra text

---

## Verification

Run all checks — pytest, pylint, mypy, ruff, lint-imports, vulture must pass.

---

## LLM Prompt

```
You are implementing Step 3 of issue #151 for the mcp-tools-py project.
Read pr_info/steps/summary.md for full context, then pr_info/steps/step_3.md
for this step's details.

Tasks:
1. Add check_line_length_conflicts() to src/mcp_tools_py/utils/project_config.py
2. Write tests first in tests/test_project_config.py (TDD)
3. Wire the check into formatter_tools.py MCP wrapper
4. Add tests for the wiring in test_formatter_tools.py
5. Run all quality checks and fix any issues

The function lives in utils/ and has no formatter imports.
It's called by the MCP wrapper with the resolved steps as used_tools.
Warnings are non-blocking — prepended to output, never stop execution.
```
