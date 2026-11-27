# review-implementation review log 1

## Round 1 — 2026-11-27
**Findings**:
Still reviewing: I've read the source diff and am now going through the helpers and tests.src/mcp_tools_py/utils/project_config.py:290 — low — `_read_script_dirs` reads the `[tool.mcp-tools-py]` table with its own loop and a second `isinstance` fallback. This repeats what `read_pyproject_tool_tables` and `_read_mcp_tools_section` already do (DRY). Extract a small helper that takes `toml_data` and returns the section, and use it in both places.
**Decisions**:
Verdict(decision='tasks', tasks=['Extract a helper in src/mcp_tools_py/utils/project_config.py that takes the parsed `toml_data` and returns the `[tool.mcp-tools-py]` table, or an empty dict when it is missing or not a table. Make `_read_script_dirs` (around line 290) and `_read_mcp_tools_section` / `read_pyproject_tool_tables` call it, so the table lookup and its `isinstance` fallback are written once. Keep current behaviour and make sure the existing tests still pass.'], escalate_reason=None)
**Changes**:
applied
