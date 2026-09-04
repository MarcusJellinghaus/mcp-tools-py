# Issue #217 — Model the project environment explicitly

## Problem

Three tools resolve Python names against the wrong interpreter:

- `inspect_library.py:38` calls `importlib.import_module` **in the MCP server's own
  process**, so it only sees the tool env.
- `jedi_tools.py:26,99` build `jedi.Project(path=...)` with no `environment_path`, so
  jedi falls back to `VIRTUAL_ENV`, then conda, then "the latest Python on the system".

Every other tool runs against `server._resolved_python`. The bug is a symptom of a
missing concept: the server knows *which interpreter to run tools under*, but nothing
says *"this is the environment Python names resolve in."*

## Architectural / design changes

### 1. A three-layer environment model

| Layer | Kind of question | Where it lives | Cost |
|---|---|---|---|
| 1 | Derivable from paths — interpreter, bin dir, does `ruff.exe` exist | `utils/python_environment.py` | free, `exists()` only |
| 2 | Fixed per server run — Python version, importable modules, installed distributions | `utils/environment_info.py` + `utils/target_scripts/probe.py` | one subprocess, ever |
| 3 | Per query — source of `langchain_openai.ChatOpenAI` | `probe.py source`, called by `inspect_library.py` | one subprocess per call |

`PythonEnvironment` is a **frozen value object** (decision 17: tools keep building their
own command lines; the seam stays open for a capability object if the invariant is ever
violated a second time).

### 2. The invariant

To be stated in `docs/architecture/architecture.md`:

> Any tool that resolves a Python name — module, symbol, or installed package — resolves
> it through `ToolContext.environment`. Never through the ambient process, never through
> `VIRTUAL_ENV`.

### 3. Two non-interchangeable child-process idioms

The repo gains a second kind of subprocess, and the directory name records the difference:

| Child | Interpreter | Invocation | Constraint |
|---|---|---|---|
| `refactoring/rope_cli.py` | `sys.executable` (tool env) | `-m mcp_tools_py.refactoring.rope_cli` | may import the project |
| `utils/target_scripts/probe.py` | the **target** interpreter | absolute file path | **stdlib-only** |

`mcp_tools_py` is not installed in the project env, so `-m` cannot work for `probe.py`;
executing a file by path also puts only that file's directory on `sys.path`, so
package-relative imports fail at runtime. Stdlib-only is a consequence of the invocation,
not a style rule. Enforced by a new `.importlinter` `forbidden` contract.

### 4. One uniform registrar signature

`ToolContext` (frozen, in `utils/`) replaces the three shapes across five registrars.
This is what lets all six `.importlinter` `ignore_imports` entries go away — the
registrars stop importing anything from `server`.

### 5. The two surviving `Scripts`/`bin` branches move into one module

