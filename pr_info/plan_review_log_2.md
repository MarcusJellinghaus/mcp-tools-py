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

## Round 2 — 2026-09-04

Round 2 verified round 1's re-anchoring: ~90 line-precise references spot-checked, the
great majority exact — every `server.py` reference, every `tests/test_server_params.py`
line, all 24 `execute_command` patch sites, the test counts, all eleven `_tool_binaries`
lines, the ten step-6 substitution rows, the fourteen `TYPE_CHECKING` importers, and the
`README.md` / `architecture.md` / `.importlinter` / `tach.toml` anchors. D1–D4 are
consistently reflected across all step files, and the ten issue criteria map cleanly onto
the criteria→step table. The remaining findings are completeness gaps, not corrections.

**Findings**:
- `pr_info/steps/step_6.md` + `summary.md` — high — three test files construct
  `CheckerTools` from a **real** `ToolServer`, not a mock, and are absent from step 6:
  `tests/test_final_validation.py` (24 sites),
  `tests/test_code_checker_pytest/test_reporting.py` (9, via the real-`ToolServer` fixture
  at `conftest.py:21-24`) and `test_code_checker_pytest/test_runners.py:77,136`. CI runs
  `mypy --strict src tests` (`ci.yml:113`), so each is an `arg-type` error.
- `pr_info/steps/step_4.md` + `step_7.md` + `summary.md` — high —
  `tests/test_refactoring/test_rope_tools.py:506` unlisted in both steps; it breaks twice
  (step 4 adds a required `environment` positional, step 7 replaces the signature).
- `pr_info/steps/step_2.md` + `summary.md` — medium — `build` is in neither `dependencies`
  nor the `dev` extra, and CI installs `.[dev]`, so `pytest.importorskip("build")` skips
  everywhere and acceptance criterion 8 would never actually be verified.
- `pr_info/steps/step_5.md` — medium — the expected post-step-5 ignored-import count is
  **2**, not 10: the four deleted expressions match 12 of the 14 edges, `checker_tools.**`
  alone covering the nine `*_tool.py` modules.
- `pr_info/steps/step_1.md` — medium — `server.py`'s `os`, `shutil` and `sys` imports all
  go dead and no step removes them; the removal must share a commit with the repointing of
  the ~20 `patch("mcp_tools_py.server.os.*")` sites or those raise `AttributeError`.
- `pr_info/steps/step_1.md` — medium — patch-target list omits
  `test_resolve_python_executable.py:85` (`shutil.which`, pinned by `:96`) and
  `test_check_tool_availability.py:103`.
- `pr_info/steps/step_1.md` — medium — two further `os.path.join` vs `str(Path(...))`
  mismatches at `test_check_tool_availability.py:68-70` and `:133-135`; `:188-190` is safe.
- `pr_info/steps/step_1.md` — low — `_is_tool_available`'s `_tool_binaries` write at
  `server.py:207` must store a `str` (pinned by `test_is_tool_available.py:77`).
- `pr_info/steps/step_1.md:160` — low — deferring the `tests/test_checker_tools.py:20`
  deletion to step 6 leaves a write with no reader, which vulture flags in step 1.
- `pr_info/steps/step_2.md` — low — the `get_environment_info.cache_clear()` autouse
  fixture is still module-scoped; the `lru_cache` is process-wide. Raised in rounds 4 and 5
  of `plan_review_log_1.md` and applied in neither.
- Seven line-reference drifts across `summary.md`, `step_3.md`, `step_4.md`, `step_6.md`
  — low.

**Decisions**:
- Accepted all eleven mechanics findings.
- One escalation candidate handled autonomously rather than asked: `main.py:52-53`'s epilog
  examples still read `tools-venv`, a sixth site carrying the framing D1 corrects. D1's
  enumeration of five sites was not an exhaustive audit, and renaming an example path is
  applying a decision the user already made, not making a new one — no scope or
  architecture impact.

**User decisions**: none — no finding this round raised a genuine design or scope question.

**Changes**: applied to all seven step files, `summary.md`, and `Decisions.md` (new D5).

