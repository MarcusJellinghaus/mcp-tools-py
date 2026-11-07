# review-plan review log 1

## Round 1 — 2026-11-07
**Findings**:
Still reviewing: checking the existing quick-depth tests against step 4's marker read.pr_info/steps/step_3.md:55 — medium — After this step, every existing real-run toolkit test (`tests/test_toolkit_test.py`, `test_toolkit_verify.py`, `test_toolkit_check*.py`, `test_toolkit_saved_coverage.py`, and step 4's strict-marker run) resolves its interpreter from whatever `VIRTUAL_ENV` the test process inherits. Nothing in `src/` sets or clears it, so a shell or CI agent whose `VIRTUAL_ENV` names another env (for example the tool env) or a removed venv makes those tests run in the wrong env or fail as stale. Add an autouse fixture, in `tests/conftest.py` or scoped to the toolkit tests, that runs `monkeypatch.delenv("VIRTUAL_ENV", raising=False)`, and have the new tests set it explicitly.
pr_info/steps/step_3.md:62 — low — `test_set_uses_its_interpreter` picks `Scripts/python.exe` or `bin/python` from the platform. `PythonEnvironment.resolve` picks the layout from `python_environment._IS_WINDOWS`, so the test should read that same flag, or it breaks wherever another test patches it.
pr_info/steps/step_2.md:15 — low — `replace(context, check_timeout=600)` in `_run_check` also raises the default for vulture, lint-imports, tach, ruff, bandit and deptry at `check@full`. The issue only asks for mypy and pylint. The summary (line 13) accepts this, but the plan has no test that pins or documents the `full`-depth behaviour, so either restrict the default to mypy/pylint or add `full` to the parametrized test in `test_default_is_600_for_mypy_and_pylint`.
**Decisions**:
Verdict(decision='tasks', tasks=['In pr_info/steps/step_3.md, add an autouse fixture (in tests/conftest.py or scoped to the toolkit tests) that runs monkeypatch.delenv("VIRTUAL_ENV", raising=False). Existing real-run toolkit tests then stop picking up the VIRTUAL_ENV inherited from the shell or CI. Have the new VIRTUAL_ENV tests set the variable explicitly.', 'In pr_info/steps/step_3.md, change test_set_uses_its_interpreter to choose between Scripts/python.exe and bin/python from python_environment._IS_WINDOWS, the flag PythonEnvironment.resolve uses, instead of detecting the platform itself.', 'In pr_info/steps/step_2.md, restrict the check_timeout=600 default in _run_check to mypy and pylint, as the issue asks. Leave the other checks at check@full with their existing default, and extend test_default_is_600_for_mypy_and_pylint to cover the full depth, including a case showing the non-mypy/pylint checks keep the old default.'], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-11-07
**Findings**:
Plan files and core code read; checking `PythonEnvironment.resolve` and `ToolContext` to validate steps 2–4.`pr_info/steps/step_4.md:15` — low — `_MARKER_LINE = r"^@pytest\.mark\.([^(:]+)"` doesn't exclude newlines, so a marker line with no colon would run into the next line and produce a bad name. This could happen with a hand-written fake stdout like the bare `integration` line planned at `step_4.md:58`. Use `[^(:\s]+` so a name stops at whitespace, and write every fake line in the `@pytest.mark.<name>: <desc>` form real pytest prints.
**Decisions**:
Verdict(decision='tasks', tasks=['In pr_info/steps/step_4.md:15, change _MARKER_LINE to r"^@pytest\\.mark\\.([^(:\\s]+)" so a marker name stops at whitespace or a newline. Rewrite the fake stdout fixtures, including the bare `integration` line at step_4.md:58, in the `@pytest.mark.<name>: <desc>` form that real pytest prints.'], escalate_reason=None)
**Changes**:
applied

## Round 3 — 2026-11-07
**Findings**:
Still reviewing: one last check on the `execute_command` signature that step 4 relies on.NO FINDINGS
**Decisions**:
Verdict(decision='dismiss', tasks=[], escalate_reason=None)
**Changes**:
dismiss
