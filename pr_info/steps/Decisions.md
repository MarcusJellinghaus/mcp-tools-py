# Decisions

1. **`test_all_tools_available` should have all tools available** — Mock `os.path.exists` to return `True` for the lint-imports binary path (plus set `venv_path` on the server) so the test lives up to its name. Expect `"lint-imports": True`.

2. **Windows binary path needs `.exe` extension** — Use `"lint-imports.exe"` on Windows (`os.name == "nt"`), consistent with the existing `"python.exe"` pattern in `_resolve_python_executable`.

3. **`TestToolHandlerShortCircuit` tests need `"lint-imports"` key** — Existing tests manually set `server._tool_availability` with only 3 keys. Add `"lint-imports": False` to keep the dict consistent.

4. **`mock_server` fixture in `test_checker_tools.py` needs updating** — Add `"lint-imports": True` to the fixture's `_tool_availability` dict and set `server.venv_path` to a mock value so lint-imports tests can resolve a binary path.

5. **Store resolved `_lint_imports_binary` on server (DRY)** — Follow the existing `_resolved_python` pattern: resolve the binary path once in `server.py` and store as `self._lint_imports_binary: Optional[str]`. `checker_tools.py` reads it directly instead of re-resolving with `os.name`/`os.path.join` logic.

6. **`test_all_tools_available` setup must be explicit** — The test needs `venv_path="/mock/venv"` on the server and `os.path.exists` mocked to return `True` for both the python executable and the lint-imports binary. This is a setup change, not just an assertion change.

7. **Include binary path in short-circuit error message** — For consistency with existing pylint/pytest/mypy short-circuit messages (which include the resolved python path), the lint-imports unavailability message includes the expected binary path.

8. **Mock target for `execute_command` in step 2 tests** — Since `checker_tools.py` imports `execute_command` directly, mock target must be `mcp_tools_py.checker_tools.execute_command`.
