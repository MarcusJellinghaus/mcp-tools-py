# review-plan review log 2

Context: the branch was rebased onto `60e1cc3 fix(server): detect tools next to the
resolved interpreter (#229)` before this run. That commit rewrote `server.py`, replaced
`tests/test_tool_availability.py` with a `tests/test_tool_availability/` package, and
reworked `main.py`, `README.md`, `code_checker_pytest/runners.py` and
`docs/architecture/architecture.md` — all of which the plan referenced by line number.
This run's first concern was re-anchoring the plan to the post-#229 tree.

## Round 1 — 2026-09-04

**Findings**:

Scope overlap with #229:
- `pr_info/steps/step_1.md` — high — step 1's deliverables are largely already on main:
  criterion 4 done (`server.py:183`, pinned by `test_check_tool_availability.py:170`);
  five of seven `Scripts`/`bin` branches gone; decision 22 done under the name `venv_bin`;
  the five `_<tool>_binary` attributes already collapsed to `_tool_binaries`; both
  `_when_no_venv` tests already rewritten; the `_check_tool_availability` docstring
  already fixed. `PythonEnvironment` as designed ends with the same two branches that
  survive, so step 1 delivers zero net branch reduction.
- `src/mcp_tools_py/main.py:70-78` — high — #229 restated the "point at the tool's own
  venv, not the project's runtime venv" framing as deliberate policy, and repeated it at
  `README.md:103,135,165` and a new Troubleshooting section at `:185-188`. Issue
  decision 5 says the opposite. Criterion 10 is no longer a stale-docs cleanup.
- `pr_info/steps/summary.md` criterion 1, `step_4.md:11` — high — written around
  `--venv-path`, which #229 deprecated (hidden from `--help`, warns on use, pinned by
  `tests/test_main_args.py:27,63`).
- `pr_info/steps/step_2.md:99-118` — medium — the `find_spec` probe silently reverses
  four behaviours #229 added on purpose, including a 30 s timeout that fails **open**.

Stale references (~60):
- All ~40 references to the deleted `tests/test_tool_availability.py` across steps 1, 2
  and 6 — high.
- `step_2.md:206-215` — high — the `execute_command` patch-site list: 24 sites across
  three files, not 15, and every line number stale.
- `step_6.md:73-95` — high — `tool_unavailable_message` already exists on main;
  `test_unavailable_message.py:33,45` assert `"--venv-path" not in message`, which the
  plan's proposed warning text would fail.
- `step_6.md:135-145` — medium — substitution table describes deleted `_ruff_binary`
  attributes and `assert ... is not None` guards.
- `server.py:47,51-65` vs `step_2.md:44` and `step_6.md:47` — medium — three parallel
  taxonomies of the same ten tools.
- `step_1.md:230-236` — medium — patch-target move affects ~14 sites, not 3.
- `test_handler_short_circuit.py:187` — medium — new reader of `ToolServer.venv_path`.
- `step_3.md:98-135` — medium — README instructions wrong in three ways.
- `step_7.md:64-92` — low — architecture doc line refs off by ~76.
- `step_1.md`/`step_6.md` — low — `tests/test_server_params.py` refs off by one.
- Assorted stale `server.py` line refs — low.
- `step_6.md:180-186` — low — `test_checker_tools.py` fixture moved and changed shape.
- Steps 3 and 7 edit `tach.toml` without regenerating the dependency graphs — low.
- `summary.md` "Files modified" omits `tests/conftest.py` and `tests/test_utility_tools.py`
  — low.

Verified unchanged by #229, deliberately left alone: `.importlinter` (all six
`ignore_imports` entries, so decision 26's ordering holds), `tach.toml`,
`vulture_whitelist.py:26-27` and `:75-76`, `tests/test_inspect_library.py`,
`refactoring/jedi_tools.py`, and the fourteen `TYPE_CHECKING` importers of
`FastMCPProtocol`. **Steps 3, 4 and 5 stand as written** apart from wording.

**Decisions**:
- Accepted all 14 mechanical re-anchoring findings — instructed the engineer to apply
  them, with an explicit do-not-churn list for the Part 3 items above.
- Escalated four findings to the user as design/scope questions (below).

**User decisions**:
- **Q1 — the help text contradicts issue decision 5, and #229 re-asserted it.**
  Options: A confirm decision 5 and rewrite #229's wording in all five places;
  B keep #229's framing and reframe the issue; C add a second flag (rejected by
  decision 5). **Answer: A.** Related, handled with A: re-express criterion 1 and step
  4's integration test through `--python-executable`, keeping
  `PythonEnvironment.resolve(venv_path=...)` honouring the deprecated flag.
- **Q2 — does step 1 still earn its place?** Options: A re-scope it to introducing the
  value object, dropping criteria 3/4 and the `bin_dir` rename; B delete it and defer
  `PythonEnvironment` to step 6. **Answer: A.**
- **Q3 — may the probe drop #229's fail-open policy?** Options: A carry fail-open into
  the probe; B accept fail-closed and delete the four tests. **Answer: A.** The other
  three #229 behaviours need no carry-over (`PYTEST_DISABLE_PLUGIN_AUTOLOAD` moot under
  `find_spec`; version logging preserved via `distributions`; console-script fast path
  moot once the probe runs once for all five).

**Changes**: applied to `step_1.md` (rewritten), `step_2.md`, `step_3.md`, `step_4.md`,
`step_5.md`, `step_6.md`, `step_7.md`, `summary.md`, and a new `steps/Decisions.md`
logging D1–D4.

Engineer corrections to the brief, found by checking the tree rather than trusting the
review: `test_unavailable_message.py` has 4 tests, not 5; the `"is not available"`
assertions are at `test_checker_tools.py:200,591,635,679`, `test_formatter_tools.py:318`
and `test_code_checker_bandit/test_integration.py:51-52`; `test_checker_tools.py`'s
fixture is `:13-54`. A Windows `Path` normalisation probe surfaced two further tests step
1 breaks that neither the plan nor the brief listed —
`test_handler_short_circuit.py:162` and `:194`.

**Status**: committed
