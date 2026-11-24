# Summary — #298 Size xdist `-n auto` workers by CPU load on Windows (`pytest_workers`)

## Goal

On Windows, `-n auto` currently starts a fixed number of workers no matter how busy the
machine is. After this change, `[mcp_tools_py] pytest_workers` in `~/.mcp_coder/config.toml`
defines what `-n auto` / `-n logical` means for a pytest run. The count reaches xdist through
`PYTEST_XDIST_AUTO_NUM_WORKERS` on the pytest subprocess. The command line and the project's
`addopts` are never rewritten. Replies get a `workers:` line, and `PythonToolkit.verify()`
gets a `pytest_workers` item.

The issue (#298) is the specification. This plan only fixes *where* and *how*.

## Architectural / design changes

| Change | Design |
|---|---|
| New shim `utils/user_app_data.py` | Re-exports `get_user_app_data_dir` from `mcp_coder_utils.user_app_data`. Added to `ignore_imports` of the `mcp_coder_utils_isolation` contract (`mcp_tools_py.utils.user_app_data -> mcp_coder_utils`). |
| New module `code_checker_pytest/workers.py` | The only new logic module. It holds the config loader, the platform seam, the raw `GetSystemTimes` wrapper, the exact math, the median sampler, the resolver and the verify data. Imports: `pytest_config` (same package), `utils.user_app_data`, stdlib. This satisfies tach (`code_checker_pytest` → `utils`, `log_utils`) and `.importlinter` (`utils` never imports `code_checker_pytest`). |
| `EffectiveConfig.n` | A new field `n: OptionValue | None`: the effective `-n` value and its source. `numprocesses: bool` stays (it still means "is the run parallel?"). |
| `check_code_with_pytest` | New optional parameter `effective: EffectiveConfig | None = None`, computed when absent, so `-n` is parsed once per run. It calls `resolve_workers` *before* its `try`, then passes the returned env (the caller's dict unchanged, or a copy with the variable added) to `run_tests`. Every return (success and exception) gets two new keys: `workers_note: str | None` and `workers_serial: bool`. `run_tests` is unchanged. |
| MCP tool `pytest_tool.py` | Passes `effective=`. Prepends `workers_note` before all other notes, and also on the outer `except` path. When `workers_serial` is true, it uses `dataclasses.replace(effective, numprocesses=False)` for `_defaults_may_explain` and `marker_notes`, so their signatures don't change. |
| Toolkit `toolkit.py` | `_run_test` combines `workers_note` and `test_paths_note` into the single note `_with_note` takes, and passes `effective=` at `full` depth. `verify()` adds `VerifyItem("pytest_workers", *pytest_workers_verify())` for `action` `None` / `"test"`, after `_build_context`'s early return. |
| `selection_identity` | Unchanged. The variable is added inside the runner, so the worker count never enters the coverage identity. |
| Test isolation | An autouse fixture in `tests/conftest.py` points `workers._config_path` at a missing file and patches `workers._is_windows` → `False` and `workers._get_system_times` → `None`. A `user_config` fixture writes a `config.toml` under `tmp_path` for tests that need one. |

### Rejected for simplicity
- A generic `utils/user_config.py` loader: it would have one consumer.
- A separate `cpu_load.py`: the issue requires only that the raw wrapper be a separate *function*.
- Returning a count: a serial flag is all the callers need.
- New parameters on `marker_notes` / `_defaults_may_explain`: `dataclasses.replace` covers it.

## `workers.py` — data and functions

```python
ENV_KEY = "PYTEST_XDIST_AUTO_NUM_WORKERS"

@dataclass(frozen=True)
class WorkersSetting:
    value: str | int        # "auto" | "all" | int >= 0  (fallback "auto")
    in_config: bool         # key present in config.toml, or config.toml unreadable/invalid
    problem: str | None     # text after "ignored ", e.g. 'pytest_workers = "x" in config.toml'
                            #   or "config.toml: invalid TOML"

@dataclass(frozen=True)
class WorkersPlan:
    env: dict[str, str] | None   # what run_tests gets
    serial: bool                 # resolved / pre-set count == 0
    note: str | None             # the "workers: ..." line, or None

_config_path() -> Path
read_pytest_workers() -> WorkersSetting                 # never raises
pytest_workers_verify() -> tuple[Literal["ok", "warning"], str, str | None]  # (status, message, hint), no sampling
_is_windows() -> bool                                   # platform seam
_get_system_times() -> tuple[int, int, int] | None      # (idle, kernel, user); the only Windows-only code
idle_fraction(before, after) -> Fraction | None
sample_idle(interval: float = 0.1) -> Fraction | None   # median of 5 deltas, exact
workers_for(logical: int, idle: Fraction) -> int        # (logical*num)//(2*den); < 2 -> 0
resolve_workers(effective, env_vars) -> WorkersPlan     # never raises
```

## `workers:` line rules (from the issue)

Count display: `serial` when the count is `0`, else the number.
Problem suffix: `; ignored <problem>`, appended inside the parentheses.

| Situation | Line |
|---|---|
| No effective `-n`, config not set | none |
| No effective `-n`, config set | `workers: no -n (pytest_workers applies to -n auto only)` |
| Numeric `-n V`, config not set | none |
| Numeric `-n V`, config set | `workers: <V or serial> (-n V from <src>; pytest_workers applies to -n auto only)`. `<src>` is `pyproject.toml addopts`, `-o addopts`, `PYTEST_ADDOPTS` or `extra_args`. |
| `auto`/`logical`, pre-set integer | `workers: <n> (PYTEST_XDIST_AUTO_NUM_WORKERS)` |
| `auto`/`logical`, pre-set non-integer | `workers: xdist default (PYTEST_XDIST_AUTO_NUM_WORKERS="x" is not an integer)` |
| value `"all"` | `workers: xdist default (all, config.toml)` |
| integer `N` | `workers: <N> (config.toml)` (variable set) |
| `auto`, not Windows | `workers: xdist default (auto, not Windows)` |
| `auto`, Windows, sampling failed or `os.cpu_count()` is None | `workers: xdist default (auto, Windows, CPU load unavailable)` |
| `auto`, Windows | `workers: <n> (auto, Windows, CPU load P %)` (variable set), with `P = round(100 * (1 - idle))` |

## Files created / modified

### Created
- `src/mcp_tools_py/utils/user_app_data.py` — shim
- `src/mcp_tools_py/code_checker_pytest/workers.py` — loader, sampler, resolver, verify data
- `tests/test_code_checker_pytest/test_workers_config.py` — loader + verify data
- `tests/test_code_checker_pytest/test_workers_cpu.py` — math, median, raw wrapper (Windows only)
- `tests/test_code_checker_pytest/test_workers_resolve.py` — resolver and every line format
- `tests/test_code_checker_pytest/test_workers_runner.py` — `check_code_with_pytest` wiring, no-restart
- `tests/test_code_checker_pytest/test_integration_workers.py` — real serial runs (`integration`)
- `tests/test_pytest_tool_workers.py` — MCP tool note placement and serial handling
- `docs/user-config.md`

### Modified
- `.importlinter`
- `src/mcp_tools_py/code_checker_pytest/pytest_config.py` — `EffectiveConfig.n`
- `src/mcp_tools_py/code_checker_pytest/runners.py` — `check_code_with_pytest`
- `src/mcp_tools_py/checker_tools/pytest_tool.py` — wiring + docstring
- `src/mcp_tools_py/toolkit.py` — `_run_test` note, `verify()` item
- `src/mcp_tools_py/toolkit_checks.py` — only if `toolkit.py` exceeds 750 lines (receives `_registered_markers`)
- `tests/conftest.py` — autouse isolation fixture + `user_config` fixture
- `tests/test_shim_reexports.py`
- `tests/test_code_checker_pytest/test_effective_config.py`
- `tests/test_server_params.py` — `effective=ANY` in `assert_called_once_with`
- `tests/test_toolkit_verify.py` — item count / name sets, new item tests
- `tests/test_toolkit_test.py` — workers note in `ActionResult`
- `README.md`, `docs/README.md`, `docs/upgrade-notes.md`, `docs/architecture/architecture.md`
- `.claude/CLAUDE.md`, `.claude/skills/implementation_review_supervisor/SKILL.md`, `.claude/skills/implement_direct/SKILL.md`

## Steps

1. Shim `utils/user_app_data.py` + import contract + shim docs
2. `EffectiveConfig.n`
3. `workers.py` config loader + verify data + test isolation fixtures
4. Toolkit `verify()` item `pytest_workers`
5. CPU sampler: seam, raw wrapper, exact math, median
6. Resolver `resolve_workers` + `workers:` line
7. Wire into `check_code_with_pytest` (+ integration tests)
8. Wire into the MCP tool `run_pytest_check`
9. Wire into the toolkit `_run_test`
10. User docs (`docs/user-config.md`, README, upgrade notes, architecture overview)
11. Agent guidance: remove the `-n auto` rule from CLAUDE.md and two skills

Every step ends with: `run_format_code`, pylint, pytest (`markers=["not integration"]`, plus the step's own integration tests when it adds any), mypy. All must pass.
