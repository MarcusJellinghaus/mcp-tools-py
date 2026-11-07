# Step 3: Flip the defaults to `None`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, then implement this step only. Write the tests first, then the code and docs. Run pylint, pytest (`extra_args=["-n", "auto"]`, including the integration tests) and mypy until they pass, format the code, and make exactly one commit.

## WHERE

- Defaults: `src/mcp_tools_py/main.py:88`, `src/mcp_tools_py/server.py:30` and `:93`, `src/mcp_tools_py/utils/tool_context.py:57`, `src/mcp_tools_py/code_checker_pytest/runners.py:470`
- Tests: `tests/test_code_checker_pytest/test_integration_test_paths.py` (new), `tests/test_server_params.py:647` and `:669`, `tests/test_main_args.py`
- Docs: `README.md:137`, `docs/pyproject-configuration.md:309`, `docs/architecture/architecture.md:182`, `docs/upgrade-notes.md`

## WHAT

```python
# main.py
parser.add_argument("--test-folder", type=str, default=None, help=...)

# server.py: ToolServer.__init__ and create_server
test_folder: Optional[str] = None

# tool_context.py
test_folder: Optional[str] = None

# runners.py: check_code_with_pytest
test_folder: Optional[str] = None
```

## HOW

- **Help text and docstrings:** `main.py:89`, `server.py:42` and `:105`, `tool_context.py:45`, `runners.py:484`. Suggested wording: "Path to the test folder (relative to project_dir). Overrides `testpaths`. Defaults to `[tool.pytest.ini_options] testpaths`, then 'tests'."
- **Pinned tests:** `test_server_params.py:647` (`server.context.test_folder == "tests"`) and `:669` (`call_args[1]["test_folder"] == "tests"`) become `is None`.
- **`tests/test_main_args.py`:** add that `--test-folder` defaults to `None` and that a given value is kept.
- **`README.md:137`:** default `None`, with the same description as the help text.
- **`docs/pyproject-configuration.md:309`:**
  - Replace "(pylint, mypy, vulture)" with the full list: pylint, mypy, ruff, bandit, vulture and `run_format_code`.
  - Add a short section "Which tests `run_pytest_check` runs" with the four-step order from the summary, that `pyproject.toml` wins over a `pytest.ini` alongside it, and what still needs `--test-folder` or a path: no `testpaths` with tests outside `tests/`; `testpaths` only in `pytest.ini`, `tox.ini` or `setup.cfg`; a TOML string value; and `[tool.pytest] testpaths`.
- **`docs/architecture/architecture.md:182`:** add "the pytest test-path resolver" to the `project_config.py` description.
- **`docs/upgrade-notes.md`:** new top entry for #58: projects whose `testpaths` differs from `tests/` now run those folders unless `--test-folder` is set.
- **Leave alone:** the `--test-folder` flag in `.mcp.json` and `.mcp.macos.json`.

## ALGORITHM

Test helper:

```python
write pyproject.toml (if the row has one) and one test module set per folder
patch FastMCP; server = ToolServer(tmp_path, python_executable=sys.executable, test_folder=row.test_folder)
reply = tool "run_pytest_check"(extra_args=row.extra_args)
assert re.search(r"Passed: (\d+)", reply) gives row.passed  (or no match, for usage errors)
assert row.note == ("testpaths entries not found" in reply)
```

## DATA

Each folder holds a different number of tests, so the pass count shows exactly which folders ran. Each test module has a unique file name, because same-named modules without `__init__.py` clash on import in pytest.

| Folder | Tests | Module |
|---|---|---|
| `tests` | 1 | `test_in_tests.py` |
| `checks` | 2 | `test_in_checks.py` |
| `integration` | 4 | `test_in_integration.py` |
| `pkgs/a/tests` | 8 | `test_in_pkg.py` |

## Tests

`test_integration_test_paths.py`: one parametrized test marked `integration`, running real pytest through the real tool on a `tmp_path` project. It has one row per Scenarios row in the issue:

| `testpaths` | Folders | Call | Passed | Note |
|---|---|---|---|---|
| `["tests"]` | `tests` | default | 1 | no |
| not set | `tests` | default | 1 | no |
| `["checks"]` | `checks` | default | 2 | no |
| `["checks"]` | `checks`, `tests` | default | 2 | no |
| `["tests", "integration"]` | both | default | 5 | no |
| `["pkgs/*/tests"]` | `pkgs/a/tests`, `tests` | default | 8 | no |
| `["nope", "checks"]` | `checks` | default | 2 | no |
| `["nope"]` | `tests` | default | 1 | yes |
| `["nope"]` | none | default | usage error | yes |
| `[]` | `tests` | default | 1 | no |
| `["checks"]` | `checks`, `tests` | `extra_args=["tests"]` | 1 | no |
| `["checks"]` | `checks` | `extra_args=["tests"]` | usage error | no |
| `["tests"]` | `tests`, `checks` | `extra_args=["checks"]` | 2 | no |
| `["tests"]` | `tests`, `checks` | `test_folder="checks"` | 2 | no |

Add one test for the toolkit: `PythonToolkit().run(...)` with `testpaths = ["checks"]` and only `checks/` present returns status `ok`, because `_build_context` (`toolkit.py:109`) has no explicit folder and uses the new default.

Add one test for coverage: `run_pytest_check(coverage=True)` with `testpaths = ["nope"]` and `tests/` present doesn't crash on the `None` folder and shows the note. `tests/_coverage_project.py` has a project layout to copy.
