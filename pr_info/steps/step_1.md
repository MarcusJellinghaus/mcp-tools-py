# Step 1: Harden `_with_rope_project()` — disable cache + gitignore filtering

**Summary**: See `pr_info/steps/summary.md` for full context (Issue #112).

Disable rope's persistent cache and add gitignore-aware file filtering to reduce
rope's scan scope. Merges the cache-disable and gitignore-filtering fixes into one step.

## WHERE: Files to modify

| File | Action |
|------|--------|
| `pyproject.toml` | Add `igittigitt` dependency + mypy override for `igittigitt` |
| `src/mcp_tools_py/refactoring/rope_tools.py` | Set `ropefolder=None`, add gitignore filtering |
| `tests/test_refactoring/test_rope_tools.py` | Add tests for cache disable + gitignore filtering |

## WHAT: Functions to add/modify

### Modified: `rope_tools.py::_with_rope_project()`

```python
@contextmanager
def _with_rope_project(project_dir: Path) -> Iterator[Project]:
    """Context manager: open fresh rope Project, yield, close."""
    ignored = _build_ignored_resources(project_dir)
    project = Project(str(project_dir), ropefolder=None, ignored_resources=ignored)
    try:
        yield project
    finally:
        project.close()
```

Key changes:
- `ropefolder=None` disables persistent `.ropeproject/` cache
- `ignored_resources` from gitignore filtering reduces scan scope

### New: `rope_tools.py::_build_ignored_resources()`

```python
def _build_ignored_resources(project_dir: Path) -> list[str]:
    """Build rope ignored_resources from .gitignore + hardcoded defaults."""
```

### New: `rope_tools.py::read_gitignore_rules()` and `apply_gitignore_filter()`

Copy ONE-TO-ONE from `p_workspace` reference project
(`src/mcp_workspace/file_tools/directory_utils.py`). These functions use `igittigitt`
(NOT `pathspec`).

Add comment at top of copied section:
```python
# Gitignore utilities copied from p_workspace (directory_utils.py).
# TODO: Refactor into shared mcp_utils package later.
```

Both functions are copied as a unit for consistency with p_workspace, even though
`_build_ignored_resources()` primarily uses the matcher from `read_gitignore_rules()`.

**`read_gitignore_rules()`** — reads `.gitignore`, returns `(matcher_fn, content)` tuple
using `igittigitt.IgnoreParser`.

**`apply_gitignore_filter()`** — filters file paths using the matcher function.

### Strategy: gitignore → rope `ignored_resources`

Rope's `ignored_resources` accepts glob patterns matched against resource paths relative
to project root. The approach:
1. Use `read_gitignore_rules()` to get a matcher from `.gitignore`
2. Walk project files, apply matcher to get ignored paths
3. Convert ignored directory names to rope glob patterns
4. Merge with hardcoded defaults, deduplicate

## ALGORITHM

```
_build_ignored_resources(project_dir):
  1. Start with hardcoded defaults:
     [".ropeproject", "__pycache__", "*.pyc", ".git",
      "node_modules", ".venv", "venv", ".tox",
      "build", "dist", ".mypy_cache", ".pytest_cache",
      ".eggs", "*.egg-info"]
  2. Read .gitignore via read_gitignore_rules()
  3. If matcher exists, scan top-level dirs and files:
     - For each entry in project_dir, check if matcher says ignore
     - Add ignored names to the pattern list
  4. Deduplicate and return as list[str]
```

## DATA

- **Hardcoded defaults**:
  ```python
  _DEFAULT_IGNORED = [
      ".ropeproject", "__pycache__", "*.pyc", ".git",
      "node_modules", ".venv", "venv", ".tox",
      "build", "dist", ".mypy_cache", ".pytest_cache",
      ".eggs", "*.egg-info",
  ]
  ```
- **New dependency**: `igittigitt` in `pyproject.toml`
- **Existing dependency**: `pathspec` remains in `pyproject.toml` (used by other project tooling)
- `ropefolder=None`: rope `Project` constructor parameter (`Optional[str]`)

## Tests (TDD — write first)

1. **Test no `.ropeproject/` created**: After `rename_symbol`, assert no `.ropeproject/`
   directory exists.
   ```python
   def test_rope_does_not_create_ropeproject_folder(sample_project: Path) -> None:
       rename_symbol(sample_project, "src/foo.py", "my_func", "better_name")
       assert not (sample_project / ".ropeproject").exists()
   ```

2. **Test defaults without gitignore**: Create project without `.gitignore`. Verify
   `_build_ignored_resources()` returns the hardcoded defaults.

3. **Test gitignore patterns applied**: Create project with `.gitignore` containing
   `ignoreme/`. Verify `_build_ignored_resources()` includes `ignoreme` in output.

4. **Test existing tests still pass**: All existing tests must pass with the new
   `ropefolder=None` and `ignored_resources` changes.

## Commit message
```
Disable .ropeproject cache and add gitignore-aware filtering for rope
```
