# Step 7 — Docstring, README, architecture doc

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_7.md`), and
> issue #294 (Part 3, decision 16, Acceptance "Docstring"). Steps 1–6 are done.
> Implement step 7 only: add the docstring test first, then the text, run the
> checks listed in the summary, then commit (one commit).

## WHERE

- Modified: `src/mcp_tools_py/checker_tools/pytest_tool.py` (docstring of
  `run_pytest_check`)
- Modified: `README.md` (`run_pytest_check` parameter rows for `markers`,
  `extra_args`, `env_vars`)
- Modified: `docs/architecture/architecture.md` (`code_checker_pytest` and
  `utils/project_config.py` bullets)
- Test: `tests/test_code_checker_pytest/test_config_notes_reply.py` (append)

## WHAT — docstring content

- `markers`: replaces an `-m` from the project's `addopts` (whole expression, not
  added to it); entries are joined with `and`. Check the markers the project
  registers (`markers` in `[tool.pytest.ini_options]` / `[tool.pytest]`) before
  using `-m`; a wrong name is reported on the failure path. Skip integration tests
  the current task doesn't affect, e.g. `markers=["not integration"]`.
- `extra_args`: the project's `addopts` apply first (e.g. `-n auto`), so don't add
  them again. `extra_args=["-o", "addopts="]` runs without them. A later `-m` here
  replaces the `addopts -m`.
- `env_vars`: `PYTEST_ADDOPTS` from the environment also applies;
  `env_vars={"PYTEST_ADDOPTS": ""}` clears it (`-o addopts=` does not).
- Examples section: add `run_pytest_check(markers=["not integration"])` and
  `run_pytest_check(extra_args=["-o", "addopts="])`; keep the existing ones.

Keep the docstring style of the file (Google style, short lines).

## HOW

- README rows say the same points, one cell each (decision 16).
- `architecture.md`: `code_checker_pytest` gains `pytest_config.py` (effective
  pytest config: `pyproject.toml` tables, `PYTEST_ADDOPTS`, call overrides; feeds the
  `addopts` line and the coverage selection) and `marker_hint.py` (marker hint on
  the failure path); remove "the pytest `addopts` accessor" from the
  `utils/project_config.py` bullet.

## ALGORITHM

None.

## DATA

None.

## Tests (write first)

One test reading `run_pytest_check.__doc__` (via the `run_pytest_check` fixture or
the registered function) asserting it contains `'-o", "addopts="'`,
`PYTEST_ADDOPTS": ""`, `replaces`, and `markers` guidance (`registers` or
`registered`).
