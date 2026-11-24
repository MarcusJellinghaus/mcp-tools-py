# Step 3 — `workers.py`: config loader, verify data, test isolation fixtures

## LLM prompt
Read `pr_info/steps/summary.md`, then implement **this step only** (`pr_info/steps/step_3.md`).
First add the fixtures to `tests/conftest.py` and the tests in `tests/test_code_checker_pytest/test_workers_config.py`. Then create `src/mcp_tools_py/code_checker_pytest/workers.py` with the loader and the verify-data function only (the sampler and resolver come in steps 5–6).
Run `run_format_code`, pylint, pytest (`markers=["not integration"]`), mypy, lint-imports and tach; all must pass. Make one commit.

## WHERE
- Create `src/mcp_tools_py/code_checker_pytest/workers.py`
- Create `tests/test_code_checker_pytest/test_workers_config.py`
- Modify `tests/conftest.py`

## WHAT
```python
"""Size pytest-xdist's `-n auto` from [mcp_tools_py] pytest_workers in ~/.mcp_coder/config.toml."""

ENV_KEY = "PYTEST_XDIST_AUTO_NUM_WORKERS"
_SECTION, _KEY = "mcp_tools_py", "pytest_workers"
VALID_VALUES_HINT = 'Valid values: "auto", "all", or an integer >= 0 (0 = serial).'

@dataclass(frozen=True)
class WorkersSetting:
    value: str | int      # "auto" | "all" | int >= 0
    in_config: bool       # key present, or config.toml unreadable / invalid
    problem: str | None   # text that follows "ignored " on the workers: line

def _config_path() -> Path: ...           # get_user_app_data_dir("mcp_coder") / "config.toml"
def read_pytest_workers() -> WorkersSetting: ...
def pytest_workers_verify() -> tuple[str, str, str | None]: ...  # (status, message, hint)
```

## HOW
- Import `get_user_app_data_dir` from `mcp_tools_py.utils.user_app_data` (the step-1 shim). Never import `mcp_coder_utils`.
- Read with `open(path, "rb")` + `tomllib.load`, as `utils/project_config.py` does. Do not use `utils.file_utils.read_file`.
- `_config_path()` is called **inside** the guarded block.
- Log invalid values / files with `logger.warning(...)` (`logging.getLogger(__name__)`).
- No caching: read on every call.

## ALGORITHM
```
try: data = tomllib.load(open(_config_path(), "rb"))
except FileNotFoundError: return WorkersSetting("auto", False, None)
except (TOMLDecodeError, UnicodeDecodeError): warn; return WorkersSetting("auto", True, "config.toml: invalid TOML")
except (OSError, RuntimeError): warn; return WorkersSetting("auto", True, "config.toml: unreadable")
section = data.get("mcp_tools_py"); if section is not a dict: section = {}   # missing / non-table → key missing
if key missing: return ("auto", False, None)
value valid ("auto" | "all" | int >= 0 and not bool) → (value, True, None)
else: warn; return ("auto", True, f"pytest_workers = {json.dumps(value, default=str)} in config.toml")
```
Order matters: `FileNotFoundError` is an `OSError`, so catch it first.

`pytest_workers_verify()`:
```
s = read_pytest_workers()
if s.problem is None: return ("ok", f"{s.value} ({'config.toml' if s.in_config else 'default'})", None)
hint = VALID_VALUES_HINT if s.problem.startswith("pytest_workers") else "Fix or remove ~/.mcp_coder/config.toml."
return ("warning", f"ignored {s.problem}; using auto", hint)
```
No CPU sampling here.

## DATA
- `read_pytest_workers()` examples:
  - missing file → `WorkersSetting("auto", False, None)`
  - `pytest_workers = 4` → `(4, True, None)`
  - `pytest_workers = "4"` → `("auto", True, 'pytest_workers = "4" in config.toml')`
  - `pytest_workers = true` → `("auto", True, 'pytest_workers = true in config.toml')`
  - `pytest_workers = -1` → invalid
  - broken TOML → `("auto", True, "config.toml: invalid TOML")`
- `pytest_workers_verify()` messages: `auto (default)`, `all (config.toml)`, `4 (config.toml)`; warnings as above.

## Fixtures in `tests/conftest.py`
```python
_WORKERS = "mcp_tools_py.code_checker_pytest.workers"
_NO_USER_CONFIG = Path(__file__).parent / "_no_user_config" / "config.toml"  # never created

@pytest.fixture(autouse=True)
def _isolate_pytest_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never read the developer's ~/.mcp_coder/config.toml."""
    monkeypatch.setattr(f"{_WORKERS}._config_path", lambda: _NO_USER_CONFIG)

@pytest.fixture
def user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], Path]:
    """Write a config.toml under tmp_path and point the loader at it; call again to change it."""
    path = tmp_path / "user_config" / "config.toml"
    path.parent.mkdir()
    monkeypatch.setattr(f"{_WORKERS}._config_path", lambda: path)
    def write(text: str) -> Path:
        path.write_text(text, encoding="utf-8")
        return path
    return write
```
Pass the setter target as a string (`"module.attr"`), so `conftest.py` doesn't import `workers` before monkeypatching.

## Tests (write first) — `test_workers_config.py`
- Missing file → `("auto", False, None)`, and no warning logged (`caplog`).
- Valid: `"auto"`, `"all"`, `0`, `4`, `64` (not capped).
- Invalid: `"4"`, `"x"`, `true`, `-1`, `1.5` → fallback `auto`, `in_config` True, problem text, warning logged.
- Section missing / key missing → default. `[mcp_tools_py]` given as a non-table → default.
- Invalid TOML and a non-UTF-8 file → `config.toml: invalid TOML`.
- `_config_path` raising `RuntimeError` (monkeypatch it with a raising lambda) → `config.toml: unreadable`; never raises.
- Real `_config_path()` body. The autouse fixture replaces `_config_path` in every test, so capture the real function at module import time, before the fixture runs (as step 5 does for `_get_system_times`):
  `from mcp_tools_py.code_checker_pytest.workers import _config_path as real_config_path`.
  - Patch `workers.get_user_app_data_dir` with a fake that records its argument and returns `tmp_path`. Assert that `real_config_path() == tmp_path / "config.toml"` and that the fake was called with `"mcp_coder"`. This proves that the path goes through the shim name imported into `workers`.
  - Restore the real function with `monkeypatch.setattr(workers, "_config_path", real_config_path)`, and patch `workers.get_user_app_data_dir` to raise `RuntimeError`. Then `read_pytest_workers()` returns `("auto", True, "config.toml: unreadable")`, logs a warning and does not raise. This proves that the path is resolved inside the guarded block.
- Changed file between two calls → second call sees the new value (no caching).
- `pytest_workers_verify()`: ok messages for default / `all` / `4`; warning + `VALID_VALUES_HINT` for an invalid value; warning with the config-file hint for invalid TOML.
