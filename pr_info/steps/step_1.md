# Step 1: Remove dead structlog imports (2 files)

> **Reference:** See `pr_info/steps/summary.md` for full context.

## Goal

Remove unused `import structlog` and `structured_logger = structlog.get_logger(...)` from 2 files that import structlog but never call it.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/reporting.py`
- `src/mcp_tools_py/code_checker_mypy/reporting.py`

## WHAT

No new functions. Remove exactly 2 lines from each file:
```python
# DELETE these lines:
import structlog
structured_logger = structlog.get_logger(__name__)
```

## HOW

1. Remove the `import structlog` line
2. Remove the `structured_logger = structlog.get_logger(__name__)` line
3. No other changes — these variables are never referenced in these files

## VERIFICATION

- Run pylint, pytest (unit), mypy — all must pass
- Grep for `structlog` in both files — should return zero matches

## LLM Prompt

```
Read pr_info/steps/summary.md for context, then implement pr_info/steps/step_1.md.

Remove the dead structlog imports from these 2 files:
- src/mcp_tools_py/code_checker_pytest/reporting.py
- src/mcp_tools_py/code_checker_mypy/reporting.py

Each file has `import structlog` and `structured_logger = structlog.get_logger(__name__)` 
that are never used. Remove both lines from each file. No other changes needed.

After editing, run all three code quality checks (pylint, pytest unit tests, mypy).
Commit with a message like: "chore: remove dead structlog imports from reporting modules"
```
