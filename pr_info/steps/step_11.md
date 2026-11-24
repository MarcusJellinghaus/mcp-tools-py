# Step 11 — Agent guidance: remove the `-n auto` rule

## LLM prompt
Read `pr_info/steps/summary.md`, then implement **this step only** (`pr_info/steps/step_11.md`).
Documentation only, so there are no tests. Edit the three files below with `mcp__mcp-workspace__edit_file`.
Run `run_format_code`, pylint, pytest (`markers=["not integration"]`) and mypy; make one commit.

## WHERE
- `.claude/CLAUDE.md` ("Code quality checks" section)
- `.claude/skills/implementation_review_supervisor/SKILL.md` (~line 76)
- `.claude/skills/implement_direct/SKILL.md` (~line 55)

## WHAT / HOW
- `.claude/CLAUDE.md`:
  - Delete the line ``**Pytest:** always use `extra_args: ["-n", "auto"]` for parallel execution.`` The project's `addopts` already has `-n auto`.
  - Rewrite the three examples:
    ```python
    # Fast unit tests (recommended for regular development)
    mcp__mcp-tools-py__run_pytest_check(markers=["not integration"])

    # All tests (slow)
    mcp__mcp-tools-py__run_pytest_check()

    # Integration tests only
    mcp__mcp-tools-py__run_pytest_check(markers=["integration"])
    ```
  - Keep the marker paragraph and the "When debugging…" line. The debugging line stays as `"-v", "-s", "--tb=short"`.
- `implementation_review_supervisor/SKILL.md`: change "pytest needs `extra_args=["-n", "auto"]` plus integration-marker exclusions" to "pytest needs integration-marker exclusions".
- `implement_direct/SKILL.md`: delete the parenthetical ``(with `extra_args: ["-n", "auto"]`)``, so the line reads ``- `mcp__mcp-tools-py__run_pytest_check` — fix all failures``. It stays a full-suite run.
- Then search `.claude/` for `-n", "auto` and `-n auto`; no matches must remain.

## DATA
None. Sibling repos are out of scope (separate follow-up).
