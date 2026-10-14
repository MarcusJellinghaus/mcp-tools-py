# Step 4 — library_search.py: LibrarySearchTools registrar

Part of the plan in `pr_info/steps/summary.md` (issue #228). Read that file first.

This step wires `resolve_scope` (step 2) and `search_in_directory` (step 3) into the
actual MCP tool. It does not touch `server.py` yet — that's step 5.

## Precondition

Steps 2 and 3 are committed: `resolve_scope`/`ScopeResolution` exist in
`environment_info.py` and `search_in_directory` exists in `library_search.py`. If
either is missing, write one line to `pr_info/.blocked.txt` and stop.

## WHERE

- `src/mcp_tools_py/library_search.py` (add to the file from step 3)
- `tests/test_library_search.py` (add to the file from step 3)

## WHAT

- `class LibrarySearchTools`:
  - `__init__(self, context: ToolContext) -> None`
  - `def register(self, mcp: "FastMCPProtocol") -> None`
- Inner registered function:
  `search_library_files(scope: str, glob: Optional[str] = None, pattern: Optional[str] = None, context_lines: int = 0, max_results: int = 50, max_result_lines: int = 200) -> dict[str, Any]`

## HOW

Same shape as `InspectTools`/`_register_get_library_source` in
`inspect_library.py`: `register()` captures `interpreter = str(self._context.environment.interpreter)` once, then defines and decorates the inner function with
`@mcp.tool()` and `@log_function_call` (imported from `mcp_tools_py.log_utils`).
Imports: `ToolContext` from `mcp_tools_py.utils.tool_context`; `resolve_scope` from
`mcp_tools_py.utils.environment_info`; `FastMCPProtocol` under `TYPE_CHECKING`
(as in `inspect_library.py`). The tool must never raise across the MCP boundary —
a bad glob is caught and converted to an error dict, matching the rest of the
server's "never raise" convention (e.g. `run_pytest_check`).

## ALGORITHM

```
def search_library_files(scope, glob=None, pattern=None, context_lines=0,
                          max_results=50, max_result_lines=200):
    resolution = resolve_scope(interpreter, scope)
    if resolution.error is not None:
        return {"error": resolution.error}
    # ScopeResolution guarantees exactly one of directory/error is set, so
    # directory is non-None here; mypy cannot see that from the error check.
    assert resolution.directory is not None
    try:
        return search_in_directory(Path(resolution.directory), glob, pattern,
                                    context_lines, max_results, max_result_lines)
    except ValueError as exc:
        return {"error": str(exc)}
```

## DATA

Returns `dict[str, Any]`: either `{"error": <str>}` (scope resolution failed, or
the glob was unparseable) or the full `search_in_directory` result dict from step 3
(always carrying `scope_root`).

## Tests (write first, see them fail, then implement)

Add a new class to `tests/test_library_search.py`, mirroring
`tests/test_inspect_library.py`'s `TestChildProcess` style — construct a
`ToolContext` (reuse the `tool_context` fixture already used elsewhere in the
suite) and call `LibrarySearchTools(context).register(mcp)` against a
`unittest.mock.MagicMock()` whose `.tool.return_value = lambda fn: fn`, then invoke
the captured `search_library_files` function directly:

- patching `mcp_tools_py.library_search.resolve_scope` to return
  `ScopeResolution(error="boom")`: the tool returns `{"error": "boom"}`; patch
  `search_in_directory` too and assert it was never called.
- patching `resolve_scope` to return a `tmp_path` directory built with a couple of
  `.py` files: the tool's return value for a given `glob`/`pattern` equals calling
  `search_in_directory` directly with the same arguments (proves the wiring, not
  the core logic already covered in step 3).
- an unparseable `glob` (e.g. a negation-only pattern) → `{"error": "..."}`, not a
  raised `ValueError`.
- registration check: `mcp.tool()` is called exactly once, and the registered
  function's `__name__` is `"search_library_files"`.

## Commit

One commit: `feat(library_search): register search_library_files MCP tool`

## LLM prompt

> Read `pr_info/steps/summary.md` for context, then implement
> `pr_info/steps/step_4.md` only. Add the tests described under "Tests" to
> `tests/test_library_search.py` first, confirm they fail (`LibrarySearchTools` does
> not exist yet), then add `LibrarySearchTools` to
> `src/mcp_tools_py/library_search.py` exactly as specified under WHAT/HOW/
> ALGORITHM/DATA, reusing `_collect_files`/`_match_glob`/`_search_content`/
> `search_in_directory` from step 3 unchanged. Do not touch `server.py` in this
> step. Re-run the tests until they pass. Run `mcp__mcp-tools-py__run_pylint_check`,
> `mcp__mcp-tools-py__run_pytest_check` (`extra_args=["-n", "auto", "-m", "not
> integration"]`) and `mcp__mcp-tools-py__run_mypy_check` — all must pass. Then run
> `mcp__mcp-tools-py__run_format_code`, stage the changes, and create exactly one
> commit: `feat(library_search): register search_library_files MCP tool`. If the
> precondition above does not hold, write one line to `pr_info/.blocked.txt` and stop
> instead.
