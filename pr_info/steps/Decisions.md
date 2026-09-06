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

### D5 — The `main.py` epilog examples follow the help text

`main.py:52-53` shows `--python-executable /path/to/tools-venv/bin/python` and
`C:\path\to\tools-venv\Scripts\python.exe`. That is D1's backwards framing in example form,
so step 1 renames the example path to a project venv.
`tests/test_main_args.py:63` (`test_epilog_does_not_advertise_venv_path`) only asserts that
the epilog names `--python-executable` and not `--venv-path`, so the rename keeps it green.

### D6 — `ToolServer.resolve_timeout` is deleted, with no delegate left behind

Step 6 previously deferred the choice ("keep it only if something outside the registrars
still calls it"). Nothing does: the only production callers are the nine
`checker_tools/*_tool.py` modules and `formatter_tools.py:84-85`, all of which move to
`ToolContext`. The condition therefore resolves to deletion, and the repo's refactoring
principles rule out leaving a back-compat delegate. `tests/test_server_params.py`'s
`TestResolveTimeout` (`:751-783`) moves to `tests/test_tool_context.py` as the concrete
form of step 6's sketched test 4.

### D7 — the frozen `ToolContext` forces a new mechanism for the invalid-timeout test

`tests/test_checker_tools.py:435-457` induces its error by assigning
`mock_server.resolve_timeout` (`:441`). Assigning any attribute on a frozen dataclass
raises `FrozenInstanceError`, and `pylint_tool.py:48` passes no explicit timeout, so
neither route survives the swap to a real `ToolContext`. Chosen replacement: write
`[tool.mcp-tools-py] pylint-timeout = 0` into the context's `project_dir` and let the real
`get_check_timeout` raise. Patching `tool_context.get_check_timeout` was the alternative;
configuration was preferred because it exercises the real resolution path.

Related: the fixture timeout stubs (`tests/test_checker_tools.py:48-53`,
`tests/test_formatter_tools.py:28-30`) are **dropped**, not ported. With no
`pyproject.toml` in the context's `project_dir`, the real `get_check_timeout` already
returns 300 for pytest, 120 otherwise, and raises on an explicit `0` — what the existing
assertions expect. `validate_timeout` (`tests/test_checker_tools.py:10`) then goes unused
and is removed with the stub.

### D8 — vulture, not ruff or pylint, is the dead-import enforcer

Step 1 justified its dead-import cleanup with "ruff and pylint flag the leftovers". Both
are silenced in this repo: `[tool.ruff.lint] select = ["D", "DOC"]`
(`pyproject.toml:89`) enables only docstring rules, so F401 never runs, and
`disable = ["W", "C", "R"]` (`:144`) with CI's `pylint -E` suppresses unused-import
warnings. Vulture (`ci.yml:154`) reports unused imports at 90% confidence, above the
repo's 60 threshold. Corrected in steps 1 and 2.

Consequence: step 3 had omitted the same cleanup, plausibly because the wrong
justification did not generalise. It now lists the imports `inspect_library.py` loses when
the resolution body moves into `probe.py` — `importlib`, `inspect`, `types`, and `Any` /
`Callable` / `Union` / `cast`.

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

### D9 — `_is_tool_available` keeps its console-script branch after the probe lands

Step 2's sketch went straight from the cache miss to `get_environment_info(...)`. Two
options: add the console-script early return to the sketch, or rewrite
`test_is_tool_available.py:82` (`test_script_only_tool_never_probes`) instead of
repointing it. Chosen: **add the branch**. It keeps steps 2 and 6 consistent — step 6's
`ToolContext.is_tool_available` already has exactly this branch — and it is not optional
anyway: `PROBED_MODULES` never carries a console-script name, so `info.importable` cannot
answer for one.

### D10 — `_dummy_python` is kept, with `tests/test_tool_context.py` as its caller

Step 6 deletes two of `_dummy_python`'s three importers and moves the third out of the
package, so the helper loses every caller. Options: import it from the new
`tests/test_tool_context.py`, or delete it with the two files. Chosen: **keep it**. The
moved `test_unavailable_message` tests still need a pinned script directory — they assert
the searched directory appears in the message, and console-script availability is a real
`os.path.exists` check — and step 1 already prescribes `_dummy_python` over patching
`os.path.exists`, so one idiom covers both.

### Second-order deletions that vulture catches at exactly 60%

Three names lose their last reader because of the plan's own deletions, and the repo runs
`vulture --min-confidence 60` (`ci.yml:154`), so each fails the vulture job rather than
pytest. Named in the steps so the implementer is not surprised:

- `_make_server` (`tests/test_server_params.py:736-748`) — all four call sites are inside
  `TestResolveTimeout`, which moves to `tests/test_tool_context.py` and builds a
  `ToolContext` directly, so the helper is deleted with the class. Its
  `_check_tool_availability` patch at `:747` therefore drops out of step 6's repoint list,
  leaving `:53,105,142,412,798`.
- `EnvironmentInfo.sys_path` — kept for #228 with no consumer. Step 2's first test asserts
  on the attribute; a constructor keyword is a write and dataclass equality is not a read.
- `_dummy_python` — see D10.
