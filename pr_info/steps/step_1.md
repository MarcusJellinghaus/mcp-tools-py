# Step 1 — Timeout resolution core

Pure logic, no wiring. Nothing consumes it yet.

## WHERE

`src/mcp_tools_py/utils/project_config.py` — append to the existing module.
`tests/test_project_config.py` — append a new test class.

## WHAT

```python
ToolName = Literal[
    "mypy", "pylint", "pytest", "ruff", "bandit",
    "vulture", "tach", "lint-imports", "black", "isort",
]

DEFAULT_CHECK_TIMEOUT = 120
DEFAULT_PYTEST_TIMEOUT = 300

_CONFIG_SECTION = "mcp-tools-py"
_SHARED_TIMEOUT_KEY = "check-timeout"


def validate_timeout(value: object, source: str) -> int: ...


def get_check_timeout(
    project_dir: str,
    tool: ToolName,
    explicit: int | None = None,
    cli_timeout: int | None = None,
) -> int: ...


def _read_mcp_tools_section(project_dir: str) -> dict[str, object]: ...
```

## HOW

- `from typing import Literal` — the module already imports `os` and `tomllib`.
- Reuse the existing `tomllib` load idiom and the existing
  `raise ValueError(f"Invalid pyproject.toml: {exc}") from exc` wording from
  `get_target_directories`.
- Do **not** copy the fallback-with-warning idiom (`TargetDirs.warnings`). That warns
  because a missing section is unexpected; for timeouts a missing section is the normal
  case, so it would warn on every tool call for every project.
- No `int | str` companion wrapper — callers rely on the raise.

## ALGORITHM

`validate_timeout`:

```
if isinstance(value, bool) or not isinstance(value, int):
    raise ValueError(f"{source} must be a positive integer, got {value!r}")
if value <= 0:
    raise ValueError(f"{source} must be a positive integer, got {value}")
return value
```

`bool` is an `int` subclass, so `mypy-timeout = true` must be rejected explicitly.

`_read_mcp_tools_section`:

```
path = join(project_dir, "pyproject.toml")
if not isfile(path): return {}
open rb; tomllib.load -> on TOMLDecodeError raise ValueError(f"Invalid pyproject.toml: {exc}")
section = data.get("tool", {}).get(_CONFIG_SECTION)   # guarded with isinstance(dict)
return section if isinstance(section, dict) else {}
```

`get_check_timeout`:

```
if explicit is not None: return validate_timeout(explicit, "timeout_seconds")
section = _read_mcp_tools_section(project_dir)
for key in (f"{tool}-timeout", _SHARED_TIMEOUT_KEY):
    if key in section: return validate_timeout(section[key], f"[tool.{_CONFIG_SECTION}] {key}")
if cli_timeout is not None: return validate_timeout(cli_timeout, "--check-timeout")
return DEFAULT_PYTEST_TIMEOUT if tool == "pytest" else DEFAULT_CHECK_TIMEOUT
```

Unknown keys in the section are ignored — that is zero code, versus an allowlist
consulted on every tool call.

## DATA

`get_check_timeout` returns a positive `int`. It raises `ValueError` for: a malformed
`pyproject.toml`, an invalid value under a known key, an invalid `explicit`, or an
invalid `cli_timeout`.

## TESTS (write first)

New class `TestGetCheckTimeout` in `tests/test_project_config.py`, following the existing
`tmp_path` + `textwrap.dedent` pyproject-writing style in that file.

Chain (one test each, or parametrized):
- no pyproject.toml → 120; `tool="pytest"` → 300
- `cli_timeout=45` and no config → 45; `tool="pytest"` → 45
- `check-timeout = 200` beats `cli_timeout=45`
- `mypy-timeout = 600` with `check-timeout = 200` → 600 for mypy, 200 for pylint
- `explicit=90` beats every configured value
- `lint-imports-timeout = 30` resolves (hyphenated tool name)
- unknown key `nonsense = 1` in the section is ignored → 120

Validation:
- `explicit` of `0`, `-1` → `ValueError` mentioning `timeout_seconds`
- pyproject value of `0`, `-5`, `"600"`, `true` → `ValueError` naming the key
- malformed `pyproject.toml` → `ValueError` containing `Invalid pyproject.toml`
- section present but not a table → treated as absent

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`. Implement step 1 only.
>
> Write the tests in `tests/test_project_config.py` first, watch them fail, then add
> `ToolName`, the two default constants, `validate_timeout`, `_read_mcp_tools_section`
> and `get_check_timeout` to `src/mcp_tools_py/utils/project_config.py`.
>
> Do not wire anything up — no other source file changes in this step. Then run
> `run_format_code`, `run_pylint_check`, `run_pytest_check(extra_args=["-n","auto"])` and
> `run_mypy_check`, and commit once.
