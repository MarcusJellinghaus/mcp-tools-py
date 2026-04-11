# Issue #149: Add Bandit Security Linter Tool

## Overview

Add [bandit](https://bandit.readthedocs.io/) as a new MCP checker tool following the **rich checker pattern** (structured JSON parsing, LLM-optimized reporting).

Bandit is a Python security linter that finds common security issues (hardcoded passwords, SQL injection, insecure deserialization, etc.).

## Architecture & Design Changes

### New Module: `src/mcp_tools_py/code_checker_bandit/`

Mirrors the ruff module structure with 4 files + `__init__.py`:

| File | Responsibility | Pattern Reference |
|------|---------------|-------------------|
| `models.py` | `BanditMessage` NamedTuple + `BanditResult` container | pylint/mypy `*Result` pattern |
| `parsers.py` | Parse `bandit --format json` output → `BanditMessage` list | ruff `parse_ruff_json_output` |
| `reporting.py` | Group by test_id, sort by severity/confidence, format LLM report | ruff `format_ruff_check_report` |
| `runners.py` | Build command, execute subprocess, return `BanditResult` | pylint `get_pylint_results` |
| `__init__.py` | Re-export public API | all checkers |

### Key Design Decisions

1. **`BanditResult` container** (not direct string return) — for testability, error handling separation, and consistency with pylint/mypy. The runner returns `BanditResult`; `checker_tools.py` formats it into the final string.

2. **Binary file check** (not `python -m`) — Bandit doesn't support `python -m bandit`, so availability is detected via binary file check in venv (same as ruff/vulture).

3. **Sorting: `(severity, confidence, -frequency)`** — Unlike ruff (prefix-based), bandit IDs are all `B1xx`–`B7xx`. Severity HIGH > MEDIUM > LOW is the meaningful ranking dimension; confidence breaks ties.

4. **File-level errors** — Bandit reports file-level errors (e.g., syntax errors) in a separate top-level `errors` array. These are surfaced at the top of the report to avoid silently hiding unscanned files.

5. **CWE references** — Detailed findings include CWE ID + link (high-value security context).

6. **No config passing** — Bandit auto-discovers `pyproject.toml` and `.bandit` since v1.7.5.

### Data Flow

```
bandit CLI (JSON) → parsers.py → BanditMessage list + errors
                                         ↓
                                   runners.py → BanditResult
                                         ↓
                              checker_tools.py → reporting.py → formatted string → MCP tool response
```

### Integration Points

- **`server.py`**: Add bandit binary detection in `_check_tool_availability()` (same block as ruff/vulture)
- **`checker_tools.py`**: Add `_register_bandit()` method, call from `register()`
- **`tach.toml`**: Add `code_checker_bandit` module with dependencies on `utils` and `log_utils`; add to `checker_tools` depends_on
- **`.importlinter`**: Add `code_checker_bandit` to the layers contract
- **`pyproject.toml`**: Add `bandit>=1.7.0` to `[project.dependencies]`

### MCP Tool Signature

```python
def run_bandit_check(
    target_directories: Optional[List[str]] = None,  # auto-detected from pyproject.toml
    extra_args: Optional[List[str]] = None,           # additional bandit CLI flags
    max_issues: int = 1,                              # detail vs summary control
) -> str:
```

## Files Created

| File | Purpose |
|------|---------|
| `src/mcp_tools_py/code_checker_bandit/__init__.py` | Package exports |
| `src/mcp_tools_py/code_checker_bandit/models.py` | Data models |
| `src/mcp_tools_py/code_checker_bandit/parsers.py` | JSON parsing |
| `src/mcp_tools_py/code_checker_bandit/reporting.py` | LLM report formatting |
| `src/mcp_tools_py/code_checker_bandit/runners.py` | Subprocess execution |
| `tests/test_code_checker_bandit/__init__.py` | Test package |
| `tests/test_code_checker_bandit/test_parsers.py` | Parser tests |
| `tests/test_code_checker_bandit/test_reporting.py` | Reporting tests |
| `tests/test_code_checker_bandit/test_runners.py` | Runner tests |

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Add `bandit>=1.7.0` dependency |
| `src/mcp_tools_py/server.py` | Add bandit binary detection |
| `src/mcp_tools_py/checker_tools.py` | Add `_register_bandit()` + import |
| `tach.toml` | Add `code_checker_bandit` module boundaries |
| `.importlinter` | Add `code_checker_bandit` to layers contract |

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | Models + dependency (`BanditMessage`, `BanditResult`, `pyproject.toml`) | `feat(bandit): add data models and dependency` |
| 2 | Parser + tests (JSON parsing into `BanditMessage` list) | `feat(bandit): add JSON parser with tests` |
| 3 | Reporting + tests (grouping, sorting, LLM formatting) | `feat(bandit): add LLM-optimized reporting with tests` |
| 4 | Runner + tests (command building, subprocess, `BanditResult`) | `feat(bandit): add subprocess runner with tests` |
| 5 | Server + checker_tools integration (binary check, MCP tool registration) | `feat(bandit): register run_bandit_check MCP tool` |
| 6 | Architecture boundaries (`tach.toml`, `.importlinter`) | `chore(bandit): add architecture boundary config` |
