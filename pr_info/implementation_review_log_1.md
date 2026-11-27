# review-implementation review log 1

## Round 1 — 2026-11-27
**Findings**:
Still reviewing: I've read the source diff and am now going through the helpers and tests.src/mcp_tools_py/utils/project_config.py:290 — low — `_read_script_dirs` reads the `[tool.mcp-tools-py]` table with its own loop and a second `isinstance` fallback. This repeats what `read_pyproject_tool_tables` and `_read_mcp_tools_section` already do (DRY). Extract a small helper that takes `toml_data` and returns the section, and use it in both places.
**Decisions**:
Verdict(decision='tasks', tasks=['Extract a helper in src/mcp_tools_py/utils/project_config.py that takes the parsed `toml_data` and returns the `[tool.mcp-tools-py]` table, or an empty dict when it is missing or not a table. Make `_read_script_dirs` (around line 290) and `_read_mcp_tools_section` / `read_pyproject_tool_tables` call it, so the table lookup and its `isinstance` fallback are written once. Keep current behaviour and make sure the existing tests still pass.'], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-11-27
**Findings**:
Source and test diffs reviewed; checking the docs diff before reporting.README.md:59 — low — Still says "Only directories that exist on disk are included" without limiting it to source and test folders. A missing `script-directories` folder is an error, not skipped. `docs/pyproject-configuration.md` was corrected for this; the README passage was not.
**Decisions**:
Verdict(decision='tasks', tasks=['In README.md around line 59, limit the sentence "Only directories that exist on disk are included" to the auto-detected source and test folders. Add that a `script-directories` entry pointing to a folder that doesn\'t exist is reported as an error, not skipped. Use the same wording as the corrected passage in docs/pyproject-configuration.md.'], escalate_reason=None)
**Changes**:
applied
