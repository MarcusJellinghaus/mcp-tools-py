# review-implementation review log 1

## Round 1 — 2026-09-30
**Findings**:
Now the source diff.`src/mcp_tools_py/formatter/runner.py:79` — medium — `formatter in _FORMATTER_STEPS` raises `TypeError` when `[tool.mcp-tools-py] formatter` is a TOML array or table (the value can't be hashed), so the step never reaches the `ValueError` that names the key and the file. The MCP layer only catches `ValueError` (`formatter_tools.py:66`), so this becomes an unhandled exception at both entry points. Check `isinstance(formatter, str)` before the lookup, and add a test.
**Decisions**:
Verdict(decision='tasks', tasks=['In src/mcp_tools_py/formatter/runner.py near line 79, check `isinstance(formatter, str)` before the `formatter in _FORMATTER_STEPS` lookup. A non-string `[tool.mcp-tools-py] formatter` value, such as a TOML array or table, must raise the same `ValueError` that names the key and the pyproject.toml file, not a `TypeError`. Add unit tests with an array value and a table value, and assert that each raises that `ValueError`.'], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-09-30
**Findings**:
Reading the key source files directly.NO FINDINGS
**Decisions**:
Verdict(decision='dismiss', tasks=[], escalate_reason=None)
**Changes**:
dismiss