Engineer corrections to the brief, found against the tree: vulture runs at `ci.yml:154`,
not `:155`; the stale ignored-import claims are at `step_5.md:82-83,122`, not `:78,110`;
the `dev` extra is `pyproject.toml:46-51`. Most notably it found a **36th** real-`ToolServer`
call site the review missed — `tests/test_server_params.py:546` — and added it to step 6.

**Status**: committed

## Round 3 — 2026-09-04

Round 3 verified round 2's additions and found them fully correct: all 36 real-`ToolServer`
`CheckerTools(...)` sites exact, and a fresh sweep of `CheckerTools(`, `FormatterTools(`,
`RefactoringTools(`, `InspectTools(` and `UtilityTools(` across the whole suite found **no
37th site**. The `build` dev-extra reasoning, step 1's dead-import table, the `cache_clear`
move to `tests/conftest.py` and the post-step-5 ignored-import count of 2 all confirmed,
the last by running `lint-imports`. All four findings below cluster on `resolve_timeout` —
the one name round 2's sweep did not cover.

**Findings**:
- `pr_info/steps/step_6.md:147-149` — medium — `ToolServer.resolve_timeout`'s deletion was
  left conditional, and the condition resolves to *delete* (no production caller outside
  the nine `*_tool.py` modules and `formatter_tools.py:84-85`). But
  `tests/test_server_params.py:751-783` (`TestResolveTimeout`, 4 tests) calls it directly
  and is absent from step 6's readers table for that name.
- `pr_info/steps/step_6.md:222-228` — medium — `tests/test_checker_tools.py:441` induces
  its error by **assigning** `mock_server.resolve_timeout`. Assigning any attribute on a
  frozen dataclass raises `FrozenInstanceError` (probed), and `pylint_tool.py:48` passes no
  explicit timeout, so there is no per-call route either. The step's fixture-migration
  bullet covers only availability and never mentions `resolve_timeout`.
- `pr_info/steps/step_3.md:14` — low — no instruction to remove `inspect_library.py`'s
  dead imports (`importlib`, `inspect`, `types`, and `Any`/`Callable`/`Union`/`cast`) once
  the resolution body moves to `probe.py`. Steps 1 and 2 state this for `server.py`; step 3
  is silent.
- `pr_info/steps/step_1.md:182-183` — low — the stated enforcement reason for removing dead
  imports is wrong. Ruff runs only docstring rules (`pyproject.toml:89`), so F401 never
  fires, and pylint's `disable = ["W","C","R"]` plus CI's `pylint -E` suppress it. The real
  enforcer is vulture (`ci.yml:154`). The instruction is right; the justification is the
  part a reader generalises from, and is plausibly why step 3 omitted the same cleanup.

**Decisions**:
- Accepted all four.
- One borderline choice made without asking: on `resolve_timeout`, took clean deletion with
  `TestResolveTimeout` re-homed onto `ToolContext.resolve_timeout`, rather than keeping a
  one-line delegate on `ToolServer`. The repo's refactoring principles require clean
  deletion with no legacy artifacts, so the simpler end state is the one the rules already
  prescribe.

**User decisions**: none — round 3 raised no design, scope, or requirements question.

**Changes**: applied to `step_1.md`, `step_2.md`, `step_3.md`, `step_6.md`, `summary.md`,
and `Decisions.md` (new D6–D8). The chosen mechanism for the invalid-timeout test is
writing `[tool.mcp-tools-py] pylint-timeout = 0` into the context's `project_dir`; the
engineer confirmed it produces the exact message `test_checker_tools.py:456` already
asserts, so that assertion survives unchanged.

Every line reference in the brief matched the tree — the first round in this run where
nothing needed correcting. The engineer added two facts from the tree: `resolve_timeout` is
at `server.py:264`, and `test_server_params.py:690` carries a section comment that moves
with the class.

**Status**: committed

## Round 4 — 2026-09-06

