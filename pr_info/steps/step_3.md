# Step 3 — `get_library_source` runs in a child process

**The reported bug closes here.** The resolution logic moves verbatim into `probe.py`;
the parent gains a timeout where it previously could hang the server indefinitely.

**Acceptance criteria closed:** "`get_library_source` no longer imports anything in the
server process", and the `get_library_source` half of "resolves through
`--python-executable`".

## WHERE

**Modified**
- `src/mcp_tools_py/utils/target_scripts/probe.py` — add the `source` subcommand
- `src/mcp_tools_py/inspect_library.py` — parent side
- `src/mcp_tools_py/server.py:116` — `InspectTools(self.environment)`
- `tach.toml` — add `{ path = "mcp_tools_py.utils" }` to the `inspect_library` module, then
  regenerate the dependency graphs (see Checks)
- `README.md` — tool table entry (`:449`), the `--python-executable` row (`:103`), the
  **Environment Configuration** section (`:133-181`) and the **Troubleshooting** section
  (`:185-188`)
- `vulture_whitelist.py:75-76` — drop the orphaned `_.b` / `_.c`
- `tests/test_inspect_library.py`

## WHAT

```python
# probe.py — second subcommand, same file, same invocation convention
def _source(import_path: str, max_lines: int) -> str: ...

# inspect_library.py
def _get_library_source(import_path: str, max_lines: int, interpreter: str) -> str: ...

class InspectTools:
    def __init__(self, environment: PythonEnvironment) -> None: ...
```

`interpreter` is **required**, not defaulted. A default would silently reproduce the
exact bug being fixed. Step 7 converts `InspectTools` to take `ToolContext`.

## ALGORITHM — child

Move the current body of `_get_library_source` (`inspect_library.py:14-99`) into
`probe.py` unchanged: the backwards walk for the longest importable module prefix, the
`getattr` chain, the available-symbols listing capped at 50, the `inspect.getsource`
call, the built-in/C-extension message, and the truncation footer. Semantics do not
change (decision 6) — the ten surviving tests are the contract that proves it.

Two child-side details:

```
sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # source may be non-ASCII
sys.stdout.write(text)                                        # no trailing newline added
```

`max_lines` validation stays in the **parent** — it is argument validation and needs no
environment, so it should not cost a subprocess.

## ALGORITHM — parent

```
_get_library_source(import_path, max_lines, interpreter):
    if max_lines < 1: return f"max_lines must be a positive integer (>= 1), got: {max_lines}"
    result = execute_command([interpreter, str(probe_script_path()), "source",
                              import_path, str(max_lines)],
                             timeout_seconds=SOURCE_TIMEOUT_SECONDS)
    if result.timed_out:        return f"Error: resolving '{import_path}' timed out after {N}s"
    if result.execution_error:  return f"Error: could not run {interpreter}: {result.execution_error}"
    if result.return_code != 0: return f"Error resolving '{import_path}' (exit {rc}): {stderr snippet}"
    return result.stdout
```

`SOURCE_TIMEOUT_SECONDS = 30`, module-level in `inspect_library.py`. Return stdout
verbatim so the child's output is the tool's output.

## DATA

Unchanged strings: source text, the truncation footer, `"Module '<x>' not found"`,
`"'<attr>' not found in module '<mod>'.\n\nAvailable symbols:\n..."`, the built-in
message, the `max_lines` message. New: three error strings for timeout, unrunnable
interpreter, and non-zero exit.

## HOW — `tach.toml`

`inspect_library` currently declares only `log_utils`. Step 3 gives it a **runtime**
import of `mcp_tools_py.utils` (for `probe_script_path` and `execute_command`), so:

```toml
[[modules]]
path = "mcp_tools_py.inspect_library"
layer = "tool_implementation"
depends_on = [
    { path = "mcp_tools_py.log_utils" },
    { path = "mcp_tools_py.utils" }
]
```

The issue puts this edit in step 6b, but tach does not see `TYPE_CHECKING` imports —
which is why it passes today despite fourteen back-edges — and this one is a runtime
import. Deferring it would leave this step red. Issue #228 needs the same line; whichever
lands second must not duplicate it.

## HOW — `README.md` and `vulture_whitelist.py`

`README.md` carries the same backwards guidance step 1 fixes in `main.py`, in four places.
All four must change in this step, or the README documents the opposite of the invariant
this issue establishes — and its worked "Incorrect Configuration" example becomes the only
configuration under which `get_library_source` resolves correctly.

1. **`:449`** — extend the `get_library_source` row to say the path is resolved in the
   project's configured environment, e.g. "Resolves a dotted import path in the configured
   project environment and returns its source".

