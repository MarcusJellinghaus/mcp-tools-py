# review-plan review log 1

## Round 1 — 2026-09-02
**Findings**:
I'll gather context first — knowledge base, the issue, and the plan files.`pr_info/steps/step_2.md:138` — high — "Existing tests in this class keep passing unchanged" is false: `TestIsToolAvailable` builds `ToolServer(project_dir=Path("/project"))` with no `python_executable`, so `_resolved_python == sys.executable` and the searched directory is the test venv's `Scripts`, which contains `pytest.exe`; the new fast path short-circuits and `test_first_call_runs_subprocess_and_caches` (`mock_exec.assert_called_once()`, `tests/test_tool_availability.py:268`) and `test_subprocess_failure_marks_unavailable` (`:326`, expects `False`, gets `True`) both fail — the same ambient-interpreter trap the plan already identifies for Step 3, not applied here. Step 2 cannot meet its "all checks pass" exit criterion without rewriting them onto the `tmp_path` script dir.

`pr_info/steps/step_4.md:106` — high — "Existing short-circuit tests ... should pass unchanged" holds only for the real-`ToolServer` tests in `test_tool_availability.py`. Six assertions run against `MagicMock` servers: `tests/test_checker_tools.py:186,376,420,464`, `tests/test_formatter_tools.py:278`, `tests/test_code_checker_bandit/test_integration.py:45`. Once the message comes from `server.tool_unavailable_message(...)`, those return a `MagicMock` and `"ruff is not available" in result` raises `TypeError`. The WHERE table (`step_4.md:11-24`) lists none of these three test files.

`pr_info/steps/step_2.md:79` — medium — the fast path sets `available = True` for a script-group key without writing `self._tool_binaries[key]`, so it can violate the invariant Step 3 relies on ("presence in the dict means available", `step_3.md:52`) after the `assert binary is not None` guards are deleted; a script-group key absent from `_tool_availability` yields `True` from `_is_tool_available` and a `KeyError` at the run site. Either store the path in the fast path when `_TOOL_MODULES[key] is None`, or keep a guard.

`pr_info/steps/step_3.md:107` — low — `test_vulture_unavailable_when_no_venv` is listed both under "Rewrite" (`:100`) and under "Re-point" (`:107`); the two instructions contradict each other.

