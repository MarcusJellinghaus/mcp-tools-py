# Step 2 — `--check-timeout` CLI and `ToolServer.resolve_timeout`

Plumbing only. After this step the setting is resolvable but no subprocess uses it yet.

## WHERE

- `src/mcp_tools_py/main.py`
- `src/mcp_tools_py/server.py`
- `tests/test_server_params.py` — new tests
- `tests/test_checker_tools.py`, `tests/test_formatter_tools.py` — `mock_server` fixtures

## WHAT

`main.py`:

```python
def _positive_timeout(value: str) -> int:
    """Parse --check-timeout as a positive integer.

    Raises:
        argparse.ArgumentTypeError: If the value is not a positive integer.
    """
```

```python
parser.add_argument(
    "--check-timeout",
    type=_positive_timeout,
    default=None,
    help=(
        "Timeout in seconds for every checker and formatter subprocess "
        "(default: 120, pytest 300). A per-tool value in [tool.mcp-tools-py] "
        "in the project's pyproject.toml overrides it"
    ),
)
```

`server.py`:

```python
class ToolServer:
    def __init__(self, ..., check_timeout: int | None = None) -> None: ...

    def resolve_timeout(self, tool: ToolName, explicit: int | None = None) -> int:
        """Resolve the subprocess timeout in seconds for one program.

        Returns:
            Positive number of seconds.

        Raises:
            ValueError: If pyproject.toml is malformed or a configured value is invalid.
        """
        return get_check_timeout(
            str(self.project_dir), tool, explicit, self.check_timeout
        )


def create_server(..., check_timeout: int | None = None) -> ToolServer: ...
```

## HOW

- Add `check_timeout` **last** in both signatures, after `vulture_whitelist`. Every
  parameter there is keyword-with-default, so appending is safe.
- `main()` passes `check_timeout=args.check_timeout` to `create_server`.
- `server.py` imports `ToolName` and `get_check_timeout` from
  `mcp_tools_py.utils.project_config`. `server → utils` is already declared in
  `tach.toml`.
- `main.py` keeps `_positive_timeout` self-contained and does **not** import
  `validate_timeout`. `tach.toml` declares `main → server` only; importing `utils` would
  need a new edge for two saved lines. Use the same message wording as
  `validate_timeout` so the two surfaces read alike.
- `default=None` is required: a CLI default of 120 sits above the built-in in the chain
  and would make pytest's 300s unreachable.
- Do not modify `tach.toml` or `.importlinter`.

## ALGORITHM

`_positive_timeout`:

```
try: parsed = int(value)
except ValueError: raise ArgumentTypeError(f"--check-timeout must be a positive integer, got {value!r}")
if parsed <= 0: raise ArgumentTypeError(same message)
return parsed
```

One message covers both failure modes.

## DATA

`args.check_timeout` is `int | None`. `ToolServer.check_timeout` is `int | None`.
`resolve_timeout` returns a positive `int`.

## TESTS (write first)

`tests/test_server_params.py`:
- `parse_args` with no flag → `args.check_timeout is None`
- `parse_args --check-timeout 600` → `600`
- `parse_args --check-timeout 0` and `--check-timeout abc` → `SystemExit`
  (argparse exits on `ArgumentTypeError`)
- `ToolServer(project_dir=..., check_timeout=45).resolve_timeout("mypy") == 45` and
  `.resolve_timeout("pytest") == 45` — patch `mcp.server.fastmcp.FastMCP` as the existing
  tests in this file do
- with no `check_timeout`, `resolve_timeout("mypy") == 120` and
  `resolve_timeout("pytest") == 300`
- a `tmp_path` project with `[tool.mcp-tools-py] mypy-timeout = 600` beats
  `check_timeout=45`

Follow the `--refactoring-timeout` argparse tests at
`tests/test_refactoring/test_rope_tools.py:432-457` for the `parse_args` pattern.

## ALSO IN THIS STEP — prepare the two `mock_server` fixtures

Both fixtures are bare `MagicMock`s, so `server.resolve_timeout("tach")` would return a
`MagicMock` and every later step's assertion would be meaningless. Add to
`tests/test_checker_tools.py::mock_server` and
`tests/test_formatter_tools.py::mock_server`:

```python
server.resolve_timeout = lambda tool, explicit=None: (
    300 if tool == "pytest" else 120
)
```

Doing it once here keeps steps 3–11 free of fixture edits.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_2.md`. Implement step 2 only.
>
> Write the `tests/test_server_params.py` tests first, then add `_positive_timeout` and
> the `--check-timeout` option to `src/mcp_tools_py/main.py`, and `check_timeout` plus
> `resolve_timeout` to `src/mcp_tools_py/server.py`. Also add the `resolve_timeout`
> lambda to the `mock_server` fixtures in `tests/test_checker_tools.py` and
> `tests/test_formatter_tools.py`.
>
> No checker, runner or formatter file changes in this step, and do not touch `tach.toml`
> or `.importlinter`. Then run `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n","auto"])` and `run_mypy_check`, and commit once.