Round 4 verified all four of round 3's edits as exact and ran a final systematic sweep for
names the plan renames, deletes or re-signatures — `_resolved_python`, `_tool_binaries`,
`_tool_availability`, `tool_unavailable_message`, `_check_tool_availability`,
`_is_tool_available`, `_script_path`, `server.venv_path`/`.python_executable`, every
`patch("mcp_tools_py.server.*")` target, `FastMCPProtocol`/`ToolDecorator`,
`_get_library_source`, `list_symbols`/`find_references`, and all five registrar
constructors. Every count and line number held. **The sweep for source names with unlisted
readers is now exhausted.**

All four findings are a different, second-order shape: a test helper or dataclass field
that loses its last reader because of the plan's *own* deletions. Three fail against
vulture at exactly the repo's 60% threshold (`ci.yml:154`), not against pytest — so the
failure mode is a red vulture job. Round 4 probed vulture to establish each.

**Findings**:
- `pr_info/steps/step_2.md:150-154` — medium — the `_is_tool_available` sketch has no
  console-script short-circuit, so on a cache miss it probes. `test_is_tool_available.py:82`
  (`test_script_only_tool_never_probes`), which step 2 keeps as merely repointed, asserts
  no probe ran. Step 6's `ToolContext.is_tool_available` already has the missing branch.
- `pr_info/steps/step_6.md:165` — medium — moving `TestResolveTimeout` orphans
  `_make_server` (`tests/test_server_params.py:736-748`), its only four callers being
  inside that class. Vulture flags an unused module-level test helper at 60%.
- `pr_info/steps/step_2.md:65` — low — `EnvironmentInfo.sys_path` is kept for #228 with no
  consumer; a constructor keyword is a write, not a read, so vulture flags the field.
- `pr_info/steps/step_6.md` — low — `_dummy_python` (`_helpers.py:23`) loses every caller:
  two of its three importers are deleted by step 6 and the third moves out of the package.

**Decisions**: accepted all four. Two sub-choices made without asking, both the simpler
option and both recorded as D9/D10: keep the console-script branch rather than rewrite
`test_is_tool_available.py:82`; and keep `_dummy_python`, imported from
`tests/test_tool_context.py`, rather than delete it — the moved `test_unavailable_message`
tests genuinely need a pinned script directory (`:30`, `:42` assert the interpreter and bin
dir appear in the message, and console-script availability is a real `os.path.exists`
check), and `step_1.md:301-302` already prefers `_dummy_python` over patching
`os.path.exists`, so one idiom serves both and `_helpers.py` needs no edit.

**User decisions**: none — round 4 raised no design, scope, or requirements question.

**Changes**: applied to `step_2.md`, `step_6.md`, `summary.md`, and `Decisions.md`
(new D9, D10, plus a note on second-order deletions vulture catches at exactly 60%).

The engineer sharpened the first finding into something larger than the failing assertion:
`PROBED_MODULES` never carries a console-script name, so without that branch
`info.importable.get("lint-imports", False)` answers `False` for **all five** console-script
tools. The sketch would have broken their availability outright, not just one test. Step 2
now states why the branch is load-bearing, and the "#229 behaviours needing no carry-over"
bullet was narrowed to retire only the fast path for module tools (`server.py:202-207`),
explicitly keeping the console-script-only branch (`:208-210`).

Every line reference in the brief matched the tree — the second consecutive clean round on
that measure.

**Status**: committed

## Round 5 — 2026-09-06

**Findings**: none.

Round 5 verified all four of round 4's edits as exact — the console-script branch and the
narrowed carry-over bullet in step 2, `_make_server` deleted with `TestResolveTimeout` and
`:747` dropped from the repoint list, the required direct read of `EnvironmentInfo.sys_path`,
and `_dummy_python` kept for `tests/test_tool_context.py`.

It then ran independent checks rather than only re-verifying: step ordering (no step
consumes what a later step creates); step 1's dead-import table against every `os`/`shutil`/
`sys` use in `server.py`; the `.importlinter` 12-of-14 / 2 arithmetic; step 7's "17 tools"
count against the `@mcp.tool()` decorators; step 7's four `architecture.md` anchors; and
every production reader of the six names step 6 removes. All clean.

