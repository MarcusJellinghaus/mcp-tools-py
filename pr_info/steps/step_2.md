# Step 2 — `script-directories` in `resolve_target_directories`

Read [summary.md](summary.md) first, especially "Behaviour" and "Error messages".

Precondition: `resolve_target_directories` in `src/mcp_tools_py/utils/project_config.py`
has a `tool` parameter and every call site passes it (Step 1). If not, write one
line to `pr_info/.blocked.txt` and stop.

## LLM prompt

> Implement Step 2 of `pr_info/steps/summary.md` as described in
> `pr_info/steps/step_2.md`. TDD: first write `tests/test_script_directories.py`,
> run it and see it fail, then implement `_read_script_dirs` and the new
> `resolve_target_directories` body in `src/mcp_tools_py/utils/project_config.py`.
> Run `run_format_code`, then pylint, pytest (`markers=["not integration"]`) and
> mypy; all must pass. Produce exactly one commit.

## WHERE

- `src/mcp_tools_py/utils/project_config.py`: the only source file changed.
- New `tests/test_script_directories.py`.

## WHAT

```python
_SCRIPT_DIRS_KEY = "script-directories"
_SCRIPT_TOOLS: frozenset[TargetTool] = frozenset({"formatter", "ruff", "pylint", "mypy"})

def _path_key(entry: str) -> tuple[str, ...]:
    """Lexical comparison key: case- and separator-insensitive where the OS is."""
    return PurePath(os.path.normcase(entry)).parts

def _overlaps(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    return a[: len(b)] == b or b[: len(a)] == a

def _read_script_dirs(
    toml_data: dict[str, object], project_dir: str, auto_dirs: list[str]
) -> list[str]:
    """Validated, normalised `[tool.mcp-tools-py] script-directories` entries.

    Raises:
        ValueError: on the first invalid entry; the message starts with the key.
    """

def resolve_target_directories(project_dir, target_directories, tool) -> list[str] | str:
    ...  # remove Step 1's `del tool`
```

`PurePath` comes from `pathlib`, which is already imported (add `PurePath` to the
import). Use `_CONFIG_SECTION` for the table name. The label is
`f"[tool.{_CONFIG_SECTION}] {_SCRIPT_DIRS_KEY}"`.

## ALGORITHM

`_read_script_dirs`:

```
section = toml_data["tool"]["mcp-tools-py"] (each level: missing or not a dict -> {}); value = section.get(key, [])
if not list or any entry not str: raise "must be a list of folder names, got {value!r}"
for entry: p = PurePath(entry); if p.drive or p.root or ".." in p.parts or not p.parts: raise "entry ... must be a folder inside the project, relative to its root"
           if not isdir(join(project_dir, entry)): raise "folder {entry!r} not found"
           if overlaps an earlier entry's key: raise "folders {earlier!r} and {entry!r} overlap"
           for auto in auto_dirs: if overlaps: raise "folder {entry!r} overlaps source/test folder {auto!r}" + ("; {auto!r} already covers it" if auto key is prefix of entry key)
return [PurePath(e).as_posix() for e in entries]
```

`resolve_target_directories`:

```
if target_directories is not None: return target_directories
try: data = _load_pyproject(...); warnings = []; auto = _read_source_dirs(data, warnings) + _read_test_dirs(data, warnings)
     existing = [d for d in auto if isdir(join(project_dir, d))]; scripts = _read_script_dirs(data, project_dir, existing)
except ValueError as exc: return f"Error resolving target directories: {exc}"
log each warning; dirs = existing + (scripts if tool in _SCRIPT_TOOLS else [])
return dirs or f"Error resolving target directories: No target directories found: {auto}"
```

Update the resolver docstring with this lookup order. `get_target_directories`
stays unchanged.

## DATA

- `_read_script_dirs` → `list[str]` of POSIX-form entries (`./tools/` → `tools`).
  A missing key or `[]` → `[]`.