2. **`:103`** — the `--python-executable` row ends with "the environment where they are
   installed (the tool's own venv), not the project's runtime venv". Replace with the
   project env: the flag names the environment holding the project's dependencies, which is
   where the checkers run *and* where library and symbol lookups resolve. Leave `:104`
   alone — #229 replaced the old `--venv-path` row with a deprecation notice that says
   nothing about which venv to pick.

3. **`:133-181`, the Environment Configuration section** — `:135` states the flag "must
   point to the environment where **the checker tools are installed** … typically the tool's
   own virtual environment, not your project's runtime venv"; `:141` introduces the correct
   example as "the venv where mcp-tools-py and its tools are installed", which names the
   **tool** env; and `:165` labels a project `.venv` (`:174`) as "Incorrect Configuration".
   After this change that example is what the fix requires. Rewrite the section to say:

   - There is **one** configurable environment, the **project env**: the venv holding the
     project's dependencies *and* the checker tools. The checkers must import the
     project's dependencies (pytest, pylint and mypy all do), so the two cannot be
     separated — decision 5.
   - The **tool env**, where `mcp_tools_py` itself is installed, is a different
     environment and is **not** configured through this flag.
   - Library and symbol resolution (`get_library_source`, `list_symbols`,
     `find_references`) now follow the same interpreter, so pointing the flag at the
     wrong venv makes those tools resolve against the wrong packages.

   Keep the `${VIRTUAL_ENV}` examples (`:150`, `:160`) as the correct ones — the JSON was
   always right; only the prose labelling them "the tool's own venv" was wrong. Replace the
   "Incorrect Configuration" block at `:163-181`: a project `.venv` **without** the checker
   tools installed is the real failure, not a project `.venv` as such. `:181` ("This will
   fail if your project's `.venv` doesn't have the required tools installed") is the
   sentence that already says this correctly — build the replacement around it.

4. **`:185-188`, the Troubleshooting section** added by #229 — two of its four bullets,
   `:186` and `:187`, tell the reader to point `--python-executable` at "an environment
   where they are installed", which under decision 5 must name the project env
   specifically. Bring those two into line with the section above; `:185` and `:188` carry
   no framing and stay.

Use the same wording as step 1's `main.py` help string so the two do not drift.

`vulture_whitelist.py:75-76` — delete `_.b` and `_.c` (mock attributes for the tests being
removed). **Keep** `_.get_library_source` at `:69`.

## Tests

Rewrite `tests/test_inspect_library.py`:

**Delete** the three mocked classes — `TestParseImportPath` (`:11-59`), `TestTruncation`
(`:62-103`) and `TestErrorHandling` (`:105-158`). They patch
`mcp_tools_py.inspect_library.importlib` / `.inspect`, which the parent no longer calls.

**Keep** the two parametrized tests at `:160-174` — `test_max_lines_invalid_returns_error`
and `test_empty_or_malformed_import_path`. They currently sit *inside* `TestErrorHandling`
and must be re-homed, not deleted with it.

**Keep** `TestRealImports` (`:177-231`, eight tests) unchanged in substance. With the two
above, ten unmocked tests survive and are the contract proving the move preserves
semantics.

All ten need a call-site edit for the new required parameter. Use one helper so the edit
is mechanical and the interpreter choice is explicit:

```python
def _src(import_path: str, max_lines: int = 200) -> str:
    return _get_library_source(import_path, max_lines, sys.executable)
```

**New parent-side tests** (patch
`mcp_tools_py.inspect_library.execute_command`, use `make_command_result`):

1. Timeout → message naming the import path, no exception.
2. Non-zero exit → message including the exit code and a stderr snippet.
3. Missing interpreter (`execution_error` set) → message naming the interpreter.
4. Success → stdout returned verbatim, with no added or stripped characters.
5. `max_lines=0` short-circuits — `execute_command` is **not** called.
6. The command is built as `[interpreter, <abs probe path>, "source", path, str(max_lines)]`
   with the interpreter passed in, never `sys.executable` from the module.

## Checks

`run_format_code`, `run_pylint_check`, `run_pytest_check`, `run_mypy_check`,
`run_lint_imports_check`, `run_tach_check` (needs the `tach.toml` edit above),
`run_vulture_check` (needs the whitelist edit).

`docs/architecture/dependencies/readme.md` requires the generated graphs to be refreshed
after a `tach.toml` change: run `tools/tach_docs.bat` and `tools/pydeps_graph.bat` and
commit the updated `dependency_graph.html` and `pydeps_graph.*` with this step.

**Manual verification worth doing once:** point a server at a venv holding a package the
tool env lacks and confirm `get_library_source` returns its source. That is the reported
bug.

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_3.md`, then implement step 3.
> Rewrite `tests/test_inspect_library.py` first — delete the three mocked classes, re-home
> the two parametrized tests, keep `TestRealImports`, add the six parent-side tests — then
> move the resolution logic verbatim from `inspect_library.py` into a `source` subcommand
> in `probe.py`, then rewrite the parent. Update `tach.toml` (regenerating the dependency
> graphs) and `vulture_whitelist.py` as described, and fix `README.md` in all four places —
> the tool-table row, the `--python-executable` row, the Environment Configuration section
> (which still tells users to point the flag at the tool's own venv and labels the project
> `.venv` as incorrect) and the Troubleshooting bullets. The ten surviving tests must pass
> with no assertion
> changes; if one needs its assertion changed, the move was not verbatim. One commit, all
> checks passing.
