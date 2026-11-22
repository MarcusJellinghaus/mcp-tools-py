# Step 1 — `read_pytest_config` and the `PYTEST*` test-env scrub

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_1.md`), and
> issue #294 (decisions 7, 8, Constraints "Value types by table", "pytest's config
> file order", "Has a pytest section"). Implement step 1 only: write the tests first,
> then the code, run the checks listed in the summary, then commit (one commit).

## WHERE

- New: `src/mcp_tools_py/code_checker_pytest/pytest_config.py`
- New: `tests/test_code_checker_pytest/test_pytest_config.py`
- Modified: `tests/test_code_checker_pytest/conftest.py` (autouse fixture). Not
  `tests/conftest.py`: `tests/test_startup_time.py` reads
  `PYTEST_XDIST_WORKER_COUNT` at runtime to skip under xdist, so a repo-wide scrub
  would break it. All tests of this issue live in `tests/test_code_checker_pytest/`.

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

Autouse fixture in `tests/test_code_checker_pytest/conftest.py`:

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

- Uses `tomllib` and `os.path` only; reads `pyproject.toml` itself (catch
  `OSError`, `tomllib.TOMLDecodeError`, `UnicodeDecodeError` → `None`). Lives in
  `code_checker_pytest` (layer above `utils`), not in `utils/project_config.py`.
- `tox.ini` / `setup.cfg`: a line match (`line.strip() == "[pytest]"` /
  `"[tool:pytest]"`), no `configparser`.
- Not used by production code yet (step 3 does); vulture sees the tests.

## ALGORITHM

```
for name in DEDICATED_FILES: if isfile(root/name): return PytestConfig([], [], None, None, name)
tool = load(pyproject)["tool"] or {}  -> on error return None
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
- strict keys: bool and string spellings in `ini_options`; string in `[tool.pytest]`
  → `None`.
- each dedicated file → `not_read == name`, empty fields; first in order wins.
- `tox.ini [pytest]` → `not_read="tox.ini"` without pyproject section; with an empty
  `[tool.pytest.ini_options]` → no note; with only an empty `[tool.pytest]` → note.
- `setup.cfg [tool:pytest]` same rule; `tox.ini` without `[pytest]` → no note.
- invalid TOML → `None`; both tables non-empty → `None`; non-empty `[tool.pytest]`
  plus empty `ini_options` → reads `[tool.pytest]`.
- no `pyproject.toml` at all → `PytestConfig([], [], None, None)`.
- scrub fixture: a test asserting no `os.environ` name starting with `PYTEST`
  other than `PYTEST_CURRENT_TEST` is present.
