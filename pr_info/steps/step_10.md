# Step 10 — User docs: `docs/user-config.md`, README, upgrade notes, architecture overview

## LLM prompt
Read `pr_info/steps/summary.md`, then implement **this step only** (`pr_info/steps/step_10.md`).
This step is documentation only, so there are no tests. Write the docs from issue #298 and the implemented behaviour in `src/mcp_tools_py/code_checker_pytest/workers.py`; read that file first, so the docs match the code exactly.
Run `run_format_code`, pylint, pytest (`markers=["not integration"]`) and mypy (unchanged code, so they should pass); make one commit.

## WHERE
- Create `docs/user-config.md`
- Modify `docs/README.md` (Configuration section)
- Modify `README.md` (the note at ~line 80: "The tool never adds `-n` ...")
- Modify `docs/upgrade-notes.md` (new entry at the top, newest first)
- Modify `docs/architecture/architecture.md` (Module Overview, `code_checker_pytest` bullet)

## WHAT
`docs/user-config.md` sections:
1. **Where:** `~/.mcp_coder/config.toml`, section `[mcp_tools_py]`. It is distinct from the project section `[tool.mcp-tools-py]` in `pyproject.toml`. It is read on every pytest run, so no restart is needed.
2. **`pytest_workers`:** values `"auto"` (default) / `"all"` / integer ≥ 0 (`0` = serial), with the Windows / other-OS table from the issue. Strict types: `"4"` is invalid. Integers are not capped.
3. **Scope:** only defines what `-n auto` / `-n logical` means (from `addopts`, `PYTEST_ADDOPTS` or `extra_args`). A numeric `-n N` is never changed, and with no `-n` nothing is added. The count reaches xdist via `PYTEST_XDIST_AUTO_NUM_WORKERS`.
4. **Resolution order:** the four steps from the issue, including the pre-set `PYTEST_XDIST_AUTO_NUM_WORKERS` rules (non-empty only, caller's `env_vars` win, non-integer → xdist default).
5. **Formula:** `n = floor(0.5 × logical cores × (1 − CPU load))`, serial when `n < 2`. Include the 24-logical table. Sampling: median of 5 × 100 ms via `GetSystemTimes`, Windows only, about 0.5 s per run. Small machines: 4 logical cores are serial above 0 % load, 8 above 50 %, 12 above 66.7 %.
6. **Reporting:** the visibility rule and the `workers:` line examples. A count of 0 is shown as `serial`.
7. **Invalid values / files:** a missing file is silent. An invalid value, unreadable file or invalid TOML → log warning + `ignored …` on the `workers:` line + `warning` verify item; falls back to `auto`.
8. **Verify:** the `pytest_workers` item of `PythonToolkit.verify()` for `None` / `"test"`.
9. **Timeouts:** if a load-sized serial run hits the 300 s default `timeout_seconds`, raise `timeout_seconds`, set `pytest_workers`, or pass a numeric `-n`.
10. **Known limitations:**
    - A `-n auto` in `pytest.ini`, `.pytest.ini`, `pytest.toml`, `.pytest.toml`, `tox.ini`, `setup.cfg` or a `-c` file is not seen. A caller's `-n auto` is still sized.
    - The line shows the requested count when a project `pytest_xdist_auto_num_workers` hook, `--maxprocesses` or `--pdb` decides otherwise.

## HOW
- `docs/README.md`, under Configuration: add `- **[User Configuration](user-config.md)** — `[mcp_tools_py]` in `~/.mcp_coder/config.toml`: `pytest_workers`, how `-n auto` is sized`.
- `README.md` note: append "The worker count of `-n auto` follows `[mcp_tools_py] pytest_workers` in `~/.mcp_coder/config.toml` ([docs/user-config.md](docs/user-config.md)); `-n auto` in `extra_args` does not bypass it, a numeric `-n N` does."
- `docs/upgrade-notes.md`: new top entry `## run_pytest_check sizes -n auto by CPU load on Windows (#298)`: default `-n auto` on Windows is now load-sized; there is a new `workers:` line on runs with `-n auto`; set `pytest_workers = "all"` for the old behaviour. Followed by `---`.
- `docs/architecture/architecture.md`, `code_checker_pytest` bullet: add "`workers.py` sizes `-n auto` from `[mcp_tools_py] pytest_workers` in the user config (`~/.mcp_coder/config.toml`), sampling CPU load on Windows, and passes the count via `PYTEST_XDIST_AUTO_NUM_WORKERS`."

## DATA
None.
