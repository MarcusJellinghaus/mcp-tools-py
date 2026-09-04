# Decisions

Decisions taken in discussion while updating the plan. Issue-level decisions live in the
GitHub issue; this file records only what was settled here.

## Round 6 — after the rebase onto #229

Context: the branch was rebased onto `60e1cc3 fix(server): detect tools next to the
resolved interpreter (#229)`, which landed on main after the plan and five review rounds.
It rewrote `server.py`, split `tests/test_tool_availability.py` into a package, reworked
`main.py`, `README.md`, `code_checker_pytest/runners.py`, `docs/architecture/architecture.md`,
all nine `checker_tools/*_tool.py`, the formatter modules, and added `tests/test_main_args.py`.

### D1 — Issue decision 5 stands: one configurable environment, the project env

#229 rewrote the `--python-executable` help text to say it "should point to the environment
where they are installed (the tool's own venv), not the project's runtime venv". Marcus
confirmed that framing is backwards and decision 5 wins: pylint, pytest and mypy must import
the project's dependencies, so the checker venv and the project-dependency venv are
necessarily the same one.

Five places carry the wrong framing and the plan now names each: `main.py:70-78` (step 1);
`README.md:103`, `:135`, `:165` and the Troubleshooting section at `:185-188` (step 3).

### D2 — Criteria are re-expressed through `--python-executable`

#229 deprecated `--venv-path` (hidden from `--help` at `main.py:83`, warned about at
`:197-202`, pinned by `tests/test_main_args.py:27,63`). Acceptance criterion 1 and step 4's
integration test now speak of `--python-executable`.
`PythonEnvironment.resolve(venv_path=...)` keeps honouring the deprecated flag for the
transition, and step 1's `main.py` edit must not break `tests/test_main_args.py:27,63`.

### D3 — Step 1 is re-scoped, not deleted

#229 delivered most of it. Step 1 now introduces `PythonEnvironment` as the value object
steps 3, 4 and 6 consume, moves the two surviving `Scripts`/`bin` branches into it
(`server.py:133-136` and `:182`), and corrects the `main.py` help text. Specifically:

- **Criterion 4 dropped from step 1** — "console-script tools found with only
  `--python-executable`" is already done (`server.py:183`, pinned by
  `test_check_tool_availability.py:170`).
- **Criterion 3 reworded** — "one `Scripts`/`bin` branch, not seven" is unachievable: five
  of seven are gone and `PythonEnvironment` as designed ends with the same two. It becomes
  "both surviving branches live in one module".
- **Issue decision 22's `venv_bin` → `bin_dir` rename dropped entirely.** #229 already
  derives the value from the interpreter under the name `venv_bin`; renaming would churn
  `runners.py`, `pytest_tool.py`, `tests/test_code_checker/test_runners.py` and
  `tests/test_server_params.py` for nothing. Decision 22 counts as satisfied.
- **`resolve()` carries `_resolve_python_executable`'s body verbatim** — existence check,
  `shutil.which` PATH fallback, and the message including the `source` label. Three tests
  pin it.
- **Deleted as obsolete:** the discussion of five `self._<tool>_binary` attributes and the
  mypy `attr-defined` problem (`_tool_binaries` replaced them); the instruction to rewrite
  the two `_when_no_venv` tests (#229 already did, as `..._when_script_not_on_disk`); the
  instruction to fix the `_check_tool_availability` docstring (done).

### D4 — The probe preserves #229's fail-open policy

`server._is_tool_available` fails open on a 30 s timeout: the tool is reported available
with a logged warning so the call proceeds and surfaces the real error
(`test_is_tool_available.py:101`). A failed or timed-out probe must therefore return a
failure-shaped `EnvironmentInfo` in which the five module tools read as **available**, not
unavailable — otherwise one slow probe makes all five vanish at once, where today each fails
open independently. `test_timeout_fails_open_and_caches` is re-anchored onto the probe, not
deleted.

Three #229 behaviours need no carry-over, and step 2 says why:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` (the probe no longer executes anything), version logging
(preserved via the probe blob's `distributions` map), and the console-script fast path (one
probe now serves all five). The three tests that assert those mechanics are deleted.

### Mechanical re-anchoring

The plan's ~60 line-precise references were re-verified against the working tree and
corrected: the `tests/test_tool_availability/` package split, the 24 `execute_command` patch
sites, the `_tool_binaries` substitution table, `README.md`, `architecture.md`,
`test_server_params.py` and `test_checker_tools.py` line numbers, and `server.py` itself.

Two consequences worth recording:

- **`tests/test_tool_availability/test_handler_short_circuit.py:187`** is a new reader of
  `ToolServer.venv_path` (`assert server.venv_path is None`), added by #229. Step 1 deletes
  that attribute, so the line goes with it.
- **Three parallel taxonomies of the same ten tools** would have existed —
  `_TOOL_MODULES`/`_TOOL_PACKAGES` in `server.py`, `PROBED_MODULES` in `environment_info.py`,
  `CONSOLE_SCRIPT_TOOLS` in `tool_context.py`. One home was chosen
  (`utils/environment_info.py`) and the others derive from it.
- **The dependency-graph regeneration step** (`docs/architecture/dependencies/readme.md`)
  was missing from steps 3 and 7, both of which edit `tach.toml`. Added to both.

### Verified unchanged by #229 — left alone

`.importlinter` (all six `ignore_imports` entries), `tach.toml`, `vulture_whitelist.py:26-27`
and `:75-76`, `tests/test_inspect_library.py`, `refactoring/jedi_tools.py`, and the fourteen
`TYPE_CHECKING` importers of `FastMCPProtocol`. Steps 3, 4 and 5 therefore stand as written
apart from the D1/D2 wording changes and the line-reference corrections.
