# review-implementation review log 1

## Round 1 — 2026-09-01
**Findings**:
I'll gather context first.The diff is documentation-only, but documentation *is* the deliverable for this issue, so it is reviewable.

`docs/architecture/architecture.md:154` — medium — "Each checker is exposed by one registrar module, `checker_tools/<tool>_tool.py`" contradicts ":18" (eight checkers, nine tools): ruff is one checker package with two registrar modules (`ruff_check_tool.py`, `ruff_fix_tool.py`), so the mapping is 8 packages → 9 registrar modules, not 1:1.
`README.md:98` — medium — CLI "Optional Parameters" tables still omit `--refactoring-timeout` and `--vulture-whitelist` (`src/mcp_tools_py/main.py:97,103`); this is the same inventory drift the issue targets, and `README.md:422` now advertises vulture running "against `vulture_whitelist.py`" with no documented way to change it.
`docs/architecture/architecture.md:247` — low — CI "Always" list omits the `ruff-docstrings` and `file-size` matrix jobs (`.github/workflows/ci.yml:114,117`); deferred by the plan, but the doc is version-bumped as an accuracy pass.
`pyproject.toml:7` — low — package description still reads "for running python code checks (pylint, pytest and mypy)", the same 3-of-17 claim the PR removes from README and architecture.md; it is the copy users see on GitHub/PyPI.
**Decisions**:
Verdict(decision='tasks', tasks=['docs/architecture/architecture.md:154 — correct the checker-to-registrar mapping: state that the eight checker packages are exposed by nine registrar modules, because ruff has two (ruff_check_tool.py and ruff_fix_tool.py), so it is not 1:1 and does not contradict the counts at line 18.', 'README.md:98 — add the missing CLI options --refactoring-timeout and --vulture-whitelist (see src/mcp_tools_py/main.py:97,103) to the Optional Parameters table, so the vulture whitelist mentioned at README.md:422 has a documented override.'], escalate_reason=None)
**Changes**:
applied
