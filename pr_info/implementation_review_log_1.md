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

## Round 2 — 2026-09-02
**Findings**:
I'll gather context systematically. Starting with the knowledge base, issue, and plan files.`src/mcp_tools_py/server.py:228` — medium — the `package` parameter of `tool_unavailable_message` has no production caller since `_TOOL_PACKAGES` was added in 4dd763c (all ten tool modules call it with the key only); two mechanisms now exist for one job and only a test exercises the parameter — drop it or drop the map.
`src/mcp_tools_py/server.py:137` — medium — the new existence check rejects a PATH-resolvable interpreter name: `--python-executable python3` worked on `main` (the subprocess resolved it) and now raises `FileNotFoundError` at startup; Decision 12 targets stale/unresolved paths, not bare names — a `shutil.which` fallback before raising would preserve that configuration.
`src/mcp_tools_py/main.py:70` — medium — `--python-executable` help is stale after `--venv-path` was suppressed: it still says "for running pytest, pylint, and mypy", omitting that ruff, bandit, vulture, tach and lint-imports are now located next to it and that a non-existent path fails at startup; the README row this branch rewrote says both, and `--help` is now the only place a user sees the flag.
`README.md:137` — low — "Both examples below build that path by interpolating an environment variable" is false: the Incorrect Configuration example at `README.md:168` uses a literal path.
`src/mcp_tools_py/code_checker_pytest/runners.py:151` — low — stale comment "NOTE: venv_bin parameter is still accepted for PATH adjustment below" describes the removed dual role of the old `venv_path`; the renamed parameter and its docstring already say this (unchanged since round 1).
`tests/test_tool_availability/_helpers.py:10` — low — `_create_server` docstring claims "with mocked FastMCP and execute_command", but the helper only constructs `ToolServer`; every caller sets up those patches itself (unchanged since round 1).
**Decisions**:
Verdict(decision='tasks', tasks=['In src/mcp_tools_py/server.py, remove the now-unused `package` parameter of `tool_unavailable_message` and let `_TOOL_PACKAGES` be the single source of install names; update the test that only exercised the parameter to cover the map instead (e.g. lint-imports resolving to import-linter).', 'In src/mcp_tools_py/server.py:137, fall back to `shutil.which` before raising `FileNotFoundError` so a PATH-resolvable interpreter name such as `--python-executable python3` keeps working; add a test for the bare-name case alongside the stale-path case.', 'Update the `--python-executable` help text in src/mcp_tools_py/main.py:70 to match the README row: it locates all bundled tools (pytest, pylint, mypy, ruff, bandit, vulture, tach, lint-imports), and a non-existent path fails at startup.', 'Fix the false claim at README.md:137 — the Incorrect Configuration example at README.md:168 uses a literal path, not an interpolated environment variable; reword so the sentence describes only the example(s) that interpolate.'], escalate_reason=None)
**Changes**:
applied

## Round 3 — 2026-09-02
**Findings**:
I'll gather context systematically. Starting with the knowledge base, the issue, and the branch diff.Context gathered: knowledge base, issue #220 (no linked open dependencies beyond #219, already merged into `main`), `pr_info/steps/*`, and the branch diff against `origin/main` (implementation changes present — `server.py`, ten tool modules, `runners.py`, `main.py`, tests, docs). Verified on the branch: pytest 646 passed / 1 skipped, mypy clean, pylint clean, vulture clean.

Checked against the issue's decisions: detection derives from `_resolved_python` in both paths (1), `--venv-path` soft-deprecated but still resolving (2, 11), fast path → probe → fail-open-on-timeout with `timed_out` branched first (3, 4, 13), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` merged additively by `prepare_env` (5), plain `30` (6), `module=None` for the five script tools with no fail-open (7), `_tool_binaries` replacing the five `_X_binary` attributes and their asserts (8), messages naming `--python-executable` and the directory searched (9), `venv_bin` as a bin directory at all three call sites (10), startup interpreter validation with a `shutil.which` fallback (12), `os.path.exists` throughout detection (15), and docs (14). No `--venv-path` string survives in `src/` messages.

`src/mcp_tools_py/code_checker_pytest/runners.py:151` — low — stale comment `NOTE: venv_bin parameter is still accepted for PATH adjustment below.` describes the removed dual role of the old `venv_path`; the renamed parameter and its docstring already state this (unchanged since round 1).
`tests/test_tool_availability/_helpers.py:10` — low — `_create_server` docstring claims "with mocked FastMCP and execute_command", but the helper only constructs `ToolServer`; every caller sets up those patches itself (unchanged since round 1).
`tests/test_checker_tools.py:44` — low — the `mock_server` fixture stubs `tool_unavailable_message` with its own wording, so the six handler short-circuit assertions no longer exercise the real templates; covered instead by `tests/test_tool_availability/test_unavailable_message.py`.

No `critical` or `high` findings.
**Decisions**:
Verdict(decision='dismiss', tasks=[], escalate_reason=None)
**Changes**:
rebase-needed
**Escalate reason**: rebase
