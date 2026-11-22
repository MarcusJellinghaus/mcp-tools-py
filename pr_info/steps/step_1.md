# Step 1 — `read_pytest_config` and the `PYTEST*` test-env scrub

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_1.md`), and
> issue #294 (decisions 7, 8, Constraints "Value types by table", "pytest's config
> file order", "Has a pytest section"). Implement step 1 only: write the tests first,
> then the code, run the checks listed in the summary, then commit (one commit).

## WHERE

- New: `src/mcp_tools_py/code_checker_pytest/pytest_config.py`
- New: `tests/test_code_checker_pytest/test_pytest_config.py`
- Modified: `tests/conftest.py` (autouse fixture, next to `_clear_virtual_env`).
  Repo-wide, so every test reaching `effective_config` through `run_pytest_check`
  (`tests/test_pytest_tool_*.py`, `tests/test_server_params.py`, the toolkit tests,
  `tests/test_code_checker_pytest/`) is covered by this one fixture; no per-module
  scrubs.
- Modified: `tests/test_startup_time.py`. `_parallel_workers()` reads
  `PYTEST_XDIST_WORKER_COUNT` at runtime, which the scrub now removes. Take it
  once at import instead (module-level `_XDIST_WORKER_COUNT =
  int(os.environ.get("PYTEST_XDIST_WORKER_COUNT", "1"))`; xdist sets it before
  collection) and have `_parallel_workers()` return that. The three tests that
  set or delete the variable (`test_startup_budget_runs_without_tracing`,
  `…_skips_with_parallel_workers`, `…_runs_with_single_worker`) use
  `monkeypatch.setattr(<module>, "_XDIST_WORKER_COUNT", n)` instead of
  `setenv` / `delenv`.

## WHAT

```python
DEDICATED_FILES = ("pytest.toml", ".pytest.toml", "pytest.ini", ".pytest.ini")

@dataclass(frozen=True)
class PytestConfig:
    """What pyproject.toml says about pytest, or which other file pytest reads instead."""
    addopts: list[str]            # ini addopts tokens; [] when none
    markers: list[str]            # project marker names, in config order
    strict_markers: bool | None   # table value; None when unset or wrong type
    strict: bool | None           # table value; None when unset or wrong type
    not_read: str | None = None   # file pytest reads instead; then the fields above are empty

def read_pytest_config(project_dir: str) -> PytestConfig | None:
    """Read the project's pytest config. Never raises; None when it can't be read."""
```

Autouse fixture in `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _clear_pytest_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep PYTEST* variables from CI or the outer run out of these tests.

    PYTEST_CURRENT_TEST is set again by pytest for each test phase; it does not
    affect selection.
    """
    for name in [n for n in os.environ if n.upper().startswith("PYTEST")]:
        monkeypatch.delenv(name)
```

## HOW

- Reads `pyproject.toml` through the existing `read_pyproject_tool_tables(Path(project_dir))`
  (`utils/project_config.py`); no own `tomllib` reader. It returns `{}` for a
  missing file or no `[tool]` table → "no pyproject section": `tox.ini` /
  `setup.cfg` are still checked. `ValueError` (invalid TOML; `UnicodeDecodeError`
  is a subclass) or `OSError` → `None`. Dedicated-file and `tox.ini` / `setup.cfg`
  checks use `os.path`. Lives in `code_checker_pytest` (layer above `utils`), not
  in `utils/project_config.py`.
- `_parse_bool(value: str) -> bool | None` is defined here (pytest's bool spellings,
  case-insensitive; anything else → `None`) for the string strict keys in
  `ini_options`; step 2 reuses it.
- `tox.ini` / `setup.cfg`: a line match (`line.strip() == "[pytest]"` /
  `"[tool:pytest]"`), no `configparser`.
- Not used by production code yet (step 3 does); vulture sees the tests.

## ALGORITHM

```
for name in DEDICATED_FILES: if isfile(root/name): return PytestConfig([], [], None, None, name)
tool = read_pyproject_tool_tables(Path(dir))  -> {} when missing; ValueError/OSError: return None
ini, native = tool.pytest.ini_options (dict|None), tool.pytest minus "ini_options" (dict)
if ini and native: return None                       # pytest rejects both non-empty
if ini is None and not native: check tox.ini [pytest], then setup.cfg [tool:pytest] -> not_read
table = ini if ini is not None else native; read addopts / markers / strict keys by table type
```

## DATA — value types per table

| key | `ini_options` | `[tool.pytest]` |
|---|---|---|
| `addopts` | str → `shlex.split` (ValueError → `[]`); list → `[str(v) …]` | list only; a str is ignored |
| `markers` | list, or multi-line str split on lines (strip, skip blank) | list only |
| `strict_markers`, `strict` | bool, or str in `true/false yes/no 1/0 on/off t/f y/n` (case-insensitive) | bool only |

Marker name = text before the first `(` or `:`, stripped. "Has a pytest section" =
an `ini_options` table (even empty) or a non-empty `[tool.pytest]` (ignoring the
`ini_options` key).

## Tests (write first) — `test_pytest_config.py`

- string and list `addopts` in `ini_options`; list `addopts` in `[tool.pytest]`;
  string `addopts` in `[tool.pytest]` → `[]`.
- `markers` list / multi-line string; `"slow: desc"` and `"x(arg): d"` → names.
- strict keys: bool and string spellings in `ini_options` (via `_parse_bool`);
  string in `[tool.pytest]` → `None`; unknown spelling → `None`.
- each dedicated file → `not_read == name`, empty fields; first in order wins.
- `tox.ini [pytest]` → `not_read="tox.ini"` without pyproject section; with an empty
  `[tool.pytest.ini_options]` → no note; with only an empty `[tool.pytest]` → note.
- `setup.cfg [tool:pytest]` same rule; `tox.ini` without `[pytest]` → no note.
- invalid TOML → `None` (the `ValueError` from `read_pyproject_tool_tables`);
  `read_pyproject_tool_tables` patched to raise `OSError` → `None`; both tables
  non-empty → `None`; non-empty `[tool.pytest]` plus empty `ini_options` → reads
  `[tool.pytest]`.
- no `pyproject.toml` at all (`{}`) → `PytestConfig([], [], None, None)`;
  `pyproject.toml` without a `[tool]` table → same.
- no `pyproject.toml`, only `tox.ini [pytest]` → `not_read == "tox.ini"`; no
  `pyproject.toml`, only `setup.cfg [tool:pytest]` → `not_read == "setup.cfg"`.
- scrub fixture: a test asserting no `os.environ` name starting with `PYTEST`
  other than `PYTEST_CURRENT_TEST` is present.
- `tests/test_startup_time.py`: the existing tests, adapted to
  `monkeypatch.setattr(…, "_XDIST_WORKER_COUNT", …)`, still pass.
