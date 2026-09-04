# Step 7 — Remaining three registrars; document the invariant

One uniform registrar signature in place of today's three shapes, and the architecture
doc states the rule whose absence produced the bug.

**Acceptance criterion closed:** "All five registrars take the same argument type."

## WHERE

**Modified**
- `src/mcp_tools_py/refactoring/__init__.py` — `RefactoringTools`
- `src/mcp_tools_py/inspect_library.py` — `InspectTools`
- `src/mcp_tools_py/utility_tools.py` — `UtilityTools`
- `src/mcp_tools_py/server.py` — three call sites
- `tach.toml` — add `mcp_tools_py.utils` to `utility_tools`, then regenerate
  `docs/architecture/dependencies/dependency_graph.html` and `pydeps_graph.*`
- `docs/architecture/architecture.md` — the invariant, the single-environment sentence,
  and the module overview
- `vulture_whitelist.py` — only if vulture flags the unused parameter
- `tests/test_refactoring/test_refactoring_tools.py`,
  `tests/test_refactoring/test_rope_tools.py:506`, `tests/test_utility_tools.py`

## WHAT

```python
class RefactoringTools:
    def __init__(self, context: ToolContext, timeout: int = 120) -> None: ...

class InspectTools:
    def __init__(self, context: ToolContext) -> None: ...

class UtilityTools:
    def __init__(self, context: ToolContext) -> None: ...
```

`server.py`:

```python
CheckerTools(self.context).register(self.mcp)
FormatterTools(self.context).register(self.mcp)
RefactoringTools(self.context, timeout=self.refactoring_timeout).register(self.mcp)
UtilityTools(self.context).register(self.mcp)
InspectTools(self.context).register(self.mcp)
```

`refactoring_timeout` stays a separate argument rather than joining `ToolContext`: it is a
rope concern, not an environment or project concern, and only one registrar uses it.

`UtilityTools` accepts a `ToolContext` it does not use (decision 24) — the price of "all
five registrars take the same argument type", which is an acceptance criterion. If vulture
flags the unused parameter, add a `vulture_whitelist.py` entry; do not invent a use for it.

## HOW

`RefactoringTools` reads `context.project_dir` and
`str(context.environment.interpreter)`, passing the latter to `jedi_list_symbols` and
`jedi_find_references`. `rope_move_symbol` / `rename_symbol` / `move_module` are unchanged
— `rope_tools.py:444` keeps `sys.executable`, which is correct: that child must import
`mcp_tools_py`, which lives in the tool env (decision 12).

`InspectTools` reads `str(context.environment.interpreter)` and passes it to
`_get_library_source`, replacing the `PythonEnvironment` it took in step 3.

## `tach.toml`

`utility_tools` gains `mcp_tools_py.utils`:

```toml
[[modules]]
path = "mcp_tools_py.utility_tools"
layer = "tool_implementation"
depends_on = [
    { path = "mcp_tools_py.log_utils" },
    { path = "mcp_tools_py.utils" }
]
```

`inspect_library` already got its line in step 3 — **do not add it twice**. `refactoring`
already declares `mcp_tools_py.utils`. `.importlinter` needs no work: steps 5 and 6
deleted all six `ignore_imports` entries as they went.

## Documentation

`docs/architecture/architecture.md`:

1. **The invariant**, in *Cross-cutting Concepts* (section 8 begins at `:228`; put it near
   the Architecture Enforcement table at `:241-245`):

   > Any tool that resolves a Python name — module, symbol, or installed package —
   > resolves it through `ToolContext.environment`. Never through the ambient process,
   > never through `VIRTUAL_ENV`.

2. **Why there is one configurable environment**, in *Deployment View*: the checkers must
   import the project's dependencies, so they run in the project env; the same interpreter
   therefore resolves library and symbol lookups. Name the two environments explicitly —
   the **tool env** (`MCP_CODER_VENV_PATH`, where `mcp_tools_py` itself is installed, not
   configurable through the flags) and the **project env** (`--python-executable`, with the
   deprecated `--venv-path` still resolving the interpreter) — because the phrase "tool
   venv" has been used for both and that ambiguity is what made `main.py`'s help text
   backwards. `:224` already names both flags after #229; extend that bullet rather than
   adding a second one. Also update the dependency-rules bullets at `:134-139` if the new
   `utils` modules change what they say.

3. **Module overview**: add `utils/python_environment.py`, `utils/environment_info.py`,
   `utils/target_scripts/probe.py`, `utils/tool_context.py` and
   `utils/mcp_protocols.py`. Note the two non-interchangeable child idioms — `rope_cli`
   runs under `sys.executable` with `-m`, `probe.py` runs under the target interpreter by
   absolute path and is stdlib-only, enforced by the `target_scripts` contract.

4. Update the `.importlinter` sentence at `:248`: it says "three contracts"; there are now
   four, and the `ignore_imports` list is gone.

## DATA

No new data structures. The observable change from this step alone is nil — it is a
signature unification plus documentation.

## Tests

- `tests/test_refactoring/test_refactoring_tools.py` (`:36,46,100,120`) and
  `tests/test_refactoring/test_rope_tools.py:506` — constructor call sites take a
  `ToolContext` (second edit to these lines; step 4 made the first).
- `tests/test_utility_tools.py:16,37,63` — `UtilityTools()` becomes `UtilityTools(context)`.
- One new test asserting all five registrars accept the same `ToolContext`: build one
  context, construct all five, register against a mock MCP, and assert 17 tools are
  registered. This is the acceptance criterion expressed as a test.

Reuse the shared `ToolContext` fixture added to `tests/conftest.py` in step 6.

## Checks

`run_format_code`, `run_pylint_check`, `run_pytest_check`, `run_mypy_check`,
`run_lint_imports_check`, `run_tach_check`, `run_vulture_check`.

`docs/architecture/dependencies/readme.md` requires the generated graphs to be refreshed
after a `tach.toml` change: run `tools/tach_docs.bat` and `tools/pydeps_graph.bat` and
commit the updated `dependency_graph.html` and `pydeps_graph.*` with this step.

Then re-run the integration-marked tests once —
`run_pytest_check(extra_args=["-n","auto"], markers=["integration"])` — since the venv
test from step 4 now reaches `get_library_source` and `list_symbols` through the converted
registrars.

Finally, walk the ten acceptance criteria in `pr_info/steps/summary.md` and confirm each
one, and delete `.scratch/` if any probe was written.

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_7.md`, then implement step 7.
> Convert `RefactoringTools`, `InspectTools` and `UtilityTools` to take a `ToolContext`,
> update the three `server.py` call sites, add the `utility_tools` line to `tach.toml`
> (the `inspect_library` line already exists from step 3 — do not duplicate it), add the
> registrar-uniformity test, and write the architecture documentation described above.
> `UtilityTools` ignores its context by design; do not invent a use for it. Finish by
> checking off all ten acceptance criteria from the summary. One commit, all checks
> passing.
