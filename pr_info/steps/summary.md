# Issue #217 — Model the project environment explicitly

## Problem

Three tools resolve Python names against the wrong interpreter:

- `inspect_library.py:36` calls `importlib.import_module` **in the MCP server's own
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

### 5. Seven `Scripts`/`bin` branches collapse to one

Six in `server.py` (`_resolve_python_executable` plus five in `_check_tool_availability`)
and one in `code_checker_pytest/runners.py:203-206`. `bin_dir` derives from the
**interpreter path**, not from `venv_path` — which fixes a live defect for free: today,
with only `--python-executable` set, all five console-script tools report unavailable.

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
2. **Same idiom for the jedi project cache**, instead of a second bespoke one.
3. **The five `_*_binary` attributes are deleted, not moved** — callers use
   `environment.binary("ruff")` at use time. Removes five attributes from `server.py` and
   from three test fixtures.
4. **`jedi_tools` takes `interpreter: str | None`**, where `None` keeps today's default
   environment. Production always passes it; the ~13 existing jedi tests need no edit and
   the suite does not spawn 13 `CompiledSubprocess` children.
5. **`prefix` and `is_venv` dropped from the probe blob** — no consumer. `sys_path` stays
   (#228 names it), `distributions` stays (decision 15's error text, #61).

## Deviations from the issue, with reasons

- **The `tach.toml` edit for `inspect_library` moves from step 6b to step 3.** tach does
  not see `TYPE_CHECKING` imports (which is why it passes today despite fourteen
  back-edges), but step 3 gives `inspect_library` a **runtime** import of
  `mcp_tools_py.utils`. Deferring would leave step 3 red. `utility_tools` keeps its edit
  in step 7. #228 needs the same `inspect_library` line — whichever lands second must not
  duplicate it.
- **Steps 6 and 7 stay split** (issue decision 25). Simplification 3 removes much of the
  fixture churn, but step 6 still touches ~16 files; merging would make one ~24-file
  commit.
- **The `integration`-marked venv test moves from the end to step 4**, where both fixed
  tools first exist together.
- **`run_tests(bin_dir=...)` always prepends to `PATH` when given** (the open question
  from the discussion; option A). `bin_dir` always matches the interpreter actually
  running pytest, so prepending it is correct rather than incidental. The parameter
  defaults to `None` for standalone library use, which preserves today's behaviour there.

## Steps

| # | Title | Closes |
|---|---|---|
| 1 | `PythonEnvironment` value object | criteria 3, 4, 10 |
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
| `src/mcp_tools_py/code_checker_pytest/runners.py` | 1 |
| `src/mcp_tools_py/inspect_library.py` | 3, 5, 7 |
| `src/mcp_tools_py/refactoring/jedi_tools.py` | 4 |
| `src/mcp_tools_py/refactoring/__init__.py` | 4, 5, 7 |
| `src/mcp_tools_py/utility_tools.py` | 5, 7 |
| `src/mcp_tools_py/checker_tools/__init__.py` | 5, 6 |
| `src/mcp_tools_py/checker_tools/{pylint,pytest,mypy,ruff_check,ruff_fix,bandit,vulture,tach,lint_imports}_tool.py` | 5, 6 |
| `src/mcp_tools_py/formatter/formatter_tools.py` | 5, 6 |
| `.importlinter` | 2 (add contract), 5 (−4 entries), 6 (−2 entries) |
| `tach.toml` | 3 (`inspect_library`), 7 (`utility_tools`) |
| `README.md` | 3 |
| `vulture_whitelist.py` | 3, 7 (if needed) |
| `docs/architecture/architecture.md` | 7 |
| `tests/test_tool_availability.py` | 1, 2, 6 |
| `tests/test_inspect_library.py` | 3 |
| `tests/test_checker_tools.py` | 6 |
| `tests/test_code_checker/test_runners.py` | 1 |
| `tests/test_code_checker_bandit/test_integration.py` | 6 |
| `tests/test_refactoring/test_refactoring_tools.py` | 4, 7 |
| `tests/test_formatter_tools.py` | 6 |
| `tests/test_server_params.py` | 1 (`:83` `venv_path` kwarg), 6 (`_check_tool_availability`, `_is_tool_available`, `_resolved_python`) |

`pyproject.toml` needs **no** change: `[tool.setuptools.packages.find]` defaults to
`namespaces = true`, so `utils/target_scripts/` with an `__init__.py` is discovered and
its `.py` files ship in the wheel (criterion 8).

## Acceptance criteria → step

| Criterion | Step |
|---|---|
| `get_library_source` + `list_symbols` resolve through `--venv-path` | 3, 4 |
| `get_library_source` imports nothing in the server process | 3 |
| One `Scripts`/`bin` branch, not seven | 1 |
| Console-script tools found with only `--python-executable` | 1 |
| No `python -m <tool> --version` subprocess remains | 2 |
| All five registrars take the same argument type | 6, 7 |
| `lint-imports` and `tach` pass with six `ignore_imports` removed | 5, 6 |
| `probe.py` present in a built wheel | 2 |
| New contract fails when `probe.py` imports a project module | 2 |
| `main.py` help text no longer contradicts the resolution target | 1 |
