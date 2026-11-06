# Step 1: Arguments

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`. Implement step 1 only, tests first. Run format, pylint, pytest (`-n auto`, `-m "not integration"`, then the new integration file) and mypy until they pass. Produce exactly one commit: `fix(pytest): stop misreading extra_args values as paths (#49)`.

## Precondition

`src/mcp_tools_py/code_checker_pytest/utils.py` still contains `if arg in ("tests", "tests/"):`. If not, write one line to `pr_info/.blocked.txt` and stop.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/utils.py`
- `src/mcp_tools_py/code_checker_pytest/runners.py`
- `tests/test_code_checker_pytest/test_extra_args.py`
- `tests/test_code_checker/test_runners.py`
- `tests/test_code_checker_pytest/test_integration_extra_args.py` (new)

## WHAT

In `utils.py`, private and module-level:

```python
_OPTION_VALUES: dict[str, int]  # option spelling -> most values it can take

def _values_taken(arg: str) -> int: ...
def _positional_args(args: List[str]) -> List[str]: ...
```

`sanitize_extra_args` keeps its signature.

## Table contents

Generated from the installed parser (pytest 9.2.0 with this repo's plugins). Every spelling below takes 1 value, except the two overrides.

```text
-W -c -k -m -n -o -p -r
--anyio-mode --assert --asyncio-mode --basetemp --cache-show --capture
--code-highlight --color --confcutdir --config-file --cov --cov-config
--cov-context --cov-fail-under --cov-precision --cov-report --debug --deselect
--dist --doctest-glob --doctest-report --durations --durations-min --ignore
--ignore-glob --import-mode --json-report-file --json-report-indent
--json-report-verbosity --junit-prefix --junit-xml --junitprefix --junitxml
--last-failed-no-failures --lfnf --log-auto-indent --log-cli-date-format
--log-cli-format --log-cli-level --log-date-format --log-disable --log-file
--log-file-date-format --log-file-format --log-file-level --log-file-mode
--log-format --log-level --max-warnings --max-worker-restart --maxfail
--maxprocesses --maxschedchunk --metadata-from-json --metadata-from-json-file
--numprocesses --override-ini --pastebin --pdbcls --px --pythonwarnings
--report-chars --rootdir --rsyncdir --rsyncignore --show-capture --tach-base
--tach-head --tb --testrunuid --tx --verbosity
```

Overrides: `--metadata` is 2, `--json-report-omit` is `sys.maxsize`.

Build it with `{**dict.fromkeys(_ONE_VALUE_OPTIONS, 1), "--metadata": 2, "--json-report-omit": sys.maxsize}`. Add a short comment saying the table is hard-coded and an option missing from it keeps today's behaviour.

## ALGORITHM

This was run in a scratch probe against the cases listed under Tests, and all passed.

```python
def _values_taken(arg):
    if arg.startswith("--"):
        return 0 if "=" in arg else _OPTION_VALUES.get(arg, 0)
    for pos, letter in enumerate(arg[1:], start=2):
        if f"-{letter}" in _OPTION_VALUES:
            return 0 if arg[pos:] else 1  # -ktests vs -xk tests
    return 0

def _positional_args(args):
    positionals, i = [], 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--":
            positionals += args[i:]
            break
        if not arg.startswith("-"):
            positionals.append(arg)
            continue
        for _ in range(_values_taken(arg)):
            if i == len(args) or args[i].startswith("-"):
                break
            i += 1
    return positionals
```

## HOW

`sanitize_extra_args`:

- Delete the `tests` / `tests/` removal.
- Change the path-detection loop to `for arg in _positional_args(cleaned):` and delete its `if arg.startswith("-"): continue`. The rest of the shape-then-existence logic stays as it is.
- Leave the switch-extraction loop unchanged. It does not look at `--`.
- Update the `Limitations` docstring: option values come from a hard-coded table, a value after an unknown option is read as a positional, and tokens after `--` are positional for path detection.

`run_tests` in `runners.py`:

- Move the `if not skip_default_test_folder: command.append(...)` block above `if extra_args: command.extend(extra_args)`.
- Change "append" to "add" in the `skip_default_test_folder` docstrings of `run_tests` and `check_code_with_pytest`, and in the comment at the moved block.

## DATA

`SanitizedArgs` fields are unchanged. `cleaned_args` now keeps `tests`, and `path_args` / `has_path_args` come from positionals only.

## Tests (write first)

`tests/test_code_checker_pytest/test_extra_args.py`

- Replace `test_tests_path_removed` with a test that `["tests"]` and `["tests/"]` stay in `cleaned_args`.
- `test_combined_deduplication`: expected `cleaned_args` becomes `["tests", "-x"]`.
- Add a parametrized test of `_positional_args`, as `args -> positionals`:

  | args | positionals |
  |---|---|
  | `-k tests --collect-only -q p.py` | `p.py` |
  | `-k tests p.py` | `p.py` |
  | `-k tests`, `-m tests`, `-p tests`, `-xk tests` | none |
  | `-xk tests p.py`, `-ktests p.py`, `-vrs p.py` | `p.py` |
  | `--collect-only --ignore tests p.py` | `p.py` |
  | `tests` | `tests` |
  | `tests/` | `tests/` |
  | `--rootdir .`, `-k src`, `--ignore other`, `--cov src`, `-c pyproject.toml`, `--deselect other/x.py::t` | none |
  | `--cov`, `--debug`, `--cache-show glob`, `--cache-show -x` | none |
  | `--cov src p.py`, `--cov -x p.py`, `--cov=src p.py`, `--debug -x p.py` | `p.py` |
  | `--metadata a b p.py` | `p.py` |
  | `--json-report-omit log` | none |
  | `--json-report-omit log keywords -x p.py`, `--json-report-omit=log p.py` | `p.py` |
  | `--maxfail -1 p.py`, `--maxfail=2 p.py`, `-k "-a b" p.py` | `p.py` |
  | `-n auto p.py`, `-n2 p.py` | `p.py` |
  | `-- tests` | `tests` |
  | `--unknown-option val` | `val` |

- Add `sanitize_extra_args` tests with a temporary `project_dir`:
  - `["-k", "src"]` and `["--rootdir", "."]` with `src/` present: `has_path_args` is False, `notes` is empty, and `cleaned_args` is unchanged.
  - `["--deselect", "missing/x.py::t"]`: no `not found` note.
  - `["tests"]` with `tests/` present: `path_args == ["tests"]`.

`tests/test_code_checker/test_runners.py`

- Add a test beside `test_run_tests_default_test_folder_appended`, using the same mocking: with `extra_args=["--cov"]`, the folder path comes before `--cov` in the command.

`tests/test_code_checker_pytest/test_integration_extra_args.py` (new, `@pytest.mark.integration`)

- Fixture, in the style of `test_integration_show_output.py`: a temporary project with `tests/test_in.py`, `other/test_out.py` and `checks/test_chk.py`, each holding one passing test.
- Helper: call `sanitize_extra_args(args, None, project_dir=...)`, then `run_tests(..., extra_args=sanitized.cleaned_args, skip_default_test_folder=sanitized.has_path_args, timeout_seconds=60)`, and return the report. Tests read nodeids from `report.tests`.
- Parametrize over `["-k", "tests"]`, `["--json-report-omit", "log"]`, `["--cov"]`, `["--debug"]`, `["--ignore", "other"]`, `["--rootdir", "."]`. For each, nodeids are non-empty and all start with `tests/`. Don't pin a count for `-k tests`, because `-k` also matches directory names.
- `["tests"]` with `test_folder="checks"`: nodeids all start with `tests/`.
