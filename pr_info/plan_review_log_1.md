# Plan Review Log — Run 1

Issue: #192 — `run_pytest_check forces -s, causing xdist worker crashes; truncated error hides root cause`
Branch: `192-run-pytest-check-forces-s-causing-xdist-worker-crashes-truncated-error-hides-root-cause`
Started: 2026-05-20

Plan files at review start: `pr_info/steps/summary.md`, `pr_info/steps/step_1.md`, `pr_info/steps/step_2.md`.
Branch state: up to date with `main`; CI failed on an unrelated flaky `jedi` cache `EOFError` in `test_registered_find_references_uses_relative_paths` (not related to this plan).

## Round 1 — 2026-05-20

**Findings (from `/plan_review` engineer subagent):**
- Citations verified: `pytest_tool.py:93-94`, `runners.py:356-363`, `test_runners.py:394-403`, `test_server_params.py:73-82`, `SanitizedArgs.notes`, `_build_error_detail` truncation behaviour, `MAX_STDERR_IN_ERROR` re-exported from `mcp-coder-utils`. All accurate.
- One minor drift: `utils.py` `-s` strip block is at lines 55-57, not 56-58 as referenced in `summary.md` "Files to Modify" and `step_1.md` "WHAT" / commit message.
- Step sizing: two single-commit, single-concern steps — no need to split or merge.
- TDD ordering, quality gates (pylint/pytest with `-n auto`/mypy), and the marker exclusion list all match `.claude/CLAUDE.md`.
- Edge-case coverage in tests is complete: lone `-s`, `-s` + `-n 0`, `-s` + `-n auto`, `-s` + `--numprocesses auto`, plus the new `INTERNALERROR>` regression test designed with a 600-char `noise` payload that deliberately exceeds the 500-char `truncate_stderr` cap.
- Algorithm placement is correct: post-loop, before path detection (path detection iterates `cleaned`, so `-s` removal must precede it).
- No new dependencies, no `pyproject.toml` changes, no mypy overrides expected.
- No requirements/design questions remain — the issue's Decisions table fully resolves the design space.

**Decisions:**
- **Skip** the line-number drift fix. `.claude/knowledge_base/software_engineering_principles.md` explicitly says line counts/numbers are "not crucial. The LLM is not good at counting. Minor updates are not relevant." The implementing engineer will land the change correctly regardless of the off-by-one in the citation.
- **Accept** the rest of the plan as-is.

**User decisions:** none — no questions raised.

**Changes:** none — no plan files modified.

**Status:** No changes needed.

## Final Status

- Rounds run: 1
- Plan changes committed this review: 0
- Plan is ready for approval and implementation.
- Note: CI is currently failing on an unrelated flaky `jedi` cache `EOFError` in `tests/test_refactoring/test_refactoring_tools.py::test_registered_find_references_uses_relative_paths`. This is independent of issue #192 and should not block implementation start.
