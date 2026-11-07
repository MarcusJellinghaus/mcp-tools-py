# #58: `run_pytest_check` uses `testpaths` instead of always passing `tests/`

## Goal

Without a path from the caller, the runner always adds `<project>/<test-folder>`, and `--test-folder` defaults to `tests`. A path on the command line makes pytest skip `testpaths`, so pytest and the static checkers can disagree about where the tests are.

Which tests to run, in order:

1. A path in `extra_args`: use it, as today (`skip_default_test_folder=True`).
2. `--test-folder` set explicitly: add it to the command.
3. Non-empty `testpaths` in `pyproject.toml`: expand the entries, including globs, and add those that exist.
4. Otherwise: add `tests`. If `testpaths` was set but no entry exists, the reply carries a note.

## Precondition

**First action, before step 1: rebase this branch onto `origin/main`.** #49 step 1 is met by `origin/main` commit 330d139 (#279): it stops removing a positional `tests`, stops reading option values as paths, and adds the default folder before `extra_args`, which step 2 edits. The rebase also brings in #275, #277, #278 and #280. #280 rewrites `toolkit.py` and `tests/test_toolkit_test.py`, which step 2 edits. The line references in these steps are taken from `origin/main` at 1cdb593. Step 1 checks that the rebase happened.

## Architectural / design changes

- **`test_folder=None` means "resolve".** The value flows through `main.py` → `ToolServer` → `ToolContext` → `check_code_with_pytest` → `run_tests`, and into `start_coverage_run` → `freshness_roots`. Today it is always a string.
- **One new resolver, `resolve_test_paths`, in `utils/project_config.py`.** It covers steps 2 to 4 of the order. Step 1 of the order stays in the runner, which doesn't call the resolver when `skip_default_test_folder` is set.
- **Entries are passed explicitly, never left for pytest to apply.** Adding no path scans the whole tree when every entry is missing, and pytest's warning about that isn't in the reply.
- **The resolver is stateless and may be called more than once per run.** `run_tests` calls it for the paths, `check_code_with_pytest` for the note, and `freshness_roots` for the roots. This keeps `test_folder: str | None` everywhere, at the cost of re-reading `pyproject.toml` and re-globbing, which is cheap.
- **The note is a separate result key, `test_paths_note`, on every return from `check_code_with_pytest`, including the error path.** It stays out of `verdict.problems` because `toolkit.py` matches on the text of those problems.
- **`pyproject.toml` wins over a `pytest.ini` alongside it.** This matches the static checkers and differs from pytest's own precedence.

Layering is unchanged: `code_checker_pytest` already imports from `utils.project_config`.

## Unchanged

- `skip_default_test_folder`.
- `get_test_directories`, still used by `freshness_roots`.
- `--test-folder` in `.mcp.json` and `.mcp.macos.json`.
- Static checkers dropping glob entries, and the other out-of-scope items in the issue.

## Files

**Created**

| File | Step |
|---|---|
| `tests/test_resolve_test_paths.py` | 1 |
| `tests/test_code_checker_pytest/test_test_paths_runner.py` | 2 |
| `tests/test_code_checker_pytest/test_integration_test_paths.py` | 3 |

**Modified**

| File | Step | Change |
|---|---|---|
| `src/mcp_tools_py/utils/project_config.py` | 1 | Add `resolve_test_paths` |
| `src/mcp_tools_py/code_checker_pytest/runners.py` | 2, 3 | Accept `None`, use the resolver, carry the note; flip the default in step 3 |
| `src/mcp_tools_py/code_checker_pytest/coverage_store.py` | 2 | `start_coverage_run` and `freshness_roots` accept `None` |
| `src/mcp_tools_py/checker_tools/pytest_tool.py` | 2 | Show the note |
| `src/mcp_tools_py/toolkit.py` | 2 | Show the note, via `_with_note` |
| `tests/test_code_checker_pytest/test_coverage_store.py` | 2 | `None` roots |
| `tests/test_server_params.py` | 2, 3 | Note in the reply; update the pins at `:647` and `:669` |
| `tests/test_toolkit_test.py` | 2 | Note in the summary |
| `src/mcp_tools_py/main.py` | 3 | Default and help text |
| `src/mcp_tools_py/server.py` | 3 | Defaults and docstrings |
| `src/mcp_tools_py/utils/tool_context.py` | 3 | Default and docstring |
| `tests/test_main_args.py` | 3 | Default is `None` |
| `README.md` | 3 | `--test-folder` row at `:137` |
| `docs/pyproject-configuration.md` | 3 | Fix `:309`; add test selection |
| `docs/architecture/architecture.md` | 3 | `project_config.py` description at `:182` |
| `docs/upgrade-notes.md` | 3 | New entry |

## Steps

1. [Resolver](./step_1.md): adds the function; nothing calls it yet.
2. [Runner and replies](./step_2.md): `None` works everywhere; defaults stay `"tests"`, so callers see no change.
3. [Flip the defaults](./step_3.md): the behaviour change, with docs and end-to-end tests.
