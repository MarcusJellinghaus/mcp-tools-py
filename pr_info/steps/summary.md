# Summary — Configurable subprocess timeouts (#219)

## Goal

Two coupled defects, fixed together:

1. **No timeout is reachable from configuration.** Nine programs run at 120s (mypy and
   pylint hardcode it, seven inherit `execute_command`'s default silently), pytest at
   300s. On a large project `run_mypy_check` is unusable.
2. **No checker reports a timeout correctly.** `execute_command` sets `timed_out=True`
   *and* `execution_error` together, so the five checkers that test `execution_error`
   first have dead `timed_out` branches; the five that test neither report a false pass
   (`tach`, `vulture`) or a wrong cause (`lint-imports`, `black`, `isort`).

## Architectural / design changes

### One new configuration surface owned by this server

`[tool.mcp-tools-py]` in the checked project's `pyproject.toml` is the first config
section mcp-tools-py itself owns — until now it only *read* sections owned by other
tools. It carries one shared key and ten per-tool keys:

```toml
[tool.mcp-tools-py]
check-timeout = 300
mypy-timeout = 600
pytest-timeout = 900
```

The CLI carries only `--check-timeout`: one blanket server-level policy, no per-tool
flags that could fight a per-tool pyproject value.

### Resolution chain

```
tool argument  →  [tool.mcp-tools-py] <tool>-timeout  →  [tool.mcp-tools-py] check-timeout
               →  --check-timeout  →  built-in (120, or 300 for pytest)
```

Resolution runs **per call**, not at startup — following the existing
`resolve_target_directories` precedent — so a timeout edit takes effect without a server
restart, at the cost of one TOML parse per tool call.

`--check-timeout` defaults to **`None`**, not 120. A CLI default of 120 would sit above
the built-in in the chain and make pytest's 300s unreachable. This deliberately differs
from the `--refactoring-timeout` precedent (`type=int, default=120`).

### Per-tool keys name programs, not MCP tools

The ten MCP tools and the ten programs are not 1:1. A key bounds **one run of one
program**, so `black-timeout` and `isort-timeout` are separate, ruff has one shared
`ruff-timeout`, and three tool calls can spend more than one budget:
`run_format_code` ≤ `black-timeout + isort-timeout`; `run_ruff_fix` ≤ 2× `ruff-timeout`;
`run_pytest_check` ≤ 2× `pytest-timeout` + the 60s install, when the pytest-json-report
plugin is missing and the run is retried.

### One raising resolver plus a three-line server method

`utils/project_config.py` gains `get_check_timeout(...)`, which **raises `ValueError`**
on a malformed `pyproject.toml` or an invalid value — following the
`get_target_directories` idiom, not the `check_line_length_conflicts` idiom that swallows
`TOMLDecodeError`. A syntactically broken `pyproject.toml` now fails every tool call,
including `run_tach_check` and `run_lint_imports_check`, which read no project config
today.

There is deliberately **no** `int | str` companion wrapper. Nine of the ten registrars
already wrap their work in a `try/except` returning an error message, so calling the
raising function inside those existing blocks already produces the required behaviour —
with no `isinstance` check at any of the 13 call sites. `mypy_tool` is the exception: its
`try` re-raises, so step 8 resolves the timeout ahead of it under a three-line
`except ValueError` that returns the message. Both tools that accept a per-call
`timeout_seconds` therefore report an invalid value the same way — as returned text, not
as an MCP protocol error.

`ToolServer.resolve_timeout(tool, explicit=None)` supplies `project_dir` and
`check_timeout`, so a call site reads `server.resolve_timeout("tach")`, matching the
existing `server._is_tool_available(...)` idiom.

### Key names are derived, not mapped

Every key is `f"{tool}-timeout"`, and the built-in is `300 if tool == "pytest" else 120`.
A `ToolName = Literal[...]` alias gives mypy-strict enforcement of the ten names at every
call site, which a runtime dict would not.

### Runner parameters default to the shared constant

The nine non-pytest runners take `timeout_seconds: int = DEFAULT_CHECK_TIMEOUT`, so the
existing runner tests — which mostly assert only the command list — need no edits. The
registrars always pass a resolved value. pytest's `run_tests` / `check_code_with_pytest`
keep their existing `= 300`; that signature is already correct and already plumbed.

### Layering unchanged

`main.py` keeps a self-contained argparse validator rather than importing the shared one,
so `tach.toml` needs no new `main → utils` edge. `.importlinter` and `tach.toml` are not
modified by this work. `RefactoringTools` stays outside `check-timeout` — it is the only
subprocess-running group that does not receive the server object, and it already has
`--refactoring-timeout`.

### Deliberately excluded subprocesses

The tool-availability probe (`server.py`, 10s, `python -m <tool> --version`) and the
pytest-json-report pip install (`code_checker_pytest/runners.py`, 60s). Neither runs user
code; both stay hardcoded.

### Not a guarantee

The effective limit is `min(server timeout, harness timeout)`. A calling agent's watchdog
can cut a tool call short regardless of this setting.

## Files created

None. No new source or test modules — every change lands in an existing file.

## Files modified

### Core (steps 1–2)

| File | Change |
|------|--------|
| `src/mcp_tools_py/utils/project_config.py` | `ToolName`, `DEFAULT_CHECK_TIMEOUT`, `DEFAULT_PYTEST_TIMEOUT`, `validate_timeout`, `get_check_timeout` |
| `src/mcp_tools_py/main.py` | `--check-timeout` argparse option + validator, passed to `create_server` |
| `src/mcp_tools_py/server.py` | `ToolServer.check_timeout`, `ToolServer.resolve_timeout`, `create_server` parameter |

### Per-program plumbing and timeout reporting (steps 3–11)

| Step | Runner | Registrar |
|------|--------|-----------|
| 3 | `code_checker_tach/runners.py` | `checker_tools/tach_tool.py` |
| 4 | `code_checker_vulture/runners.py` | `checker_tools/vulture_tool.py` |
| 5 | `code_checker_lint_imports/runners.py` | `checker_tools/lint_imports_tool.py` |
| 6 | `code_checker_bandit/runners.py` | `checker_tools/bandit_tool.py` |
| 7 | `code_checker_ruff/runners.py` | `checker_tools/ruff_check_tool.py`, `checker_tools/ruff_fix_tool.py` |
| 8 | `code_checker_mypy/runners.py`, `code_checker_mypy/reporting.py` | `checker_tools/mypy_tool.py` |
| 9 | `code_checker_pylint/runners.py`, `code_checker_pylint/reporting.py` | `checker_tools/pylint_tool.py` |
| 10 | `code_checker_pytest/runners.py` | `checker_tools/pytest_tool.py` |
| 11 | `formatter/black_runner.py`, `formatter/isort_runner.py`, `formatter/runner.py` | `formatter/formatter_tools.py` |

### Tests

`tests/test_project_config.py`, `tests/test_server_params.py`, `tests/test_checker_tools.py`,
`tests/test_formatter_tools.py`, `tests/test_error_transparency.py` (mypy + pylint runner
timeouts), `tests/test_code_checker/test_runners.py`,
`tests/test_code_checker_{tach,vulture,lint_imports,bandit,ruff}/test_runners.py`,
`tests/test_black_runner.py`, `tests/test_isort_runner.py`, `tests/test_formatter_runner.py`.

### Docs (step 12)

`README.md`, `docs/pyproject-configuration.md` (retitled), `docs/architecture/architecture.md`.

## Test rule that applies to every step

`tests/conftest.py::make_command_result` leaves `execution_error=None` by default, so
`make_command_result(timed_out=True)` builds a state `execute_command` never produces —
which is why the existing bandit and ruff `test_timeout` tests pass today against dead
branches. **Every new or updated timeout test must set `timed_out=True` together with a
non-empty `execution_error`.** The two existing tests are corrected in their steps.

## Steps

| # | Step | Commit content |
|---|------|----------------|
| 1 | [step_1.md](step_1.md) | Timeout resolution core in `utils/project_config.py` |
| 2 | [step_2.md](step_2.md) | `--check-timeout` CLI + `ToolServer.resolve_timeout` |
| 3 | [step_3.md](step_3.md) | tach |
| 4 | [step_4.md](step_4.md) | vulture |
| 5 | [step_5.md](step_5.md) | lint-imports |
| 6 | [step_6.md](step_6.md) | bandit |
| 7 | [step_7.md](step_7.md) | ruff (3 invocations) |
| 8 | [step_8.md](step_8.md) | mypy (+ per-call `timeout_seconds`) |
| 9 | [step_9.md](step_9.md) | pylint |
| 10 | [step_10.md](step_10.md) | pytest (+ per-call `timeout_seconds`) |
| 11 | [step_11.md](step_11.md) | black + isort |
| 12 | [step_12.md](step_12.md) | Documentation |

Steps 1 and 2 must land first. Steps 3–11 are independent of each other and may be
reordered. Step 12 is last.

## Definition of done for every step

```
mcp__mcp-tools-py__run_format_code
mcp__mcp-tools-py__run_pylint_check
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto"])
mcp__mcp-tools-py__run_mypy_check
```

All four pass, then exactly one commit.
