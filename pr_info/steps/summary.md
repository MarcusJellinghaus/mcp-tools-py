# Summary — Prepare PythonToolkit's depths and fix prompts for implement (#276)

mcp_coder#1389 binds `check@standard` and `test@quick` by default in
`implement_final`. This change makes both depths safe to run there and gives
mcp-coder a test-fix prompt. Nothing changes in mcp-coder-utils.

## Architectural / design changes

| Area | Before | After |
|---|---|---|
| Project environment | `_build_context` always resolves `sys.executable`. | `_build_context` resolves `VIRTUAL_ENV` when it's set and non-empty, else `sys.executable`. A `VIRTUAL_ENV` with no interpreter raises `FileNotFoundError` naming `VIRTUAL_ENV`. `run` turns it into an `error` result and `verify` into one `error` item named `environment`. There is no fallback. `tool_environment` doesn't change. |
| Name Resolution rule | "never through `VIRTUAL_ENV`" | The toolkit's context is the documented exception. |
| Check timeouts | Every checker's default is 120 s (`DEFAULT_CHECK_TIMEOUT`). | `_run_check` sets `check_timeout=600` on the context for every check depth, the same mechanism #272 uses for test depths. `[tool.mcp-tools-py]` `<tool>-timeout` / `check-timeout` still win. At `check@full` the other tools (vulture, ruff, bandit and so on) also get 600 s by default; that only lengthens how long a hung tool runs before it's reported. |
| `test@quick` selection | Fixed `-m "not integration"`. That misses `*_integration` markers and gives a usage error under `--strict-markers` when `integration` isn't registered. | Excludes every **registered** marker whose name ends in `integration`, read from `python -m pytest --markers --color=no` in the project env. No match → no marker filter. A failed read (non-zero exit, timeout, run error, or exit 0 with no `@pytest.mark.` lines) → `error`; it never runs unfiltered. No `-o strict_markers=false`, because only registered names are passed. |
| Prompt fragments | `fix.check` is mypy-only. There is no test-fix fragment. | `fix.check` covers findings from any checker. A new `fix.test` fragment says to fix the failing tests named in the output and re-run only those. |

Design choices (KISS):
- The marker read is one private function in `toolkit.py`, not a new module.
  The parser is a single `re.findall`.
- The marker command is plain: `cwd=project_dir`, no `--rootdir` and no PATH
  tweaks. Pytest finds the config and top-level `conftest.py` from the
  working directory.
- The marker read reuses `context.resolve_timeout("pytest")`, so there's no
  new setting.
- `PythonEnvironment.resolve` doesn't change. `_build_context` only rewraps
  its `FileNotFoundError` with a `VIRTUAL_ENV` message.

## Files

Modified:
- `src/mcp_tools_py/toolkit.py`: prompts, `fix.test`, `_build_context`,
  `run`/`verify` guards, `_registered_markers`, `test@quick` markers.
- `src/mcp_tools_py/toolkit_checks.py`: `_LONG_CHECK_TIMEOUT` in `_run_check`.
- `docs/architecture/architecture.md`: "Name Resolution".
- `tests/test_toolkit.py`: prompt fragment tests.
- `tests/test_toolkit_check.py`: timeout tests.
- `tests/test_toolkit_verify.py`: stale `VIRTUAL_ENV` item.

Created:
- `tests/test_toolkit_environment.py`: `VIRTUAL_ENV` set, unset and stale for `run`.
- `tests/test_toolkit_markers.py`: marker read, parsing, and the real strict-marker run.

## Steps

1. `step_1.md`: reword `fix.check`, add `fix.test`.
2. `step_2.md`: 600 s default timeout for check depths.
3. `step_3.md`: project environment from `VIRTUAL_ENV`, plus the docs update.
4. `step_4.md`: `test@quick` excludes registered `*integration` markers.

Every step: run pylint, pytest (`-n auto`) and mypy until they pass; run
`run_format_code`; one commit.
