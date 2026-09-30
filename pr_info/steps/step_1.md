# Step 1 — Read-only `addopts` accessor

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_1.md`).
> Implement only this step, TDD: write the tests first, then the code. Run
> pylint, pytest (`-n auto`), mypy and `run_format_code`; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/utils/project_config.py`
- `tests/test_project_config.py`

## WHAT

```python
def get_pytest_addopts(project_dir: str) -> str | None:
    """Return `[tool.pytest.ini_options] addopts` from pyproject.toml, or None."""
```

Decision 12: parse and expose the string, nothing more. No flag interpretation.

## HOW

- Private helper `_load_pyproject(project_dir) -> dict[str, object]` that returns
  `{}` when the file is missing and raises `ValueError("Invalid pyproject.toml: …")`
  on bad TOML — the same behaviour as the existing inline loads. Use it here;
  step 2 reuses it. Do not refactor the other existing readers.
- Walk `tool` → `pytest` → `ini_options` → `addopts` with `isinstance(..., dict)`
  checks (as `check_line_length_conflicts` does).

## ALGORITHM

```
data = _load_pyproject(project_dir)
value = data["tool"]["pytest"]["ini_options"].get("addopts")  # dict-guarded
if isinstance(value, str): return value
if isinstance(value, list): return " ".join(str(v) for v in value)
return None
```

## DATA

`"-n auto -m 'not slow'"` / `None`.

## Tests (`tests/test_project_config.py`)

- string `addopts` returned verbatim
- list `addopts` joined with spaces
- no pyproject / no section / no key → `None`
- invalid TOML → `ValueError`
