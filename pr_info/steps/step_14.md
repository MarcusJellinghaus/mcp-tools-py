# Step 14 — Docstring, README and architecture docs

## LLM prompt
Read `pr_info/steps/summary.md` and this file; issue #293 "Docstring", "README" and "Known limits" list the
content. Update the docs; keep wording short. Run pylint, mypy and the non-integration pytest suite (docstring
tests, if any, must stay green). One commit.

## WHERE
- `src/mcp_tools_py/checker_tools/pytest_tool.py` — `run_pytest_check` docstring
- `README.md` — `extra_args` row of the `run_pytest_check` table
- `docs/architecture/architecture.md` — `code_checker_pytest` bullet: `report_data.py`, `report_extras.py`
- `docs/architecture/output-conventions.md` — one sentence: report-level sections share the pytest budget after
  the failure blocks and `-s` output; dropped ones are named in the `Not shown, budget used up:` notice

## WHAT (docstring content, under `extra_args` / an "Output control" block)
- Default: counts plus one hint line; logs inside failing-test blocks.
- `--durations=N` (`0` = all), `--durations-min` (fixed default 0.005 s — deviation), `-rs`, `-rw`, `-ra`/`-rA`
  (include `w` here — deviation; no implicit `w`), unsupported letters get a note, `--disable-warnings`,
  `--show-capture=no|stdout|stderr|log|all` (failing blocks only), `-s` (passing output incl. logs).
- Snapshot workflow: `extra_args=["--snapshot-update"]`, then check `git status` for rewritten baselines.
- `--log-level=INFO`/`DEBUG` records more than WARNING+; `-p no:warnings` empties the warning list.
- Known limits: `-r`/`--durations` from `pytest.ini`/`tox.ini`/`-c` files are not read; unknown plugins' short
  options in combined groups; collect-time warnings repeat per xdist worker; first warning location not
  deterministic under xdist; `-p no:logging` gives no tracebacks in log records; shared-helper module skips differ
  between `-n 0` and `-n N`; other terminal-only flags (`--setup-show`, `--fixtures`, …) show nothing.

## Check
`mcp__mcp-workspace__check_file_size` stays within 750 lines for `pytest_tool.py`.
