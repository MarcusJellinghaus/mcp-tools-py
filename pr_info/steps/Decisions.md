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
