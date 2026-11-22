# Step 3 — Coverage selection on `EffectiveConfig`; delete `get_pytest_addopts`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_3.md`), and
> issue #294 (decision 14, Constraints "Coverage history", "The `addopts` line and
> the marker hint live in `run_pytest_check`" — the toolkit exception). Steps 1–2 are
> done. Implement step 3 only: update the tests first, then the code, run the checks
> listed in the summary, then commit (one commit).

## WHERE

- Modified: `src/mcp_tools_py/code_checker_pytest/coverage.py`
- Modified: `src/mcp_tools_py/checker_tools/pytest_tool.py`
- Modified: `src/mcp_tools_py/toolkit.py`
- Modified: `src/mcp_tools_py/utils/project_config.py` (delete `get_pytest_addopts`)
- Modified: `tests/test_code_checker_pytest/test_coverage.py` (`TestSelectionLine`)
- Modified: `tests/test_code_checker_pytest/test_coverage_selection_identity.py`
- Modified: `tests/test_project_config.py` (delete `TestGetPytestAddopts` and its import)
- Modified if they break: `tests/test_toolkit.py`, `tests/test_toolkit_test.py`.
  Either way, each of these two modules gets a module-level autouse fixture that
  removes every `PYTEST*` variable (`monkeypatch.delenv`, same body as step 1's
  `_clear_pytest_env`): the toolkit's `full` depth now reads `PYTEST_ADDOPTS` from
  `os.environ` (issue Constraints, "Tests").

## WHAT

```python
def selection_line(effective: EffectiveConfig, path_args: list[str]) -> str
def selection_identity(
    markers: list[str] | None,
    effective: EffectiveConfig,
    cleaned_args: list[str],
    path_args: list[str],
    env_vars: dict[str, str] | None,
) -> str
```

Deleted: `coverage._effective_option`, `coverage._option_value`,
`project_config.get_pytest_addopts`.

## HOW

- `coverage.py` imports `EffectiveConfig` from `code_checker_pytest.pytest_config`
  (same package, layer contract unchanged).
- `pytest_tool.py`: right after `sanitize_extra_args`, build
  `effective = effective_config(project_dir, markers, sanitized.cleaned_args, env_vars)`
  (always, not only for coverage — step 6 uses it). Pass it to `selection_line` /
  `selection_identity`; drop the `get_pytest_addopts` import and call.
- `toolkit.py` (`full` depth): `effective = effective_config(project_dir, markers, [], None)`;
  `selection_line(effective, [])`, `selection_identity(markers, effective, [], [], None)`.
  Drop the `get_pytest_addopts` import.

## ALGORITHM — `selection_line`

```
parts = []
m = effective.m; if m and m.value: label by source:
    "pyproject.toml"/"-o" -> "addopts -m 'X'"; "PYTEST_ADDOPTS" -> "PYTEST_ADDOPTS -m 'X'"; else "markers 'X'"
k likewise -> "addopts -k 'X'" / "PYTEST_ADDOPTS -k 'X'" / "-k 'X'"; paths -> "paths a, b"
line = "selection: " + "; ".join(parts) or the full-suite line
if effective.not_read: line += f"; pytest config is in {effective.not_read}, not read"
```

`selection_identity`: `m_value` = `" and ".join(sorted(markers))` when
`effective.m.source == "markers"`, else `effective.m.value` (None when no `-m`);
`k_value` = `effective.k.value`. The `rest` / env-hash logic is unchanged, except
`rest` also skips `-m=`/`-k=` forms (already covered by the `startswith` check).
Add `effective.not_read` to the JSON list so a not-read run is its own selection.

## DATA

Unchanged return types (`str`). Old saved coverage runs become a separate selection
on `combine_with_previous` — accepted by the issue.

## Tests (update first)

Build `EffectiveConfig` through `effective_config(str(tmp_path), …)` with a written
`pyproject.toml` (a small helper in each test module), replacing the old
`addopts` string argument. Keep every existing expectation and add:

- list `addopts = ["-m", "not slow"]` → `selection: addopts -m 'not slow'`.
- `[tool.pytest]` `addopts = ["-m", "not slow"]` → same.
- `PYTEST_ADDOPTS="-m fast"` → `selection: PYTEST_ADDOPTS -m 'fast'`.
- `extra_args=["-o", "addopts="]` with addopts `-m slow` → full-suite line.
- `pytest.ini` present → line ends with `; pytest config is in pytest.ini, not read`
  and shows no `pyproject.toml` `-m`; `-c other.ini` → same with `other.ini`.
- `-m=slow` in args → `selection: markers 'slow'`.
- `extra_args=["-m", ""]` with addopts `-m slow` → full-suite line.
- unbalanced quotes in addopts → full-suite line (no raise).
- identity: `-m=slow` equals `-m slow`; addopts list form counts; not-read differs.
- toolkit `full` depth test (existing ones) still passes with the new call.
