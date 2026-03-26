# Decisions

1. **`test_all_tools_available` should have all tools available** — Mock `os.path.exists` to return `True` for the lint-imports binary path (plus set `venv_path` on the server) so the test lives up to its name. Expect `"lint-imports": True`.

2. **Windows binary path needs `.exe` extension** — Use `"lint-imports.exe"` on Windows (`os.name == "nt"`), consistent with the existing `"python.exe"` pattern in `_resolve_python_executable`.

3. **`TestToolHandlerShortCircuit` tests need `"lint-imports"` key** — Existing tests manually set `server._tool_availability` with only 3 keys. Add `"lint-imports": False` to keep the dict consistent.

4. **`mock_server` fixture in `test_checker_tools.py` needs updating** — Add `"lint-imports": True` to the fixture's `_tool_availability` dict and set `server.venv_path` to a mock value so lint-imports tests can resolve a binary path.