`pr_info/steps/step_5.md:86` — low — the new PATH regression test is pointed at `tests/test_code_checker_pytest/test_runners.py`, but the existing `run_tests`/`check_code_with_pytest` tests (and the file this step edits) are `tests/test_code_checker/test_runners.py`; leaving the choice open risks two same-named runner test files in different directories.
**Decisions**:
Verdict(decision='tasks', tasks=["In pr_info/steps/step_2.md, correct the claim at line 138 that existing TestIsToolAvailable tests pass unchanged: since ToolServer(project_dir=Path('/project')) resolves _resolved_python to sys.executable, the new fast path finds a real pytest.exe in the test venv's Scripts dir and short-circuits. Add explicit instructions to Step 2 to rewrite test_first_call_runs_subprocess_and_caches (tests/test_tool_availability.py:268) and test_subprocess_failure_marks_unavailable (:326) onto a tmp_path script directory so the ambient interpreter cannot satisfy the fast path.", "In pr_info/steps/step_4.md, add tests/test_checker_tools.py (lines 186, 376, 420, 464), tests/test_formatter_tools.py (line 278), and tests/test_code_checker_bandit/test_integration.py (line 45) to the WHERE table at step_4.md:11-24, and replace the 'should pass unchanged' claim at line 106 with instructions to configure the MagicMock servers' tool_unavailable_message return value (or use a real ToolServer) so the 'X is not available' substring assertions do not raise TypeError on a MagicMock.", 'In pr_info/steps/step_2.md around line 79, make the fast path preserve the invariant Step 3 relies on (step_3.md:52): when _TOOL_MODULES[key] is None, store the discovered script path in self._tool_binaries[key] alongside setting available = True, so a script-group key can never be available with no recorded binary (which would KeyError at the run site after Step 3 deletes the assert binary is not None guards).'], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-09-02
**Findings**:
I'll gather context now.`pr_info/steps/step_3.md:104` — medium — the "Re-point — `_X_binary` → `_tool_binaries[...]`" instruction is wrong for the seven `assert ... is None` assertions it covers (`tests/test_tool_availability.py:175,178,203,205,207,234,236`): with `_tool_binaries` an absent key means unavailable, so a literal subscript re-point raises `KeyError`; they must become `"<key>" not in server._tool_binaries` (or `.get(key) is None`), as the Rewrite bullet at `:101` already states.

`pr_info/steps/step_5.md:92` — medium — new test asserts `venv_bin == os.path.dirname(server._resolved_python)` while the call site is specified at `:50` as `str(Path(server._resolved_python).parent)`; on Windows these differ for a POSIX-style interpreter path (`'\custom'` vs `'/custom'`). Use `os.path.dirname` at the call site, matching Steps 2/4 and Decision 15, which also removes the new `pathlib` import mandated at `:65`.

`pr_info/steps/step_4.md:25` — medium — the MagicMock-server list omits `tests/test_formatter_tools.py:125` (`test_invalid_step_returns_error` passes `steps=["ruff"]`, which short-circuits on availability and asserts `"ruff" in result`); once the message comes from `tool_unavailable_message`, the MagicMock repr contains no `"ruff"`. The prescribed fixture-level fix covers it, but the assertion is not enumerated alongside `:278`.

`pr_info/steps/step_4.md:80` — low — template selection on `_TOOL_MODULES.get(key) is None` cannot distinguish a console-script tool from a key absent from the table; `formatter_tools.py:65` passes user-supplied `steps` to `_is_tool_available` before validation, so `steps=["foo"]` yields "No foo console script was found in <dir>" rather than an invalid-step error. Key on `key in _TOOL_MODULES and _TOOL_MODULES[key] is None`.

`pr_info/steps/step_6.md:74` — low — `test_venv_path_hidden_from_help` and `test_epilog_does_not_advertise_venv_path` (`:84`) cannot be written as described: `main.parse_args()` returns a `Namespace` and exposes no parser, so `format_help()`/`epilog` are unreachable; the tests must capture `--help` via `SystemExit` + `capsys`, or the parser construction must be extracted (listed only as an option).

`pr_info/steps/step_6.md:80` — low — `test_venv_path_logs_deprecation_warning` and `test_no_warning_without_venv_path` call `main()`, which `sys.exit(1)` at `main.py:121-125` unless `--project-dir` names an existing directory; the step does not say to pass a `tmp_path`.

`pr_info/steps/step_3.md:109` — low — `test_vulture_unavailable_when_no_venv` is listed under both Rewrite (`:102`) and Re-point (`:109`); the two instructions contradict each other (carried over unfixed from round 1).
**Decisions**:
Verdict(decision='tasks', tasks=['In pr_info/steps/step_3.md at line 104, fix the \'Re-point — _X_binary → _tool_binaries[...]\' instruction for the seven `assert ... is None` assertions (tests/test_tool_availability.py:175,178,203,205,207,234,236): a literal subscript re-point raises KeyError because an absent key now means unavailable. Specify they become `"<key>" not in server._tool_binaries` (or `.get(key) is None`), consistent with the Rewrite bullet at :101.', 'In pr_info/steps/step_5.md, make the call site at :50 use `os.path.dirname(server._resolved_python)` instead of `str(Path(server._resolved_python).parent)` so it matches the assertion at :92 and Steps 2/4 / Decision 15 (the two differ on Windows for a POSIX-style interpreter path), and drop the now-unneeded pathlib import mandated at :65.', 'In pr_info/steps/step_4.md, add tests/test_formatter_tools.py:125 (`test_invalid_step_returns_error`, which passes steps=["ruff"], short-circuits on availability, and asserts `"ruff" in result`) to the MagicMock-server list at :25 alongside :278, so the fixture-level fix is explicitly applied to that assertion.'], escalate_reason=None)
**Changes**:
applied

## Round 3 — 2026-09-02
**Findings**:
I'll gather context now.Confirmed line anchors. Report:

`pr_info/steps/step_2.md:150` — medium — `test_script_only_tool_never_probes` is unwritable as specified at Step 2: Step 3 has not landed yet, so the old `_check_tool_availability` still pre-populates all five `module=None` keys in `_tool_availability` (as `False`), and no `module=None` key is "absent from `_tool_availability`"; the test must pop the key (or the step must say to).

`pr_info/steps/step_2.md:91` — low — `_TOOL_MODULES.get(tool_name) is None` is also true for a key absent from the table, so `formatter_tools.py:65` passing an unvalidated user `step` (e.g. `steps=["pip"]`) can record a non-tool path in `_tool_binaries`, contradicting Decision 8 ("holds the five script tools only"). Key on `tool_name in _TOOL_MODULES and _TOOL_MODULES[tool_name] is None`.

`pr_info/steps/step_4.md:80` — low — same predicate in `tool_unavailable_message`: an unknown key selects the console-script template, so `steps=["foo"]` yields "No foo console script was found in <dir>" instead of an invalid-step error (carried from round 2, unfixed).

`pr_info/steps/step_3.md:102` — low — `test_vulture_unavailable_when_no_venv` is listed under Rewrite (`:102`) and again under Re-point (`:115`); likewise `test_lint_imports_unavailable_when_no_venv` is under Rewrite (`:100`) while its `:175`/`:178` assertions are counted in the Re-point "seven `is None` assertions" list at `:108` (carried from rounds 1 and 2, unfixed).

`pr_info/steps/step_6.md:74` — low — `test_venv_path_hidden_from_help` and `test_epilog_does_not_advertise_venv_path` (`:84`) cannot reach the parser: `main.parse_args()` builds it as a local and returns a `Namespace`, so `format_help()`/`epilog` are unreachable without capturing `--help` via `SystemExit` + `capsys` or extracting parser construction (carried from round 2, unfixed).
**Decisions**:
Verdict(decision='dismiss', tasks=[], escalate_reason=None)
**Changes**:
dismiss
