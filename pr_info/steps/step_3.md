# Step 3: Gitignore-aware file filtering for rope

**Summary**: See `pr_info/steps/summary.md` for full context (Issue #112).

This step parses the project's `.gitignore` using `pathspec` (already a dependency) and
converts the patterns into rope's `ignored_resources` format. This reduces rope's scan
scope and prevents it from parsing irrelevant files.

## WHERE: Files to modify

| File | Action |
|------|--------|
| `tests/test_refactoring/test_rope_tools.py` | Add test for gitignore filtering |
| `src/mcp_tools_py/refactoring/rope_tools.py` | Add `_build_ignored_resources()`, update `_with_rope_project()` |

## WHAT: Functions to add/modify

### New: `rope_tools.py::_build_ignored_resources()`

```python
def _build_ignored_resources(project_dir: Path) -> list[str]:
    """Build rope ignored_resources patterns from .gitignore.

    Falls back to hardcoded defaults if no .gitignore exists.
    """
```

**Signature**: `(project_dir: Path) -> list[str]`
**Returns**: List of glob patterns suitable for rope's `ignored_resources` parameter.

### Modified: `rope_tools.py::_with_rope_project()`

```python
@contextmanager
def _with_rope_project(project_dir: Path) -> Iterator[Project]:
    ignored = _build_ignored_resources(project_dir)
    project = Project(str(project_dir), ropefolder=None, ignored_resources=ignored)
    try:
        yield project
    finally:
        project.close()
```

## HOW: Integration points

- `pathspec` import: `import pathspec` (already in `pyproject.toml` dependencies)
- `_build_ignored_resources()` is called by `_with_rope_project()` — no other callers
- Rope's `ignored_resources` parameter accepts a list of glob pattern strings

## ALGORITHM

```
1. Read .gitignore from project_dir (if exists)
2. Parse patterns with pathspec.PathSpec.from_lines("gitwildmatch", lines)
3. Convert pathspec patterns to rope-compatible glob strings
4. Merge with hardcoded defaults: [".ropeproject", "__pycache__", "*.pyc",
   ".git", "node_modules", ".venv", "venv", ".tox", "build", "dist",
   ".mypy_cache", ".pytest_cache", ".eggs", "*.egg-info"]
5. Deduplicate and return as list[str]
```

### Rope `ignored_resources` format

Rope uses its own glob format. Each pattern in `ignored_resources` is matched against
resource paths relative to the project root. Patterns like `"node_modules"` match
directories named `node_modules` at any level. This is simpler than full gitignore
semantics — we extract directory/file names from gitignore patterns and pass them
as-is where possible.

## DATA

- **Input**: `.gitignore` file contents (optional)
- **Output**: `list[str]` — rope-compatible ignore patterns
- **Hardcoded defaults** (used when no `.gitignore` exists or merged with it):
  ```python
  _DEFAULT_IGNORED = [
      ".ropeproject", "__pycache__", "*.pyc", ".git",
      "node_modules", ".venv", "venv", ".tox",
      "build", "dist", ".mypy_cache", ".pytest_cache",
      ".eggs", "*.egg-info",
  ]
  ```

## Tests (TDD — write first)

1. **Test gitignore patterns applied**: Create a project with a `.gitignore` containing
   `ignoreme/`, create `ignoreme/mod.py` with a symbol. Run a rope operation and verify
   the ignored directory doesn't interfere.

2. **Test defaults without gitignore**: Create a project without `.gitignore`. Verify
   `_build_ignored_resources()` returns the hardcoded defaults.

3. **Test defaults with gitignore**: Create a project with a `.gitignore`. Verify
   `_build_ignored_resources()` returns patterns from `.gitignore` merged with defaults.

## Commit message
```
Add gitignore-aware file filtering for rope to reduce scan scope
```
