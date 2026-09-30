# Step 8 — Mypy `max_issues` tool parameter and docs

## LLM prompt

Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_8.md`) only.
Tests first. Run pylint, pytest (`-n auto`), mypy; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/checker_tools/mypy_tool.py` — `run_mypy_check`
- `tests/test_checker_tools.py`
- `README.md`, `docs/architecture/architecture.md`, `tests/mcp_tools_py_manual/TEST_PLAN.md`

## WHAT

```python
def run_mypy_check(
    disable_error_codes: list[str] | None = None,
    target_directories: list[str] | None = None,
    follow_imports: str | None = None,
    cache_dir: str | None = None,
    timeout_seconds: int | None = None,
    max_issues: int | None = None,
) -> str: ...
```

## HOW

Forward `max_issues=max_issues` to `get_mypy_prompt`; add it to the "Starting mypy check" log extras.

Docstring:
```
max_issues: Number of error codes shown in detail (5 locations each).
    None (default) details every code. 0 = counts only: one line per code
    with count and directory split, no file paths. Remaining codes get one
    summary line each.
```

## Docs

- `README.md` Pylint Parameters table, `max_issues` row: add "`0` = counts only (per-rule count and
  directory split)".
- `docs/architecture/architecture.md` utils list: add a bullet for `utils/report_counts.py` — shared
  per-rule report helpers (directory split, total line, plural) for the ruff, pylint, bandit and mypy
  reports.
- `TEST_PLAN.md`: add cases for `max_issues=0` on ruff/pylint/bandit/mypy (total line, per-rule count
  and split, no paths) and `run_mypy_check(max_issues=1)`.

## Tests (`tests/test_checker_tools.py`)

- `max_issues=2` reaches `get_mypy_prompt` (`call_args[1]["max_issues"] == 2`).
- Default reaches it as `None`.
