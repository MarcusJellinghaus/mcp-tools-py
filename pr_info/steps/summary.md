# Issue #233 — Console-script tools come from the tool env

## Goal

`tach`, `ruff`, `vulture`, `bandit` and `lint-imports` are hard dependencies of
mcp-tools-py, so they always exist in the environment the server itself runs in.
Today they are looked up only next to `--python-executable`, which in mcp-coder's
two-env setup is the *project* venv — so they read as missing.

After this change the five console scripts are resolved in the **tool env**
(`sys.executable`'s directory). Only checks that must import the project —
pytest, pylint, mypy, black, isort — keep using `--python-executable`.

## Architectural / design changes

**1. `ToolContext` carries two environments instead of one.**

| Field | Interpreter | Used by |
|-------|-------------|---------|
| `environment` | `--python-executable` (project env) | pytest, pylint, mypy, black, isort, jedi/rope, `get_library_source`, the lint-imports locate probe |
| `tool_environment` | `sys.executable` (tool env), not configurable | tach, ruff check, ruff fix, vulture, bandit (step 1), lint-imports (step 3) |

`tool_environment` is a plain field with `default_factory=PythonEnvironment.resolve`.
No CLI flag, no fallback chain: a console script missing from the tool env means
mcp-tools-py's own install is broken, and the message says so.

**2. Availability answers split along the same line.** The console-script branch of
`ToolContext.is_tool_available`, its `unavailable_message` branch, and
`ToolServer._warn_missing_console_scripts` all read `tool_environment`. The
`python -m` branch and its cached probe are untouched.

**3. lint-imports gets a `PYTHONPATH` bridge.** Running the script from the tool env
means the project's root package is no longer on `sys.path` — and for a project that
is *also* installed in the tool env, lint-imports would silently check that stale
copy and report PASSED. So before each run, `code_checker_lint_imports.runners`:

1. reads the root package name(s) from the import-linter config (CLI discovery order,
   `--config` honoured),
2. asks the **project** interpreter where those packages live, via a new stdlib-only
   `probe.py locate` subcommand (`importlib.util.find_spec`), uncached,
3. prepends the resulting directories to `PYTHONPATH` for the subprocess.

Only the root package's parent directory goes on `PYTHONPATH` — never the project
env's whole `sys.path`, which would shadow the tool env's `grimp` (compiled
extension) and `click`.

**4. `probe.py` grows a third subcommand.** It stays standard-library-only, so the
`target-scripts-stdlib-only` contract is unaffected. No new source module is
created anywhere in this change.

## Decisions taken in this plan

- **lint-imports moves to the tool env in step 3, not step 1**, so that the binary
  switch and the `PYTHONPATH` bridge land in the same commit. The tool env's
  lint-imports without the bridge is the stale-copy read this whole change exists to
  prevent; no commit may leave it in that state.
- **Directories outside `--project-dir` are skipped, and the skip is reported.** If
  the project is pip-installed non-editable in its own venv, `find_spec` returns that
  venv's `site-packages`; prepending a whole `site-packages` would put it ahead of the
  tool env's `grimp`, whose compiled extension can then crash on a version or ABI
  mismatch — the one thing the issue rules out explicitly. Skipping is not safe
  either: it leaves lint-imports resolving the package as if there were no bridge
  (*not* today's behaviour, which runs lint-imports from the project env with the
  project's `sys.path` underneath it). So the skipped directory goes into the report
  as an info line above the state header, where a reader can see that a PASSED may
  not be about their working tree.
- **`locate_packages` returns `list[str] | str`** (directories, or the reason it could
  not be asked) — the same idiom as `resolve_target_directories`, rather than a new
  result type.
- **The config reader never raises**: any problem yields no names, which means "run
  lint-imports anyway, without `PYTHONPATH`", exactly as the issue specifies. It does
  distinguish "this file has no import-linter section" from "it has one and names
  nothing", so discovery stops at the file the CLI itself would open.
- **The `tool_context` fixture backs both fields with the same dummy directory**, so
  the existing checker-tool and bandit tests need no rewriting; one new test per
  direction proves the split instead.
- **Version drift is documented, not detected**: a project pinning its own ruff/tach
  now gets the tool env's version.

## Files created or modified

One new test file (step 3); no new source module.

**Source**

| File | Change | Step |
|------|--------|------|
| `src/mcp_tools_py/utils/tool_context.py` | `tool_environment` field; console-script branches of `is_tool_available` and `unavailable_message` | 1 |
| `src/mcp_tools_py/server.py` | `_warn_missing_console_scripts`; `python_executable` docstrings (×2) | 1 |
| `src/mcp_tools_py/main.py` | `--python-executable` help text | 1 |
| `src/mcp_tools_py/checker_tools/tach_tool.py` | binary lookup → `tool_environment` | 1 |
| `src/mcp_tools_py/checker_tools/ruff_check_tool.py` | same | 1 |
| `src/mcp_tools_py/checker_tools/ruff_fix_tool.py` | same | 1 |
| `src/mcp_tools_py/checker_tools/vulture_tool.py` | same | 1 |
| `src/mcp_tools_py/checker_tools/bandit_tool.py` | same | 1 |
| `src/mcp_tools_py/checker_tools/lint_imports_tool.py` | binary lookup → `tool_environment`, + passes the project interpreter | 3 |
| `src/mcp_tools_py/utils/target_scripts/probe.py` | `locate` subcommand, `_USAGE`, `main` | 2 |
| `src/mcp_tools_py/utils/environment_info.py` | `locate_packages()` | 2 |
| `src/mcp_tools_py/code_checker_lint_imports/runners.py` | config reading, `PYTHONPATH`, locate-failure ERROR | 3 |

**Configuration and docs**

| File | Change | Step |
|------|--------|------|
| `.importlinter` | drop the dead `root_package_paths = src` | 3 |
| `README.md` | parameter table (`:115`), Environment Configuration (`:145-197`), Troubleshooting (`:203-204`) | 4 |
| `docs/architecture/architecture.md` | §5 `probe.py` and `ToolContext` bullets, §7 two-env description | 4 |

**Tests**

| File | Change | Step |
|------|--------|------|
| `tests/conftest.py` | `tool_context` fixture sets both environments | 1 |
| `tests/test_tool_context.py` | `_context` helper, message assertions, split coverage | 1 |
| `tests/test_tool_availability/_helpers.py` | `_patched_tool_env` context manager | 1 |
| `tests/test_tool_availability/test_handler_short_circuit.py` | lint-imports message test; new split test | 1 |
| `tests/test_server_params.py` | `TestStartupConsoleScriptWarnings` | 1 |
| `tests/test_checker_tools.py` | `_remove_console_script`, tach assertion, lint-imports kwargs | 1, 3 |
| `tests/test_environment_info.py` | `TestLocatePackages`, real-subprocess `locate` test | 2 |
| `tests/test_code_checker_lint_imports/test_runners.py` | config discovery, `PYTHONPATH`, ERROR path | 3 |
| `tests/test_code_checker_lint_imports/test_bridge_integration.py` | new; real lint-imports against a src-layout project, nothing patched | 3 |

`tests/test_code_checker_bandit/test_integration.py` is listed in the issue but needs
no change: the fixture keeps `environment.binary("bandit")` and
`tool_environment.binary("bandit")` pointing at the same file.

## Steps

1. `step_1.md` — tach, ruff, vulture and bandit resolve in the tool environment
2. `step_2.md` — `probe.py locate` and `locate_packages()`
3. `step_3.md` — lint-imports moves to the tool env with its `PYTHONPATH` bridge
4. `step_4.md` — documentation

Each step is one commit: tests, implementation, and `run_format_code` +
`run_pylint_check` + `run_pytest_check` + `run_mypy_check` all passing.
