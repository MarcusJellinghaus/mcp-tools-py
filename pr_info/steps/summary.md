# Summary — `[tool.mcp-tools-py] script-directories` (issue #308)

## Goal

Without `target_directories`, the formatter, ruff check, ruff fix, pylint and mypy
also cover the folders listed in `[tool.mcp-tools-py] script-directories`, in the
MCP tools and in the toolkit (`format` action; `check` runners for ruff, pylint and
mypy). vulture and bandit validate the key but add no scripts. deptry, coverage and
pytest never read it. An explicit `target_directories` is used as given and the key
is not read.

```toml
[tool.mcp-tools-py]
script-directories = ["tools"]
```

| Kind | Declared in | formatter, ruff check / fix | pylint, mypy | vulture, bandit | deptry, coverage | pytest |
|---|---|---|---|---|---|---|
| Source | `[tool.setuptools.packages.find] where` | ✓ | ✓ | ✓ | ✓ | – |
| Tests | `[tool.pytest.ini_options] testpaths` | ✓ | ✓ | ✓ | – | ✓ |
| Scripts | `[tool.mcp-tools-py] script-directories` | ✓ | ✓ | – | – | – |

## Architectural / design changes

- **One resolver, one new parameter.** `resolve_target_directories(project_dir,
  target_directories, tool)` in `utils/project_config.py` gains a required `tool:
  TargetTool`, where `TargetTool = Literal["formatter", "ruff", "pylint", "mypy",
  "vulture", "bandit"]`. It's a narrow Literal, not `ToolName`, so `"pytest"`,
  `"tach"` and others can't be passed. Every call site passes its tool; both ruff
  tools pass `"ruff"`. All formatter steps share `"formatter"`, so
  `formatter.runner.run_format_code` keeps a single `target_dirs` list.
- **The resolver no longer calls `get_target_directories`.** It reads
  `pyproject.toml` once with `_load_pyproject`, gets source and test folders from
  `_read_source_dirs` / `_read_test_dirs` on that data, keeps those that exist on
  disk, then reads the scripts from the same data. `get_target_directories` and
  `TargetDirs` (public exports) stay unchanged.
- **One new private validator**, `_read_script_dirs(toml_data, project_dir,
  auto_dirs) -> list[str]`, in `project_config.py`. It raises `ValueError` on the
  first bad entry. The resolver catches every `ValueError` and returns it as a
  `str` with the existing prefix `Error resolving target directories: `. It never
  raises, because `PythonToolkit.run` would not catch the exception.
- **Path comparison is purely lexical.** Each folder gets a key,
  `PurePath(os.path.normcase(entry)).parts`. Two folders overlap when either key is
  a prefix of the other. `normcase` makes the comparison case- and
  separator-insensitive on Windows. On POSIX a backslash stays part of the name.
  Keys use no `resolve()` or `abspath`. The empty key of `.` (flat layout)
  therefore contains every script folder without special-casing.
- **Order** is source, tests, scripts. Nothing is deduplicated, because every equal
  pair is already an error.
- **No new modules.** The validation adds about 60 lines to `project_config.py`
  (491 lines today). `toolkit.py` is at 749 lines, so its edit stays a one-line
  change.

## Behaviour of `resolve_target_directories`

1. `target_directories is not None` → return it unchanged. `pyproject.toml` is not
   read, so even an invalid key is ignored.
2. Read `pyproject.toml`. Get source and test folders and keep those on disk
   (`existing`). Log fallback warnings as today.
3. Validate `script-directories` for **every** tool value. A missing key or `[]`
   gives `[]`.
4. `dirs = existing + (scripts if tool in _SCRIPT_TOOLS else [])`, where
   `_SCRIPT_TOOLS = {"formatter", "ruff", "pylint", "mypy"}`.
5. Empty `dirs` → `Error resolving target directories: No target directories
   found: [<source + test entries>]`. Existing script folders alone are enough.

## Error messages

Every message is `Error resolving target directories: [tool.mcp-tools-py]
script-directories: <detail>`:

| Condition (checked in this order, first failure wins) | `<detail>` |
|---|---|
| value not a `list`, or an entry not a `str` | `must be a list of folder names, got {value!r}` |
| `p.drive or p.root or ".." in p.parts or not p.parts` with `p = PurePath(entry)` (covers absolute, `/tools`, `\tools`, `C:tools`, `..`, `""`, `.`, `./`) | `entry {entry!r} must be a folder inside the project, relative to its root` |
| `not os.path.isdir(os.path.join(project_dir, entry))` (missing, or a file) | `folder {entry!r} not found` |
| overlaps an earlier script entry (equal, inside, containing) | `folders {earlier!r} and {entry!r} overlap` |
| overlaps an existing source or test folder | `folder {entry!r} overlaps source/test folder {auto!r}`, plus `; {auto!r} already covers it` when `auto` contains `entry` |

An invalid `pyproject.toml` keeps today's text: `Error resolving target
directories: Invalid pyproject.toml: …`.

## Files

### Modified

| File | Change |
|---|---|
| `src/mcp_tools_py/utils/project_config.py` | `TargetTool`, `_SCRIPT_TOOLS`, `tool` parameter, `_read_script_dirs`, resolver rewrite |
| `src/mcp_tools_py/formatter/formatter_tools.py` | pass `"formatter"`; docstring |
| `src/mcp_tools_py/checker_tools/ruff_check_tool.py` | pass `"ruff"`; docstring |
| `src/mcp_tools_py/checker_tools/ruff_fix_tool.py` | pass `"ruff"`; docstring |
| `src/mcp_tools_py/checker_tools/pylint_tool.py` | pass `"pylint"`; docstring |
| `src/mcp_tools_py/checker_tools/mypy_tool.py` | pass `"mypy"`; docstring |
| `src/mcp_tools_py/checker_tools/vulture_tool.py` | pass `"vulture"`; docstring |
| `src/mcp_tools_py/checker_tools/bandit_tool.py` | pass `"bandit"`; docstring |
| `src/mcp_tools_py/toolkit.py` | `_run_format` passes `"formatter"` (one-line edit) |
| `src/mcp_tools_py/toolkit_checks.py` | `_run_mypy` / `_run_pylint` / `_run_vulture` / `_run_ruff` / `_run_bandit` pass their tool |
| `tests/test_project_config.py` | existing `resolve_target_directories` calls get the `tool` argument |
| `tests/test_formatter_tools.py` | two pinned `assert_called_once_with` get `"formatter"` |
| `docs/pyproject-configuration.md` | new `script-directories` section; auto-detection section updated |
| `docs/README.md` | index text lists `script-directories` |
| `docs/architecture/architecture.md` | `project_config.py` description; "single reader" claim corrected |
| `README.md` | auto-detection section and `target_directories` table rows |

### Created

| File | Content |
|---|---|
| `tests/test_target_directories_call_sites.py` | each MCP tool and toolkit runner passes the right `tool` and returns the resolver's error |
| `tests/test_script_directories.py` | resolver behaviour for `script-directories`, plus one toolkit `check@full` test |

## Steps

1. [step_1.md](step_1.md): add the `tool` parameter and pass it at every call site
   (no behaviour change).
2. [step_2.md](step_2.md): implement `script-directories` in the resolver.
3. [step_3.md](step_3.md): docs and MCP tool docstrings.
