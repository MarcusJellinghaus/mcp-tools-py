# review-implementation review log 1

## Round 1 — 2026-09-02
**Findings**:
I'll gather context first — knowledge base, issue, plan files, and the diff.All checks pass on the branch (pytest 643 passed/1 skipped, mypy clean, pylint clean, ruff clean, vulture clean). The diff contains real implementation changes, so the review proceeds.

`src/mcp_tools_py/server.py:157` — medium — the eager startup warning hand-rolls a second message template instead of calling `tool_unavailable_message`, and for `lint-imports` it tells the user to install `lint-imports`, which is not a distribution; the helper's `package="import-linter"` override exists precisely to avoid that misdiagnosis (step_4 calls it out as the one case the templates must not flatten). It also diverges in wording from the message the handler returns, which the README troubleshooting entry quotes as "ruff is not available".
`src/mcp_tools_py/code_checker_pytest/runners.py:151` — low — stale comment `NOTE: venv_bin parameter is still accepted for PATH adjustment below.` describes the removed dual role of `venv_path` (interpreter selection vs PATH); the renamed parameter and its docstring now say this, so the comment is vestigial.
`src/mcp_tools_py/server.py:83` — low — the `venv_path` docstring in `ToolServer.__init__` (and the identical one in `create_server` at `src/mcp_tools_py/server.py:296`) still presents the flag as the normal way to select the tool environment, with no deprecation note, while `--help`, README, architecture doc and the startup warning all mark it deprecated.
`.mcp.json:11` — low — this repo's own MCP config (and `.mcp.macos.json:11`) still passes `--venv-path` alongside `--python-executable`, so every server start now emits the deprecation warning this branch introduced and resolution still goes through the deprecated precedence path; mitigated by the fact that mcp-config regenerates these files (tracked as MarcusJellinghaus/mcp-config#56).
`tests/test_tool_availability/_helpers.py:10` — low — `_create_server` docstring claims "with mocked FastMCP and execute_command", but the helper only constructs `ToolServer`; every caller sets up those patches itself.
**Decisions**:
Verdict(decision='tasks', tasks=["In src/mcp_tools_py/server.py:157, replace the hand-rolled startup warning template with a call to tool_unavailable_message so the eager warning matches the handler's wording and uses the package override (lint-imports must instruct installing import-linter, not lint-imports).", 'Add a deprecation note to the venv_path docstring in ToolServer.__init__ (src/mcp_tools_py/server.py:83) and the identical one in create_server (src/mcp_tools_py/server.py:296), pointing to --python-executable, matching --help, README and the architecture doc.'], escalate_reason=None)
**Changes**:
applied
