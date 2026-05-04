# Step 2 — Wire it in, retire old helper, self-register

## LLM Prompt

> Read `pr_info/steps/summary.md` for the design and `pr_info/steps/step_1.md`
> for what already exists. Then implement **this step only**: route the live
> `run_lint_imports_check` MCP tool through the new package, delete the old
> stripper and its tests, and self-register the new package in
> `.importlinter` and `tach.toml`.
>
> The architectural updates (`.importlinter`, `tach.toml`) and the deletion
> of the old helper must land in the same commit as the production wiring,
> otherwise either the import-linter contract breaks (new package not
> declared) or `_strip_lint_imports_header` lingers as dead code.
>
> After implementation, run `mcp__tools-py__run_pylint_check`,
> `mcp__tools-py__run_pytest_check` (with the CLAUDE.md exclusion pattern),
> and `mcp__tools-py__run_mypy_check`. All three must pass before
> committing.

## WHERE — files to modify

- `src/mcp_tools_py/checker_tools.py`
- `tests/test_checker_tools.py`
- `.importlinter`
- `tach.toml`

No new files are created in this step.

## WHAT — changes per file

### `src/mcp_tools_py/checker_tools.py`

1. **Add import** (top of file, alongside other `code_checker_*` imports):

   ```python
   from mcp_tools_py.code_checker_lint_imports import (
       run_lint_imports_check_impl,
   )
   ```

2. **Delete** the helper and its regexes (currently at the top of the file):

   ```python
   _BOX_DRAWING_OR_ARROWS = re.compile(r"[─-╿▶◀▲▼]")
   _ONLY_DASHES = re.compile(r"^-+$")

   def _strip_lint_imports_header(raw: str) -> str:
       ...
   ```

3. **Remove `import re`** if and only if `re` is no longer referenced
   anywhere else in the file (verify with a search before deleting).

4. **Replace `_register_lint_imports` body** with a thin shim:

   ```python
   def _register_lint_imports(self, mcp: "FastMCPProtocol") -> None:
       """Register the lint-imports checker tool."""

       @mcp.tool()
       @log_function_call
       def run_lint_imports_check(
           extra_args: Optional[List[str]] = None,
       ) -> str:
           """
           Run lint-imports on the project to check import contracts.

           Args:
               extra_args: Additional lint-imports arguments.
                   Examples: [\"--contract\", \"layers\"], [\"--verbose\"]

           Returns:
               Structured report. The first non-empty line is the state
               header (PASSED / BROKEN / ERROR), so truncation cannot hide
               failures.
           """
           if not self._server._is_tool_available("lint-imports"):
               binary_path = self._server._lint_imports_binary or "N/A"
               return (
                   f"lint-imports is not available at {binary_path}. "
                   f"Ensure the virtual environment has import-linter "
                   f"installed and --venv-path is configured. Restart "
                   f"the server after installing."
               )

           try:
               binary = self._server._lint_imports_binary
               assert binary is not None
               return run_lint_imports_check_impl(
                   binary,
                   str(self._server.project_dir),
                   extra_args,
               )
           except Exception as e:
               error_msg = (
                   f"Unexpected error running lint-imports: "
                   f"{type(e).__name__}: {e}"
               )
               logger.error(
                   "lint-imports check failed",
                   extra={
                       "error": str(e),
                       "error_type": type(e).__name__,
                       "project_dir": str(self._server.project_dir),
                   },
               )
               return error_msg
   ```

   The pre-call `logger.info("Starting lint-imports check", ...)` and
   post-call `logger.info("lint-imports check completed", ...)` are
   covered by `@log_function_call` on `run_lint_imports_check_impl`
   (which captures parameters, timing, and result) — no need to keep
   manual log calls here.

### `tests/test_checker_tools.py`

1. **Remove the import** of `_strip_lint_imports_header` from line ~10:

   ```python
   from mcp_tools_py.checker_tools import CheckerTools, _strip_lint_imports_header
   ```

   becomes

   ```python
   from mcp_tools_py.checker_tools import CheckerTools
   ```

