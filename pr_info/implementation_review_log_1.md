# review-implementation review log 1

## Round 1 — 2026-09-01
**Findings**:
I'll gather context systematically. Starting with the knowledge base, the issue, and the branch diff.Reviewed the full `origin/main...HEAD` diff (13 subprocess invocations, resolver core, CLI, docs, tests). Checks run on the branch: pytest 625 passed / 1 skipped, mypy clean, pylint clean, lint-imports 3 contracts kept.

`src/mcp_tools_py/checker_tools/pytest_tool.py:114` — low — an invalid per-call `timeout_seconds` is caught by the generic handler and returned as `Unexpected error running pytest: ValueError: ...`, while the other per-call surface (`mypy_tool.py:80`) returns a clean `Error: ...`; the two tools that accept the argument report the same user mistake differently.
`src/mcp_tools_py/formatter/formatter_tools.py:81` — low — both `isort` and `black` timeouts are resolved regardless of `resolved_steps`, so an invalid `isort-timeout` fails `run_format_code(steps=["black"])`, and every call parses `pyproject.toml` twice.
`src/mcp_tools_py/server.py:245` — low — `resolve_timeout` describes the propagating `ValueError` inside the `Returns:` block instead of a `Raises:` section, hiding the exception contract that the eight registrars relying on `except Exception` depend on.
`tests/test_checker_tools.py:281` — low — the newly documented behaviour "a malformed `pyproject.toml` now fails every tool call, including `run_tach_check` and `run_lint_imports_check`" has no tool-level test; only `pylint` has a raising-resolver test (`:414`).
**Decisions**:
Verdict(decision='dismiss', tasks=[], escalate_reason=None)
**Changes**:
dismiss
