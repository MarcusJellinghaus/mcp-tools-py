# Step 1: Handler rejects a resolved scope that is not a directory

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_1.md`), then implement this step only. Write the test first and confirm it fails, then add the implementation. Run pylint, pytest (`extra_args: ["-n", "auto"]`) and mypy until they all pass, run the formatter, and make one commit.

## WHERE

- `tests/test_library_search.py`, class `TestLibrarySearchTools`
- `src/mcp_tools_py/library_search.py`, the `search_library_files` handler inside `LibrarySearchTools.register`

## WHAT

No signatures change. The handler `search_library_files(scope, glob, pattern, context_lines, max_results, max_result_lines) -> Dict[str, Any]` gains one early return.

New test:

```python
@pytest.mark.parametrize("directory", ["", "no_such_directory_xyz"])
def test_non_directory_scope_returns_error(
    self, tool_context: ToolContext, directory: str
) -> None:
```

## HOW

- `os` is already imported in `library_search.py`, so no new imports are needed.
- The check goes after `assert resolution.directory is not None` and before the `try`.
- The test follows the existing pattern in the class: capture the registered function with `mcp.tool.return_value = _capture`, patch `mcp_tools_py.library_search.resolve_scope` to return `ScopeResolution(directory=directory)`, and patch `mcp_tools_py.library_search.search_in_directory`.
- Do not refactor the repeated `_capture` code in that class.

## ALGORITHM

```
resolution = resolve_scope(interpreter, scope)
if resolution.error is not None: return {"error": resolution.error}
assert resolution.directory is not None
if not os.path.isdir(resolution.directory): return the non-directory error
return search_in_directory(...), as today
```

Use `os.path.isdir`, not `Path(...).is_dir()`: `Path("").is_dir()` is True.

## DATA

The handler returns:

```python
{"error": f"scope '{scope}' resolved to {resolution.directory!r}, which is not a directory"}
```

The test calls `search_library_files("mypy")` and asserts:

- the result equals `{"error": f"scope 'mypy' resolved to {directory!r}, which is not a directory"}`
- `search_in_directory` was not called
