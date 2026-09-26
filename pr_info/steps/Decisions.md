# Decisions

Decisions made during manual/supervisor triage of issue #233's plan, after the
automated plan-review loop hit its 5-round limit without converging
(`pr_info/plan_review_log_1.md`, `pr_info/plan_review_log_2.md`). All four were
confirmed as real, unresolved issues by a manual review pass and triaged by the
supervisor as straightforward fixes (no open design question, no user escalation).

## 1. Split the old step 3 into two commits

**Problem:** the old `step_3.md` bundled two config readers, `_pythonpath_env`, two
signature changes, the `_format_report` refactor (8 existing test call sites), the
registrar binary switch, the `.importlinter` edit, ~15 new unit tests and a new
venv-building integration file — more than one TDD commit, and flagged as oversized
in 3 of 5 automated review rounds without ever being fixed.

**Decision:** split it into:
- `step_3.md` — the pure, unwired helpers (`_read_ini`, `_read_toml`,
  `_root_packages`, `_pythonpath_env`) and the behaviour-neutral `_format_report`
  `info_line` → `info_lines` refactor. Nothing here is called by any handler; the
  registrar and `run_lint_imports_check_impl`'s signature are untouched, so this
  commit cannot expose lint-imports resolving from the tool env without the bridge.
- `step_4.md` — the wiring: `locate_packages` call, `PYTHONPATH` construction, the
  registrar's switch to `context.tool_environment`, the `.importlinter` dead-config
  deletion, the docstring contract fix, and the new `test_bridge_integration.py`.
  This is the one commit that must land atomically.

Old `step_4.md` (documentation) is renumbered to `step_5.md`, unchanged in content.
`summary.md`'s step list, decisions and file/step tables are updated accordingly.

## 2. Correct step 2's VERIFY claim about `test_target_scripts_contract.py`

**Problem:** step 2's VERIFY section claimed that running
`tests/test_target_scripts_contract.py` as an integration test proves the
`target-scripts-stdlib-only` contract holds for the new `probe.py locate` code. It
does not: that test builds its own synthetic `fakepkg`/`probe.py` to prove the
contract's *shape* isn't a silent no-op, and never reads the real `probe.py`. Raised
3 times across automated rounds, never fixed.

**Decision:** drop the claim. Stdlib-only compliance for the new code is established
by inspection (`_locate` and its `main` dispatch use only `importlib.util`, `json`
and `sys`) plus the real-subprocess `TestProbeScript` test already in step 2's own
TESTS section, which runs the actual `probe.py locate` in a child process. No
lint-imports run (MCP tool or otherwise) is required for step 2.

## 3. Fix step 1's lint-imports message-accuracy bug

**Problem:** step 1 routes all `CONSOLE_SCRIPT_TOOLS`, including `lint-imports`,
through `tool_environment` for `is_tool_available`/`unavailable_message`, while
`lint_imports_tool.py`'s binary lookup deliberately stays on `context.environment`
until the tool-env wiring step. In the issue's own normal scenario (tool env has
`lint-imports`, project env doesn't), this makes the handler's short-circuit fire
and `unavailable_message` claim "mcp-tools-py's installation is incomplete: reinstall
and restart", naming the tool env directory — which does have the script. The
message is false: mcp-tools-py's install is fine. Raised twice across automated
rounds, never fixed.

**Decision:** carve `lint-imports` out of the tool-env routing in step 1's
`is_tool_available` and `unavailable_message` (and out of
`_warn_missing_console_scripts`'s tool-env check), so its availability answer, its
message and its binary all keep reading `self.environment` — identical to today —
until step 4 moves all three together. Step 4 deletes the carve-out.

## 4. Note that `locate_packages` is deliberately uncached

**Problem:** `environment_info.py`'s module docstring says every value in the module
is "probed once" and "cached per interpreter path". Step 2 adds `locate_packages`,
which is explicitly uncached (the answer can change while the server runs), without
updating that docstring. Low severity, raised once, never fixed.

**Decision:** step 2 adds a one-sentence caveat to the module docstring noting
`locate_packages` as the exception.

## 5. Make the `_warn_missing_console_scripts` carve-out test asymmetric

**Problem:** `_warn_missing_console_scripts` does its own direct
`self.environment.binary(key)` / `self.tool_environment.binary(key)` check for
lint-imports — a third carve-out site, separate from `is_tool_available` and
`unavailable_message`. Step 1's and step 4's tests for it (`TestStartupConsole
ScriptWarnings`) only used the symmetric case (lint-imports missing from both
envs), where checking either environment gives the same answer, so the test
passes whether or not the carve-out actually exists. Raised in round 2 review.

**Decision:** replace the symmetric sibling case with an asymmetric one, matching
the pattern already used for `test_lint_imports_message_still_names_project_env`
/ `test_lint_imports_binary_comes_from_the_tool_env`: tool env has `lint-imports`,
project env doesn't. Step 1 adds
`test_lint_imports_warning_still_checks_project_env` asserting the startup
warning still fires (proving the check reads `self.environment`); step 4 inverts
the same test's expected outcome (no warning, since `tool_environment` now has
it) instead of deleting it.

## 6. Align cross-reference nits left by the step 3/4 split

**Problem:** three small inconsistencies from round 2 review, all cosmetic and
none blocking implementation: (a) `summary.md`'s file-tracking table listed
`tool_context.py` and `server.py` as touched only in step 1, though step 4 also
edits both to remove the lint-imports carve-out; (b) `summary.md` and
`step_5.md` cited different line ranges (`:203-204` vs `:199-204`) for the same
README Troubleshooting edit; (c) both cited `README.md:115` for the
`--python-executable` parameter-table row, which is actually on line 116.

**Decision:** annotate `tool_context.py`/`server.py` as touched in steps "1, 4"
in `summary.md`'s table; make `step_5.md` use `summary.md`'s more precise
`:203-204`; correct both files' parameter-table citation to `:116`.
