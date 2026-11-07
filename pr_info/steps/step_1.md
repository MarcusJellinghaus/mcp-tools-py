# Step 1 — Reword `fix.check`, add `fix.test`

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step
(`pr_info/steps/step_1.md`) only. Use TDD: update the tests first, then the
code. Run pylint, pytest (`extra_args=["-n", "auto"]`) and mypy until all
pass, run `run_format_code`, and make exactly one commit.

## WHERE
- `src/mcp_tools_py/toolkit.py`: `_FIX_CHECK_PROMPT`, new `_FIX_TEST_PROMPT`,
  `PythonToolkit.prompt_fragments`.
- `tests/test_toolkit.py`: `TestPromptFragments`.

## WHAT
- `_FIX_CHECK_PROMPT: str`: reworded so it covers findings from any checker
  (type checker, linter, other static checks). No mypy- or typing-specific
  steps. Keep "fix only the reported findings, minimal focused changes,
  keep functionality".
- `_FIX_TEST_PROMPT: str`: fix the failing tests named in the output below.
  Fix the cause (code or test, whichever is wrong) with minimal changes.
  Re-run only the failing tests named in the output to confirm, not the
  whole suite. No arguments or placeholders: the failures travel in
  `ActionResult.fix_text`.
- `prompt_fragments()` adds `"fix.test": _FIX_TEST_PROMPT`. Update its
  docstring to describe `fix.check` as checker-agnostic and add `fix.test`.

## Tests (write first)
In `tests/test_toolkit.py`:
- `test_contains_required_keys`: the key set also has `"fix.test"`.
- Replace the `"mypy type errors" in ...` assertion in
  `test_fix_check_has_no_mypy_output_placeholder`. Keep the placeholder
  assertions. Add a test that `fix.check` doesn't mention "mypy" (case-insensitive).
- New `test_fix_test_reruns_only_failing_tests`: `fix.test` is non-empty,
  has no `[` placeholder, and mentions re-running the failing tests (for
  example, contains "failing tests" and "not the whole suite").

## DATA
`prompt_fragments()` returns
`{"language_context", "check_instructions", "check_instructions.unattended", "fix.check", "fix.test"}`,
all non-empty strings.
