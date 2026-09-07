# Implementation Review Log 1 — Issue #217

Model the project environment explicitly, and resolve library source and symbols against it.

Branch: `217-model-the-project-environment-explicitly-and-resolve-library-source-and-symbols-against-it`

Supervised code review. Each round: review subagent → triage → fixes → commit.

## Round 1 — 2026-09-07

**Findings**

1. `probe.py` `source` — `importlib.import_module` executes the target's top-level code, whose `print()` output lands on the same stdout the source is written to, so banners are prepended to the returned source. Verified by probe.
2. `tool_context.py:81` — `info.importable` is keyed by module name, but looked up by tool key. Correct only because every `-m` tool's key equals its module today.
3. `README.md:205` / `unavailable_message` — both still say console-script availability is cached at startup and needs a restart; it is now a live `exists()` per call.
4. Six registrars repeat `not is_tool_available(x) or binary(x) is None`; the second half is unreachable.
5. `_STDERR_SNIPPET = 500` defined in both `environment_info.py` and `inspect_library.py`.
6. `SOURCE_TIMEOUT_SECONDS = 30` hardcoded, not routed through `resolve_timeout`.
7. `.importlinter` forbidden wildcards stop at three levels; a bare `import mcp_tools_py` is unmatched.
8. Fail-open branch logs "Assuming %s is available" then can return `False`.
9. File-size allowlist entry for `server.py` is stale — this branch shrank it to ~128 lines.
10. `implementation_review_log_1.md` untracked.

**Decisions**

- **Accept 1** — functional regression against the pre-move behaviour, and packages that print at import are common.
- **Accept 2** — `TOOL_MODULES` exists to express key ≠ module; using it is correctness, not future-proofing.
- **Accept 3** — this branch changed the behaviour the docs describe.
- **Skip 4** — a `require_binary` helper touches six files and adds a context method. The pattern is a mypy-narrowing idiom and the branch is harmless. Renovation, not Boy Scout.
- **Accept 5** — DRY; both copies were created by this branch.
- **Skip 6** — needs a new `ToolName` member and a config knob the issue never asked for. YAGNI.
- **Skip 7** — speculative. The bare-root gap is a documented structural limit: the contract cannot forbid its own ancestor.
- **Accept 8** — one-line honesty fix in a file already being edited.
- **Accept 9** — staleness caused by this branch.
- **Skip 10** — this skill's own log; committed later in the process.

**Changes**

- `probe.py`: `_resolve_source` split out; `_source` wraps it in `redirect_stdout(io.StringIO())`.
- `tool_context.py`: fail-open branch returns `True`; probe lookup goes through `TOOL_MODULES`; console-script message says no restart is needed.
- `environment_info.py` / `inspect_library.py`: one shared `STDERR_SNIPPET`.
- `README.md`: troubleshooting split into per-call console scripts vs process-cached `python -m` tools.
- `.large-files-allowlist`: `server.py` entry removed (three pre-existing stale entries left).
- `tests/test_inspect_library.py`: new regression test for import-time banner output.
- `tests/test_tool_context.py`, `tests/test_code_checker_bandit/test_integration.py`: two console-script message assertions repointed.

`environment_info._failed()` needed no change — already module-keyed.

**Checks**: pylint clean, 699 unit + 23 integration tests pass, mypy clean, ruff/vulture/lint-imports/black clean.

**Status**: committed

## Round 2 — 2026-09-07

Round 1's six fixes were re-verified as correct and complete; nothing new was broken.

**Findings**

1. `tests/test_tool_availability/test_handler_short_circuit.py:21` — `_server_with(**importable)` never reads the parameter, but its docstring says it configures the reported environment. A future caller trusting it gets a green-but-meaningless assertion.
2. `docs/architecture/dependencies/pydeps_graph.svg` — stale. The branch regenerated the `.dot` and `.html` from the same command but not the `.svg`.
3. `probe.py` — `redirect_stdout` covers the target module's import output, not the target *interpreter*'s (a printing `sitecustomize.py` or `.pth`). Suggested a sentinel-line protocol.
4. `FormatterTools.context` is public though nothing outside reads it, unlike the three private `_context` registrars.
5. `tests/test_tool_availability/` is now a misnomer and exports `_helpers` to four outside modules.
6. `.large-files-allowlist` has further staleness: three stale entries, a duplicated `rope_tools.py` line, and a path naming a directory that no longer exists.
7. Tool-version INFO logging is gone, though `Decisions.md` D4 claims it is "preserved via the probe blob's `distributions` map". Nothing logs it.

**Decisions**

- **Accept 1** — a helper whose docstring contradicts its body is a trap, and the file is one this branch reworked.
- **Accept 2 (best effort)** — the plan required regenerating the graph; attempt it, change nothing if the toolchain is missing.
- **Skip 3** — speculative hardening against an unusual interpreter setup. The `info` subcommand already fails open safely on unparseable output.
- **Skip 4** — cosmetic rename of readable code.
- **Skip 5** — D10 already settled `_dummy_python`'s home; moving it is churn.
- **Skip 6** — pre-existing on `main`, out of scope.
- **Accept 7** — a recorded decision claims a diagnostic is preserved that in fact was lost. Fix the code, in one place.

**Changes**

