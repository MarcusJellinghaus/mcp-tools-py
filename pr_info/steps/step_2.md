# Step 2: Disable `.ropeproject/` persistent cache

**Summary**: See `pr_info/steps/summary.md` for full context (Issue #112).

This step disables rope's persistent `.ropeproject/` cache folder by setting
`ropefolder=None` in the `Project()` constructor. One-shot MCP operations don't
benefit from persistent caching, and stale cache can cause hangs.

## WHERE: Files to modify

| File | Action |
|------|--------|
| `tests/test_refactoring/test_rope_tools.py` | Add test verifying no `.ropeproject/` created |
| `src/mcp_tools_py/refactoring/rope_tools.py` | Set `ropefolder=None` in `_with_rope_project()` |

## WHAT: Function to modify

### `rope_tools.py::_with_rope_project()`

**Current**:
```python
project = Project(str(project_dir))
```

**After**:
```python
project = Project(str(project_dir), ropefolder=None)
```

## HOW: Integration points

- No new integration — single parameter change in existing context manager
- All three public functions (`move_symbol`, `rename_symbol`, `move_module`) already use
  `_with_rope_project()`, so they all benefit automatically

## ALGORITHM

```
1. _with_rope_project() passes ropefolder=None to rope.base.project.Project
2. Rope operates entirely in-memory with no disk cache
3. No stale cache reconciliation can occur
4. Context manager close() still called for cleanup
```

## DATA

- No new data structures or return types
- `ropefolder=None` is a rope `Project` constructor parameter (type: `Optional[str]`)

## Tests (TDD — write first)

1. **Test no ropeproject created**: After running `rename_symbol` (or any rope operation),
   assert that no `.ropeproject/` directory exists in the project directory.
   ```python
   def test_rope_does_not_create_ropeproject_folder(sample_project: Path) -> None:
       rename_symbol(sample_project, "src/foo.py", "my_func", "better_name")
       assert not (sample_project / ".ropeproject").exists()
   ```

## Commit message
```
Disable .ropeproject/ persistent cache to prevent stale-cache hangs
```
