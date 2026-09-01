# Step 1 — Validate the resolved interpreter at startup

Implements **Decision 12**. See [summary.md](./summary.md) §8.

Replaces the venv-only existence check with one check on whatever
`_resolve_python_executable` returns, naming the flag that supplied the path.
Precedence is unchanged.

## WHERE

| File | Change |
|---|---|
| `src/mcp_tools_py/server.py` | `_resolve_python_executable` (currently `:91-113`) |
| `tests/test_tool_availability.py` | `TestResolvePythonExecutable` |

## WHAT

```python
def _resolve_python_executable(self) -> str:
    """Centralize venv -> python_executable -> sys.executable resolution.

    Returns:
        Path to the Python interpreter to use for tool subprocesses.

    Raises:
        FileNotFoundError: If the resolved interpreter does not exist.
    """
```

Signature unchanged. Only the body and the `Raises:` clause change.

## HOW

- Keep `os.path.join` and the `os.name == "nt"` branch for the venv case — six
  existing tests patch `mcp_tools_py.server.os.name` and
  `mcp_tools_py.server.os.path.exists`.
- Track which flag produced the path so the error names it.
- No new imports.

## ALGORITHM

```
if self.venv_path:
    python = join(venv_path, "Scripts/python.exe" if os.name == "nt" else "bin/python")
    source = "--venv-path"
elif self.python_executable:
    python, source = self.python_executable, "--python-executable"
else:
    python, source = sys.executable, "sys.executable"
if not os.path.exists(python):
    raise FileNotFoundError(f"Python interpreter not found: {python} (from {source})")
return python
```

## DATA

Returns `str`. Raises `FileNotFoundError` whose message contains both the path and
the originating flag name.

## TESTS (write first)

In `tests/test_tool_availability.py::TestResolvePythonExecutable`:

1. **Re-point** `test_venv_path_not_found_raises` — same construction, but the
   assertion now targets the resolved-interpreter check. Assert the message
   contains `--venv-path`.
2. **New** `test_python_executable_not_found_raises` — `python_executable` set to a
   path that does not exist, no `os.path.exists` patch, expect `FileNotFoundError`
   whose message contains `--python-executable`.
3. **Fix** `test_python_executable_fallback` (`:76-90`) — passes
   `/usr/local/bin/python3.11`, does not patch `os.path.exists`, so it now raises.
   Add `patch("mcp_tools_py.server.os.path.exists", return_value=True)`.
4. **Fix** `test_resolved_python_passed_to_pytest_runner`
   (`TestToolHandlerShortCircuit`, `:483-521`) — passes `/custom/python`, same
   problem, same fix.
5. `test_sys_executable_fallback` needs no change — `sys.executable` exists.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`.
>
> Implement Step 1 only: move the startup `FileNotFoundError` from the venv-only
> branch of `ToolServer._resolve_python_executable` onto the resolved interpreter,
> so a missing `--python-executable` fails at startup too. The error message must
> name the flag that supplied the path (`--venv-path`, `--python-executable`, or
> `sys.executable`). Resolution precedence is unchanged.
>
> Use `os.path.exists` and keep the `os.name == "nt"` branch — existing tests patch
> `mcp_tools_py.server.os.path.exists` and `mcp_tools_py.server.os.name`, and
> `pathlib` would silently defeat those patches.
>
> Write the tests first. Four tests in `tests/test_tool_availability.py` are
> affected: re-point `test_venv_path_not_found_raises`, add a
> `--python-executable` equivalent, and add an `os.path.exists` patch to
> `test_python_executable_fallback` and `test_resolved_python_passed_to_pytest_runner`
> (both pass fake interpreter paths and would otherwise start raising).
>
> Do not touch `_check_tool_availability`, `_is_tool_available`, any
> `checker_tools/*` module, or the docs — later steps own those.
>
> Then run, in order: `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`,
> `run_mypy_check`. All must pass. Commit as one commit.
