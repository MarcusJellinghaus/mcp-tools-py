# Step 12 — Documentation

Docs only. No source or test changes.

## WHERE

- `README.md` — §Optional Parameters → *Tool Configuration* table
- `docs/pyproject-configuration.md` — retitle + new section
- `docs/architecture/architecture.md` — §5 module overview line, plus metadata

## WHAT — `README.md`

Three tables change.

1. §Optional Parameters → *Tool Configuration* — one new row:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--check-timeout` | integer | None (120; pytest 300) | Timeout in seconds for every checker and formatter subprocess. Overridden per tool by `[tool.mcp-tools-py]` in the project's `pyproject.toml` |

The issue also asks to backfill `--refactoring-timeout` and `--vulture-whitelist`.
**Both are already present** in that table (added in #226) — verify and leave them alone.

2. §*Pytest Parameters* — this table enumerates every `run_pytest_check` argument, so
   step 10's new one belongs in it:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout_seconds` | integer | None (resolved from config, else 300) | Maximum seconds to wait for the test run. Positive integers only |

3. §*Mypy Parameters* — same, for step 8's argument:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout_seconds` | integer | None (resolved from config, else 120) | Maximum seconds to wait for mypy. Positive integers only |

These two tables are the only per-tool argument documentation in the README; leaving
them out would ship a documented tool surface that is missing an argument it accepts.

## WHAT — `docs/pyproject-configuration.md`

1. **Retitle.** The file is called *"Pylint Configuration via `pyproject.toml`"* but
   already covers more than pylint (it has a *Target directory auto-detection* section).
   Retitle to *"Project Configuration via `pyproject.toml`"* and adjust the opening so the
   pylint material reads as one section among several.

2. **New section: `[tool.mcp-tools-py]` — subprocess timeouts.** This is the first config
   section mcp-tools-py itself owns; every other section the file describes is owned by
   another tool. Cover, in this order:

   - Example:
     ```toml
     [tool.mcp-tools-py]
     check-timeout = 300
     mypy-timeout = 600
     pytest-timeout = 900
     ```
   - The full precedence chain:
     `tool argument → <tool>-timeout → check-timeout → --check-timeout → built-in`
   - Built-ins: 120 seconds, 300 for pytest. Configuration is opt-in.
   - The ten per-tool keys: `mypy-timeout`, `pylint-timeout`, `pytest-timeout`,
     `ruff-timeout`, `bandit-timeout`, `vulture-timeout`, `tach-timeout`,
     `lint-imports-timeout`, `black-timeout`, `isort-timeout`.
   - **Keys name programs, not MCP tools.** A key bounds one run of one program, so a
     single tool call can spend more than one budget:
     `run_format_code` up to `black-timeout + isort-timeout`;
     `run_ruff_fix` up to 2× `ruff-timeout` (a pre-check call, then the apply call);
     `run_pytest_check` up to 2× `pytest-timeout` plus a 60s install, when the
     pytest-json-report plugin is missing and the run is retried.
   - **Positive integers only.** `0` and negatives are rejected with a clear error;
     `0 = disabled` is deliberately not supported, because an unbounded subprocess in an
     MCP server is an unrecoverable hang — nothing else will reap it and the tool call
     simply never returns. A large value approximates "never".
   - **Per-call overrides.** `run_mypy_check` and `run_pytest_check` accept
     `timeout_seconds`; the other tools do not.
   - **`--check-timeout` is server-wide.** The CLI carries only the shared setting; there
     are no per-tool CLI flags.
   - **A malformed `pyproject.toml` now fails every tool call**, including
     `run_tach_check` and `run_lint_imports_check`, which read no project config before
     this change.
   - **Name collision note.** `pytest-timeout` is also the name of a well-known PyPI
     plugin. There is no actual TOML clash — that plugin reads
     `[tool.pytest.ini_options] timeout` — but the similarity is worth knowing.
   - **Not a guarantee.** The effective limit is `min(server timeout, harness timeout)`:
     a calling agent's watchdog can cut a tool call short regardless of this setting.
   - Unknown keys in the section are ignored.

## WHAT — `docs/architecture/architecture.md`

- §5 module overview: the `utils/project_config.py` bullet currently reads
  *"target-directory auto-detection from `pyproject.toml`"*. Extend it to cover timeout
  resolution from `[tool.mcp-tools-py]`.
- Update the `Version` and `Last Updated` metadata at the top.
- Do not restructure anything else; `tach.toml` and `.importlinter` are unchanged by this
  work, so the enforcement sections stay as they are.

## DATA

None — prose and tables only.

## VERIFICATION

No tests to write. Still run the full check set before committing: `run_format_code`
(docs changes must not leave the tree unformatted), `run_pylint_check`,
`run_pytest_check(extra_args=["-n","auto"])` and `run_mypy_check`.

Cross-check the ten key names in the docs against `ToolName` in
`src/mcp_tools_py/utils/project_config.py` — every key must be exactly
`f"{tool}-timeout"`.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_12.md`. Implement step 12 only.
>
> Update `README.md` (one new `--check-timeout` row in *Tool Configuration*, plus a
> `timeout_seconds` row in each of the *Pytest Parameters* and *Mypy Parameters* tables;
> confirm `--refactoring-timeout` and
> `--vulture-whitelist` are already there and leave them), retitle and extend
> `docs/pyproject-configuration.md` with the `[tool.mcp-tools-py]` section covering every
> bullet listed in this step, and extend the `utils/project_config.py` line in
> `docs/architecture/architecture.md` §5 with a metadata bump.
>
> Docs only — no source or test changes. Keep it concise: shorter is better. Then run the
> four checks and commit once.