#229 removed five of the original seven: `_check_tool_availability` now derives the search
directory from the resolved interpreter (`server.py:183`), and
`code_checker_pytest/runners.py` takes an already-derived `venv_bin`. Two remain — the
directory branch in `_resolve_python_executable` (`server.py:133-136`) and the `.exe`
filename branch in `_script_path` (`:182`) — and step 1 moves both into
`utils/python_environment.py`. The defect that motivated the collapse ("with only
`--python-executable` set, all five console-script tools report unavailable") is already
fixed on main.

### 6. Availability without subprocesses

- **Console-script tools** (ruff, vulture, bandit, tach, lint-imports) — a filesystem
  question, answered by `PythonEnvironment.binary()`.
- **`-m`-invoked tools** (pylint, pytest, mypy, black, isort) — answered by the single
  probe blob via `find_spec`. All `python -m <tool> --version` subprocesses go away.

## Simplifications applied to the issue's plan

These reduce moving parts without touching any acceptance criterion:

1. **No mutable probe collaborator.** Decision 20 introduces a class purely to reconcile
   `frozen=True` with a lazy cache. A module-level `@lru_cache` function keyed by
   interpreter path removes that tension entirely — `ToolContext` stays frozen and carries
   only values. (`lru_cache` does not cache exceptions, so the probe function *returns* a
   failure-shaped `EnvironmentInfo` instead of raising — which decision 3 wants anyway.)
   That shape reports the five module tools **available**, preserving #229's fail-open
   timeout: one slow probe must not make all five vanish at once.
2. **Same idiom for the jedi project cache**, instead of a second bespoke one.
3. **`server._tool_binaries` is deleted, not moved** — callers use
   `environment.binary("ruff")` at use time. Removes one attribute from `server.py` and
   from three test fixtures.
4. **`prefix` and `is_venv` dropped from the probe blob** — no consumer. `sys_path` stays
   (#228 names it), `distributions` stays (decision 15's error text, #61).
5. **One home for the ten-tool taxonomy.** #229 put `PROBE_TIMEOUT_SECONDS`, `_TOOL_MODULES`
   and `_TOOL_PACKAGES` in `server.py`; step 2 moves them to `utils/environment_info.py` and
   everything else derives from them — `PROBED_MODULES` there, `CONSOLE_SCRIPT_TOOLS` in
   step 6's `tool_context.py`. Three parallel lists of the same ten tools would otherwise
   drift.

## Deviations from the issue, with reasons

- **The `tach.toml` edit for `inspect_library` moves from step 6b to step 3.** tach does
  not see `TYPE_CHECKING` imports (which is why it passes today despite fourteen
  back-edges), but step 3 gives `inspect_library` a **runtime** import of
  `mcp_tools_py.utils`. Deferring would leave step 3 red. `utility_tools` keeps its edit
  in step 7. #228 needs the same `inspect_library` line — whichever lands second must not
  duplicate it.
- **Steps 6 and 7 stay split** (issue decision 25). Simplification 3 and #229 remove much
  of the fixture churn, but step 6 still touches ~16 files; merging would make one ~24-file
  commit.
- **Issue decision 22's `venv_bin` → `bin_dir` rename is dropped.** #229 already derives the
  value from the interpreter under the name `venv_bin`, so the rename would be pure churn
  across `runners.py`, `pytest_tool.py` and two test files. The decision's intent —
  "the PATH prepend follows the interpreter, not `--venv-path`" — is satisfied.
- **Criteria are stated through `--python-executable`, not `--venv-path`.** #229 deprecated
  `--venv-path`: hidden from `--help`, warned about at startup, and no longer used to locate
  tools. It still resolves the interpreter, and `PythonEnvironment.resolve(venv_path=...)`
  keeps honouring it for the transition.
- **The `integration`-marked venv test moves from the end to step 4**, where both fixed
  tools first exist together.
- **`jedi_tools.list_symbols` / `find_references` take a required `interpreter`**, with no
  `None` default. A default meaning "jedi's default environment" would leave the
  `VIRTUAL_ENV` fallback this issue removes reachable, and step 3 makes the same parameter
  required on `_get_library_source`. Cost: fifteen existing test call sites are edited in
  step 4 and each distinct project now builds a `jedi.Environment`.
- **`run_tests(venv_bin=...)` always prepends to `PATH` when given** (the open question
  from the discussion; option A). #229 already implements this: `venv_bin` matches the
  interpreter actually running pytest, so prepending it is correct rather than incidental,
  and the parameter still defaults to `None` for standalone library use.

## Steps

| # | Title | Closes |
|---|---|---|
| 1 | `PythonEnvironment` value object | criteria 3, 10 |
| 2 | Probe script + `EnvironmentInfo` | criteria 5, 8, 9 |
| 3 | `get_library_source` runs in a child | criteria 1 (half), 2 — **reported bug closes** |
| 4 | jedi `environment_path` + venv integration test | criterion 1 |
| 5 | Move `FastMCPProtocol` out of `server.py` | criterion 7 (4 of 6) |
| 6 | `ToolContext`; `CheckerTools` + `FormatterTools` | criteria 6 (part), 7 (6 of 6) |
| 7 | Remaining three registrars; docs | criterion 6 |

Each step is one commit: tests, implementation, and pylint + pytest + mypy passing.

## Files created

```
src/mcp_tools_py/utils/python_environment.py          step 1
src/mcp_tools_py/utils/target_scripts/__init__.py     step 2
src/mcp_tools_py/utils/target_scripts/probe.py        steps 2, 3
src/mcp_tools_py/utils/environment_info.py            step 2
src/mcp_tools_py/utils/mcp_protocols.py               step 5
src/mcp_tools_py/utils/tool_context.py                step 6

tests/test_python_environment.py                      step 1
tests/test_environment_info.py                        step 2
tests/test_target_scripts_contract.py                 step 2
tests/test_packaging.py                               step 2
tests/test_environment_integration.py                 step 4
tests/test_tool_context.py                            step 6
```

One new folder: `src/mcp_tools_py/utils/target_scripts/`.

## Files modified

| File | Steps |
|---|---|
| `src/mcp_tools_py/server.py` | 1, 2, 3, 4, 5, 6, 7 |
| `src/mcp_tools_py/main.py` | 1 |
| `src/mcp_tools_py/inspect_library.py` | 3, 5, 7 |
| `src/mcp_tools_py/refactoring/jedi_tools.py` | 4 |
| `src/mcp_tools_py/refactoring/__init__.py` | 4, 5, 7 |
| `src/mcp_tools_py/utility_tools.py` | 5, 7 |
| `src/mcp_tools_py/checker_tools/__init__.py` | 5, 6 |
| `src/mcp_tools_py/checker_tools/{pylint,pytest,mypy,ruff_check,ruff_fix,bandit,vulture,tach,lint_imports}_tool.py` | 5, 6 |
| `src/mcp_tools_py/formatter/formatter_tools.py` | 5, 6 |
| `.importlinter` | 2 (add contract), 5 (−4 entries), 6 (−2 entries) |
| `pyproject.toml` | 2 (`build` in the `dev` extra) |
| `tach.toml` | 3 (`inspect_library`), 7 (`utility_tools`) |
| `README.md` | 3 |
| `vulture_whitelist.py` | 1 (`_.python_executable`, `_.venv_path`), 3, 7 (if needed) |
| `docs/architecture/architecture.md` | 7 |
| `docs/architecture/dependencies/dependency_graph.html`, `pydeps_graph.*` (generated) | 3, 7 |
| `tests/test_tool_availability/test_resolve_python_executable.py` | 1, 2, 6 |
| `tests/test_tool_availability/test_check_tool_availability.py` | 1, 6 (deleted) |
| `tests/test_tool_availability/test_is_tool_available.py` | 1, 2, 6 (deleted) |
| `tests/test_tool_availability/test_handler_short_circuit.py` | 1, 2, 6 |
| `tests/test_tool_availability/test_unavailable_message.py` | 6 (moved into `tests/test_tool_context.py`; step 2 only constrains its message text) |
| `tests/test_main_args.py` | 1 (must keep passing; no edit expected) |
| `tests/test_inspect_library.py` | 3 |
| `tests/test_checker_tools.py` | 1 (`:20`), 6 |
| `tests/test_code_checker_bandit/test_integration.py` | 6 |
| `tests/test_final_validation.py` | 6 (24 `CheckerTools(server)` sites) |
| `tests/test_code_checker_pytest/test_reporting.py` | 6 (9 sites) |
| `tests/test_code_checker_pytest/test_runners.py` | 6 (2 sites) |
| `tests/test_code_checker_pytest/conftest.py` | 6 (real-`ToolServer` `server` fixture) |
| `tests/test_refactoring/test_refactoring_tools.py` | 4, 7 |
| `tests/test_refactoring/test_rope_tools.py` | 4, 7 (`:506` constructor call) |
| `tests/test_refactoring/test_jedi_tools.py` | 4 |
| `tests/test_refactoring/test_integration.py` | 4 |
| `tests/test_refactoring/test_lazy_imports.py` | 4 |
| `tests/test_formatter_tools.py` | 6 |
| `tests/test_utility_tools.py` | 7 |
| `tests/conftest.py` | 2 (autouse `get_environment_info.cache_clear()`), 6 (shared `ToolContext` fixture) |
| `tests/test_server_params.py` | 6 (`_check_tool_availability`, `_is_tool_available`, `_resolved_python`) |

`pyproject.toml` needs no change for **package discovery**:
`[tool.setuptools.packages.find]` sets only `where = ["src"]`, so `namespaces` defaults to
true, `utils/target_scripts/` with an `__init__.py` is discovered, and its `.py` files ship
in the wheel (criterion 8). It does need one **test dependency**: step 2 adds
`"build>=1.0"` to the `dev` extra, without which `tests/test_packaging.py` skips both
locally and in CI and criterion 8 is never verified.

## Acceptance criteria → step

| Criterion | Step |
|---|---|
| `get_library_source` + `list_symbols` resolve through `--python-executable` | 3, 4 |
| `get_library_source` imports nothing in the server process | 3 |
| Both surviving `Scripts`/`bin` branches live in one module | 1 |
| Console-script tools found with only `--python-executable` | already on main (#229) |
| No `python -m <tool> --version` subprocess remains | 2 |
| All five registrars take the same argument type | 6, 7 |
| `lint-imports` and `tach` pass with six `ignore_imports` removed | 5, 6 |
| `probe.py` present in a built wheel | 2 |
| New contract fails when `probe.py` imports a project module | 2 |
| `main.py` help text no longer contradicts the resolution target | 1 |