- `resolve_target_directories` → `list[str]` in the order source, tests, scripts,
  or a `str` error.

## Tests (`tests/test_script_directories.py`)

Helper: `_project(tmp_path, extra_toml="", dirs=("src", "tests"), where=("src",),
testpaths=("tests",))`. It writes a `pyproject.toml` with `where = [...]` and
`testpaths = [...]` from its arguments, plus `extra_toml` (which must not redefine
`[tool.pytest.ini_options]` or `[tool.setuptools.packages.find]`), and creates the
given folders plus `tools/`. `ALL_TOOLS` is the six `TargetTool`
values and `PREFIX = "Error resolving target directories: [tool.mcp-tools-py]
script-directories: "`.

1. A missing key and `script-directories = []` → `["src", "tests"]` for every tool.
2. `["tools"]` → `["src", "tests", "tools"]` for formatter, ruff, pylint and mypy;
   `["src", "tests"]` for vulture and bandit.
3. `["./tools/"]` → the last entry is `"tools"`.
4. Invalid values, parametrised × `ALL_TOOLS`. The result is a `str` starting with
   `PREFIX`:
   - `"tools"` (a string), `[1]`
   - `[""]`, `["."]`, `["./"]`, `["/tools"]`, `["<abs>/tools"]`, `[".."]`,
     `["tools/.."]`, `["../x"]`. `<abs>/tools` is a placeholder: the test body
     replaces it with `str(tmp_path / "tools")`, because `tmp_path` doesn't exist
     when tests are collected.
   - `["tool"]` (missing; the message contains `folder 'tool' not found`)
   - `["file.py"]` (create it as a file)
   - `["tools", "tools/sub"]`, `["tools", "./tools"]` (create `tools/sub`)
   - `["src"]`, `["src/pkg"]` (create `src/pkg`)
5. Containing a test folder: `_project(..., testpaths=["tools/tests"])` with
   `tools/tests` on disk, and `["tools"]` → error.
6. Flat layout: `_project(..., where=["."])` and `["tools"]` → error containing
   `'.' already covers it`.
7. An auto-detected folder that is not on disk is not an overlap:
   `_project(..., testpaths=["tools/tests"])` without the folder, and `["tools"]`
   → OK.
8. Scripts alone: no `src` or `tests` on disk, and `["tools"]`. mypy gives
   `["tools"]`; vulture gives an error containing `No target directories found`.
9. An explicit list wins: `script-directories = "tools"` and
   `resolve_target_directories(path, ["x"], "mypy") == ["x"]`.
10. Invalid TOML → a `str` containing `Invalid pyproject.toml`.
11. Other resolvers ignore the key, even an invalid one (`script-directories =
    "tools"`): `resolve_source_directories(path, None) == ["src"]`,
    `resolve_coverage_source(path, None) == ["src"]`, and
    `resolve_test_paths(path, None)[0] == ["tests"]`.
12. Windows only (`pytest.mark.skipif(os.name != "nt", ...)`):
    - `["C:tools"]`, `["\\tools"]` → error.
    - `["tools\\"]` → `"tools"`.
    - `["SRC"]` → overlap error.
    - `["tools", "Tools"]` → overlap error.
13. Toolkit `check@full` with `script-directories = "tools"` and `src/mod.py`.
    Monkeypatch `mcp_tools_py.toolkit_checks.run_lint_imports_check_impl` (returns
    `"=== PASSED ===\nContracts: 0 kept, 0 broken"`), `run_tach_check` (returns
    `TachResult(None, 0, [], None)`) and `run_deptry_check_impl` (returns
    `DeptryResult(return_code=0, messages=[])`). Then call
    `PythonToolkit().run(ActionRequest(action="check", depth="full",
    project_dir=tmp_path, params={}))`. Assert `status == "error"` and
    `summary.count("[tool.mcp-tools-py] script-directories") == 5` (mypy, pylint,
    vulture, ruff, bandit).
