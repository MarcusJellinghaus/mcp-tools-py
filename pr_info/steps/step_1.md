# Step 1: Resolver in `project_config.py`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, then implement this step only. Write the tests first, then the code. Run pylint, pytest (`extra_args=["-n", "auto", "-m", "not integration"]`) and mypy until they pass, format the code, and make exactly one commit.

## Precondition

Rebase onto `origin/main` first, which includes #49 step 1 as 330d139 (#279). After the rebase, check that `src/mcp_tools_py/code_checker_pytest/utils.py` no longer contains `if arg in ("tests", "tests/"):`. If it still does, the rebase didn't happen: write one line to `pr_info/.blocked.txt` saying so and stop.

## WHERE

- `src/mcp_tools_py/utils/project_config.py`, directly after `get_test_directories`
- `tests/test_resolve_test_paths.py` (new; `tests/test_project_config.py` is close to the 750-line limit)

## WHAT

```python
def resolve_test_paths(
    project_dir: str, test_folder: str | None
) -> tuple[list[str], str | None]:
    """Choose the test paths to pass to pytest."""
```

## HOW

- Add `import glob` to `project_config.py`.
- Reuse `_load_pyproject` and `_read_test_dirs`. `_read_test_dirs` appends to its `warnings` argument only when `testpaths` is unset or isn't a list, which tells "unset" from "set".
- A `ValueError` from `_load_pyproject` propagates, as it does for `get_test_directories`; document that in the docstring. An explicit folder never reads the file.
- Nothing calls the function yet.

## ALGORITHM

```python
if test_folder is not None:
    return [test_folder], None
warnings = []
entries = _read_test_dirs(_load_pyproject(project_dir), warnings)
if warnings or not entries:
    return ["tests"], None
paths = [p for e in entries for p in sorted(glob.iglob(e, root_dir=project_dir, recursive=True))]
if paths:
    return paths, None
return ["tests"], f"testpaths entries not found: {entries}; falling back to 'tests'."
```

## DATA

`(paths, note)`:

- `paths`: non-empty list, relative to `project_dir`.
- `note`: `None`, except when `testpaths` is non-empty and no entry exists. The wording must stay true when `tests` is missing too, so it says "falling back", not "ran".

## Tests

One parametrized test, building the project in `tmp_path`. Normalize the returned paths with `Path(p).as_posix()`, because glob returns backslashes on Windows.

| `test_folder` | `pyproject.toml` | Folders | Paths | Note |
|---|---|---|---|---|
| `"checks"` | `testpaths = ["tests"]` | `tests` | `["checks"]` | no |
| `None` | no file | none | `["tests"]` | no |
| `None` | no `testpaths` key | none | `["tests"]` | no |
| `None` | `testpaths = []` | `checks` | `["tests"]` | no |
| `None` | `testpaths = "checks"` | `checks` | `["tests"]` | no |
| `None` | `testpaths = ["checks"]` | `checks`, `tests` | `["checks"]` | no |
| `None` | `testpaths = ["tests", "integration"]` | both | `["tests", "integration"]` | no |
| `None` | `testpaths = ["pkgs/*/tests"]` | `pkgs/b/tests`, `pkgs/a/tests` | `["pkgs/a/tests", "pkgs/b/tests"]` | no |
| `None` | `testpaths = ["**/tests"]` | `pkgs/a/tests` | `["pkgs/a/tests"]` | no |
| `None` | `testpaths = ["nope", "checks"]` | `checks` | `["checks"]` | no |
| `None` | `testpaths = ["nope"]` | `tests` | `["tests"]` | yes |
| `None` | `testpaths = ["nope"]` | none | `["tests"]` | yes |

For the "yes" rows, assert the note names both `nope` and `tests`.

Two separate tests with invalid TOML:

- `test_folder=None` raises `ValueError`.
- `test_folder="checks"` returns `(["checks"], None)`.
