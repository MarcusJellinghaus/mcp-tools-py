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

## Round 2 — 2026-09-01
**Findings**:
I'll gather context systematically. Starting with the knowledge base, the issue, and the branch diff.`docs/architecture/architecture.md:182` — medium — §6 sequence diagram still shows `server.py` receiving `run_pytest_check` and calling `check_code_with_pytest()` / `_format_*_result()`; since #202 the tool entry point is `checker_tools/pytest_tool.py` and the formatter is `CheckerTools` (`checker_tools/__init__.py:57`), the same staleness this PR corrected in §5 and at `:202`
`docs/architecture/architecture.md:170` — medium — `utils/subprocess_runner.py` and `utils/file_utils.py` are thin re-export shims over `mcp_coder_utils` (`src/mcp_tools_py/utils/subprocess_runner.py:1-7`), but the Module Overview presents them as implementations and neither the Dependency Rules (`:134-138`) nor Architecture Enforcement (`:238-243`) records the `mcp_coder_utils_isolation` contract in `.importlinter:43`, even though this PR added `mcp-coder-utils` to the runtime dependency list at `:48`
`tests/mcp_tools_py_manual/TEST_PLAN.md:5` — low — "Manual test plan for all 8 tools" is the same 8-of-17 claim the issue targets (it covers the pre-#202 tool set only); not listed among the plan's deliberate exclusions, so it is an omission rather than a scoping decision
**Decisions**:
Verdict(decision='tasks', tasks=['docs/architecture/architecture.md:182 — update the §6 sequence diagram to match the post-#202 flow: the run_pytest_check entry point is checker_tools/pytest_tool.py (not server.py), and result formatting is done by CheckerTools (checker_tools/__init__.py:57), not the _format_*_result() helpers.', 'docs/architecture/architecture.md:170 — describe utils/subprocess_runner.py and utils/file_utils.py as thin re-export shims over mcp_coder_utils rather than implementations, and record the mcp_coder_utils_isolation contract (.importlinter:43) in the Dependency Rules (:134-138) and Architecture Enforcement (:238-243) sections.'], escalate_reason=None)
**Changes**:
applied

## Round 3 — 2026-09-01
**Findings**:
I'll start by gathering context in parallel.`README.md:114` — medium — CLI table says `--log-file` defaults to console-only logging; `main.py:133-140` writes `project_dir/logs/mcp_tools_py_<timestamp>.log` unless `--console-only` is passed, so the documented default is wrong in a table this PR audited.
`tests/mcp_tools_py_manual/TEST_PLAN.md:5` — low — still says "all 8 tools" (pre-#202 set); same stale count the issue targets, deferred in round 2.
`pyproject.toml:7` — low — package description still "for running python code checks (pylint, pytest and mypy)"; the 3-of-17 claim removed from README/architecture.md survives in the PyPI/GitHub blurb, deferred in round 1.
**Decisions**:
Verdict(decision='dismiss', tasks=[], escalate_reason=None)
**Changes**:
rebase-needed
**Escalate reason**: rebase