2. **Delete** the 5 helper tests (currently lines ~227-272):
   `test_strip_lint_imports_header_removes_banner`,
   `_preserves_content_only`,
   `_logo_only_falls_back`,
   `_empty_string_falls_back`,
   `_removes_dash_separators`.

3. **Delete** the 2 obsolete handler tests (currently lines ~166-224):
   `test_lint_imports_success_returns_raw_output`,
   `test_lint_imports_failure_returns_raw_output`.

4. The structured equivalents already exist under
   `tests/test_code_checker_lint_imports/` from step 1; nothing to add here.

5. The `import re` at the top of `tests/test_checker_tools.py` may become
   unused — remove it if so (only kept for the deleted regex assertion).

### `.importlinter`

Two edits:

1. **Append** to the third layer of `[importlinter:contract:layers]`:

   ```
       mcp_tools_py.code_checker_pytest | mcp_tools_py.code_checker_pylint | mcp_tools_py.code_checker_mypy | mcp_tools_py.code_checker_ruff | mcp_tools_py.code_checker_bandit | mcp_tools_py.code_checker_vulture | mcp_tools_py.code_checker_tach | mcp_tools_py.code_checker_lint_imports
   ```

2. **Append** to `forbidden_modules` of `[importlinter:contract:forbidden-imports]`:

   ```
       mcp_tools_py.code_checker_lint_imports
   ```

### `tach.toml`

Two edits:

1. **Add a new module entry** alongside the other `code_checker_*` entries:

   ```toml
   [[modules]]
   path = "mcp_tools_py.code_checker_lint_imports"
   layer = "tool_implementation"
   depends_on = [
       { path = "mcp_tools_py.utils" },
       { path = "mcp_tools_py.log_utils" }
   ]
   ```

2. **Add `code_checker_lint_imports` to `mcp_tools_py.checker_tools.depends_on`**:

   ```toml
   [[modules]]
   path = "mcp_tools_py.checker_tools"
   layer = "tool_implementation"
   depends_on = [
       { path = "mcp_tools_py.code_checker_pytest" },
       ...
       { path = "mcp_tools_py.code_checker_tach" },
       { path = "mcp_tools_py.code_checker_lint_imports" },
       { path = "mcp_tools_py.utils" },
       { path = "mcp_tools_py.log_utils" }
   ]
   ```

## HOW — verification order

1. Apply the four file edits above.
2. Run pytest (with CLAUDE.md exclusion pattern). Expectation:
   - The 7 deleted tests are gone.
   - The new `tests/test_code_checker_lint_imports/` tests still pass.
   - The remaining `test_checker_tools.py` tests still pass.
   - `test_checker_tools_registers_nine_tools` still passes (count
     unchanged — same 9 tools, just one rewired).
3. Run pylint. Expect no new warnings; in particular no
   `unused-import` for `re` in `checker_tools.py` (means the import was
   correctly removed) and no `unused-import` warnings in
   `tests/test_checker_tools.py`.
4. Run mypy. Expect clean.
5. (Optional sanity) Run `mcp__tools-py__run_lint_imports_check_impl`
   indirectly via the CI's `lint-imports` step locally if available —
   confirms the architecture self-registration is correct.

## ALGORITHM — none

Pure plumbing: import switch, body replacement, two config edits, deletions.

## DATA — none

No new data structures. The MCP tool's return type and signature stay the
same string/Optional[List[str]] as before.

## Done When

- `_strip_lint_imports_header` is gone from the source tree.
- The MCP tool `run_lint_imports_check` returns the structured output
  defined in `summary.md`.
- `.importlinter` and `tach.toml` declare the new package.
- All three quality checks pass (pylint, pytest, mypy).
- One commit: `refactor: structured output for run_lint_imports_check (#171)`.
