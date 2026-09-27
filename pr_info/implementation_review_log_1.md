# review-implementation review log 1

## Round 1 — 2026-09-27
**Findings**:
I'll gather context systematically.I'll verify one load-bearing premise in the design with a scratch probe.

Probe: runs the real tool-env `lint-imports` on a flat-layout temp project with no PYTHONPATH, to see whether its working directory is on `sys.path` at all.
Why MCP doesn't: no Bash used — this is a pytest scratch probe via the MCP tools.Verified the branch is green (pytest 744 + 26 integration, pylint, mypy, lint-imports, vulture all pass) and validated the design's load-bearing premise — that `lint-imports` has its working directory on `sys.path` — with a scratch probe against the real console script (it does; scratch deleted).

`src/mcp_tools_py/code_checker_lint_imports/runners.py:327` — medium — when the config names a root package but `locate_packages` returns no directories at all (src-layout project not installed in the project env), the run proceeds with no `PYTHONPATH` and no info line, so lint-imports can resolve the package from the tool env's own site-packages and report PASSED on an installed copy — the exact silent-stale read the `skipped` info line exists to surface; no test covers this path either.
`src/mcp_tools_py/main.py:74` — medium — `--python-executable` help text omits lint-imports from the tools that come from mcp-tools-py's own environment, so `--help` still implies import-linter must be installed in the project env, contradicting `server.py:39` and `README.md:115,204`; step 4 moved lint-imports but step 5 updated only README and architecture.md.
`src/mcp_tools_py/utils/target_scripts/probe.py:82` — low — on Windows `site.getsitepackages()` includes `sys.prefix` itself, so a located directory under the project venv's root (venv created at the project root) is classified as a site dir: the bridge is suppressed and the info line calls a plain source tree "site-packages of the project interpreter".
`src/mcp_tools_py/utils/environment_info.py:53` — low — narrowing `TOOL_DISTRIBUTIONS` drops the only place any version of ruff/bandit/vulture/tach/import-linter was reported, and nothing logs the tool env's versions that now actually run, so the documented version drift is invisible to a user debugging it.
**Decisions**:
Verdict(decision='tasks', tasks=["In src/mcp_tools_py/code_checker_lint_imports/runners.py around line 327: handle the case where the config names a root package but locate_packages returns no directories. Do not run silently with no PYTHONPATH — emit an info line stating the package could not be located in the project environment (so a PASSED result from the tool env's own site-packages cannot be mistaken for a real check), consistent with the existing 'skipped' info line. Add a test covering this path (config names a root package, locate returns nothing).", "Update the --python-executable help text in src/mcp_tools_py/main.py:74 to include lint-imports in the list of tools that run from mcp-tools-py's own environment, matching server.py:39 and README.md:115,204.", 'Fix the site-directory classification in src/mcp_tools_py/utils/target_scripts/probe.py:82: on Windows site.getsitepackages() includes sys.prefix itself, so a located directory under a venv created at the project root is wrongly treated as site-packages, suppressing the PYTHONPATH bridge and mislabelling a plain source tree in the info line. Exclude the bare sys.prefix entry (match only real site-packages directories) and add a test for a located directory directly under the venv root.'], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-09-27
**Findings**:
I'll gather context systematically.`src/mcp_tools_py/utils/tool_context.py:38` — low — the `environment` attribute docstring still reads "The Python environment the tools run in", which is no longer true now that `tool_environment` runs the five console-script tools; the two adjacent field descriptions disagree about which tools use which environment.

`src/mcp_tools_py/code_checker_lint_imports/runners.py:322` — low — when one root package resolves to a site directory and another to a usable source tree, only the site-packages info line is emitted and its "lint-imports may be reading an installed copy" wording does not say which package that applies to, so a reader cannot tell the bridged package from the unbridged one.
**Decisions**:
Verdict(decision='tasks', tasks=['Correct the stale `environment` attribute docstring in src/mcp_tools_py/utils/tool_context.py:38 so it no longer claims to be the environment the tools run in; describe it as the project/target interpreter and make it consistent with the adjacent `tool_environment` field description (which runs the five console-script tools).', 'In src/mcp_tools_py/code_checker_lint_imports/runners.py around line 322, name the affected root package in the site-packages info line so a multi-package config makes clear which package resolved to a site directory (and is therefore unbridged) versus which resolved to a usable source tree.'], escalate_reason=None)
**Changes**:
applied

## Round 3 — 2026-09-27
**Findings**:
I'll gather context systematically.`src/mcp_tools_py/code_checker_lint_imports/runners.py:342` — medium — with a multi-`root_packages` config, a package the project interpreter cannot locate is silently dropped when a *different* package did locate: `if skipped: ... elif not usable:` emits no info line, so the tool env's own installed copy can answer for it and the report gives no hint that the PASSED is not about the working tree (the round-1 fix only closed the all-packages-unlocated subcase).

`src/mcp_tools_py/utils/environment_info.py:53` — medium — narrowing `TOOL_DISTRIBUTIONS` to the `python -m` tools removes the only place any version of ruff/bandit/vulture/tach/import-linter was reported, and nothing logs the tool env's versions that now actually run, so the version drift `README.md` tells users to manage is not observable from the server's logs.

`src/mcp_tools_py/code_checker_lint_imports/runners.py:344` — low — for a flat-layout project whose package is not installed in the project env, `locate` returns nothing and the report says "lint-imports may be reading an installed copy" although lint-imports' own cwd entry resolves the working tree correctly; the issue's rationale explicitly calls that case covered.

`src/mcp_tools_py/code_checker_lint_imports/runners.py:340` — low — the locate-failure report duplicates the phrase, because `locate_packages`' non-timeout reason already begins "could not locate \<names\> in \<interpreter\>".

`docs/architecture/architecture.md:172` — low — the `utils/environment_info.py` bullet still describes only "the cached one-shot probe" and omits `locate_packages`, the new uncached public function added to that module, while the adjacent `probe.py` bullet was updated for `locate`.

`src/mcp_tools_py/main.py:71` — low — `--python-executable` help still opens with "The checkers run in it", now true of only five of the ten tools; the README parameter table was rewritten to name them explicitly, the help text was not.
**Decisions**:
Verdict(decision='dismiss', tasks=[], escalate_reason=None)
**Changes**:
rebase-needed
**Escalate reason**: rebase