- `test_handler_short_circuit.py`: `**importable` dropped, docstring rewritten. No call site changed — all five already passed nothing.
- `environment_info.py`: `TOOL_DISTRIBUTIONS` derived from `TOOL_MODULES`/`TOOL_PACKAGES`, and `_log_tool_versions` logs found distributions at INFO on the success path of `get_environment_info` — once per interpreter per process, since the result is `lru_cache`d. Failure path untouched.
- **Finding 2 not applied**: GraphViz is not installed on this machine (`dot` absent from PATH and from Program Files), and `tools/pydeps_graph.bat` only emits the SVG when it is present. Nothing was written; the readme and the stale `.svg` are unchanged. The SVG needs regenerating on a machine with GraphViz.

**Checks**: pylint clean, 699 unit tests pass, mypy clean, vulture and black clean.

**Status**: committed

## Round 3 — 2026-09-07

Commit `98272aa` verified correct and complete. No Critical findings.

**Findings**

1. The tool-version logging restored in round 2 has no test. It was silently dropped once already and caught only by human review; a search for `_log_tool_versions` hits nothing but the source.
2. `.importlinter:52` scopes `target-scripts-stdlib-only` to the single module `…target_scripts.probe`, but `target_scripts/__init__.py` and `architecture.md:269` both claim the whole directory is enforced. A second script there would import the project with the contract still reporting KEPT.
3. `_clear_project_cache` is byte-identical in four test modules.
4. `server.py:47-52` still assigns `test_folder`, `keep_temp_files`, `vulture_whitelist`, `check_timeout`, `refactoring_timeout` — each written only to be read back when building `ToolContext`. `step_6.md:180` prescribed moving them.

**Decisions**

- **Accept 1** — a diagnostic that has already been lost once silently needs a test, not vigilance.
- **Accept 2** — the docs describe a guarantee the contract does not give. Prefer widening the contract over narrowing the docs, if it can be shown to bite.
- **Accept 3** — duplication created by this branch; the fix is one new conftest.
- **Accept 4** — two names for one value is exactly the duplication the `ToolContext` refactor set out to remove.

**Changes**

- `tests/test_environment_info.py`: `TestToolVersionLogging` — success path asserts one record naming `pylint 3.2.0` and `import-linter 2.0`; failure path asserts none, which pins the call to the success path.
- `.importlinter`: `source_modules` widened to the `mcp_tools_py.utils.target_scripts` package. A `.scratch` experiment first **confirmed the hole** — with the old single-module scope, a second script importing a project module still reported KEPT (rc=0); widened, it reports BROKEN (rc=1) and names the edge, while still catching `probe.py` itself. The ancestor-overlap trap does not bite at this scope. `tests/test_target_scripts_contract.py` gained `test_second_script_is_covered_too`. Widening made the docstring and `architecture.md:269` true as written, so no doc edit was needed.
- `tests/test_refactoring/conftest.py` (new) holds the one fixture; three copies deleted along with the imports they alone kept alive. The copy in `test_environment_integration.py` stays — it is outside the package. `vulture_whitelist.py` comment updated.
- `server.py`: all five superseded attributes removed, parameters flow straight into `ToolContext(...)`. `project_dir` and `environment` kept — `_warn_missing_console_scripts` reads them. Every removal was checked with `find_references` plus a repo-wide search; the only readers were `test_server_params.py:588-589`, repointed to `server.context.*`.

**Checks**: pylint clean, 701 unit + 24 integration tests pass, mypy clean, vulture clean, lint-imports 4/4 kept.

**Status**: committed

## Round 4 — 2026-09-07

Commit `e758e1f` verified correct and complete on all four counts; nothing new introduced.
Notably, `test_second_script_is_covered_too` proves the widened contract catches the
*second* script specifically, and both new logging tests share an interpreter key, so they
would false-pass without the autouse cache-clearing fixture — which is present.

**Findings**: none. One nitpick was raised and withdrawn in the same breath: a third
`_clear_project_cache` copy remains in `tests/test_environment_integration.py`, outside the
refactoring package. Consolidating it would mean moving the fixture to the root
`tests/conftest.py`, where it would run for the entire suite — a worse trade. Left as is.

**Changes**: none. The review loop terminates here.

**Status**: no changes needed

## Final Status

Four review rounds; three produced commits, the fourth was clean.

| Round | Findings | Accepted | Commit |
|---|---|---|---|
| 1 | 10 | 6 | `adc3f08` |
| 2 | 7 | 3 (1 blocked) | `98272aa` |
| 3 | 4 | 4 | `e758e1f` |
| 4 | 0 | — | — |

**Most significant fix**: `probe.py` returned any output the target module printed at import
time prepended to the source it was asked for — a regression introduced by moving the
resolution into a child process, invisible to every existing test.

**Also worth noting**: the widened `.importlinter` contract closed a real hole, confirmed by
experiment rather than inspection. Under the original single-module scope, a second script
in `target_scripts/` could import the project and the contract still reported KEPT.

**Final checks** (run by the supervisor at `e758e1f`): vulture clean, lint-imports 4 kept /
0 broken, tach clean. Engineer-run at the same commit: pylint clean, 701 unit + 24
integration tests pass, mypy clean.

**Outstanding, not fixable here**: `docs/architecture/dependencies/pydeps_graph.svg` is
stale. GraphViz is not installed on this machine and `tools/pydeps_graph.bat` only emits the
SVG when it is present, so the file still shows a pre-#217 graph beside a current `.dot`.
It needs regenerating on a machine with GraphViz.

**Rejected findings**, recorded so they are not re-raised: a `require_binary` helper across
six registrars; a configurable `SOURCE_TIMEOUT_SECONDS`; a fourth `.importlinter` wildcard
level; a sentinel-line protocol against interpreter-level stdout; renaming
`FormatterTools.context`; relocating `_dummy_python`; and the pre-existing
`.large-files-allowlist` staleness this branch did not cause.