One sweep round 4 had not run: the three names step 2 moves and renames —
`PROBE_TIMEOUT_SECONDS`, `_TOOL_MODULES`, `_TOOL_PACKAGES` — have no reader outside
`server.py`, so dropping the underscore breaks nothing. It also confirmed
`test_unavailable_message.py` survives step 1 untouched, `_dummy_python` returning a
natively-normalised path so `os.path.dirname(...)` and `str(environment.bin_dir)` agree —
the same exemption already noted for `test_check_tool_availability.py:188-190`.

**Decisions**: none needed.

**User decisions**: none — the third consecutive round raising no design, scope, or
requirements question.

**Changes**: none. The loop terminates on this round.

**Status**: no changes needed

---

## Final Status

**Plan is ready for approval.**

Five rounds in this run, on top of five in `plan_review_log_1.md`. Findings per round: 14,
11, 4, 4, 0. Every acceptance criterion in issue #217 is owned by a named step, with the
single exception of criterion 4, which #229 delivered on main and D3 formally retired.

### What this run was actually about

The branch was **behind main** at the start, and `60e1cc3` (#229, "detect tools next to the
resolved interpreter") had landed in the interim. That commit rewrote `server.py`, deleted
`tests/test_tool_availability.py` and split it into a package, and reworked `main.py`,
`README.md`, `code_checker_pytest/runners.py` and `docs/architecture/architecture.md`. The
plan — refined across five prior rounds — was written against the pre-#229 tree, so roughly
sixty of its line-precise references pointed at code that no longer existed. Reviewing
before rebasing would have produced findings that were wrong on arrival, so the run began
with a rebase.

The core of #217 survived intact: `inspect_library.py:38` still imports in the server's own
process, and `jedi_tools.py:26,99` still build `jedi.Project` with no `environment_path`.
Steps 3, 4 and 5 needed almost no change. Step 1, however, was largely delivered by #229,
and step 6 shrank by roughly half.

### User decisions (round 1)

| # | Question | Answer |
|---|---|---|
| D1 | `main.py`/`README.md` help text contradicts issue decision 5, and #229 re-asserted it | **Confirm decision 5** — one configurable environment, the project env; correct the framing in all five places |
| D2 | Acceptance criterion 1 and step 4's test are written around `--venv-path`, deprecated by #229 | Re-express via `--python-executable`; `resolve(venv_path=...)` still honours the deprecated flag |
| D3 | Does step 1 still earn its place? | **Re-scope, don't delete** — drop criterion 4 as delivered, reword criterion 3, drop the `bin_dir` rename as pure churn |
| D4 | May the probe drop #229's fail-open timeout policy? | **No** — carry fail-open into the probe; the other three #229 behaviours need no carry-over |

D5–D10 were recorded in later rounds as smaller settled choices (epilog examples;
`resolve_timeout` deleted with no delegate; the frozen-context mechanism for the
invalid-timeout test; vulture as the dead-import enforcer; the console-script branch; keeping
`_dummy_python`).

### Commits

| SHA | Round |
|---|---|
| `60f4960` | 1 — rebase plan onto #229 |
| `42129bb` | 2 — real-`ToolServer` call sites, `build` dev dependency, dead imports, count corrections |
| `ca1a92c` | 3 — `resolve_timeout` deletion, frozen-context test mechanism, step 3 dead imports |
| `b1b4af7` | 4 — console-script branch, three vulture orphans |

### Two findings worth carrying into implementation

- **The `build` dev dependency.** `tests/test_packaging.py` uses
  `pytest.importorskip("build")`, and `build` is in neither `dependencies` nor the `dev`
  extra. Acceptance criterion 8 would have skipped silently in CI rather than verifying the
  wheel. Step 2 now adds `build>=1.0`.
- **The console-script branch in `_is_tool_available`.** `PROBED_MODULES` never carries a
  console-script name, so without the early return `info.importable.get("lint-imports",
  False)` answers `False` for all five console-script tools — availability broken outright,
  not merely one failing assertion.
