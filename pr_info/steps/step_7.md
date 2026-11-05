# Step 7: Add the coverage store: hashes, save, load, clear

**Commit:** `feat(coverage): add the saved coverage store`

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_7.md`. Implement step 7 only: write the tests first, then the code, make pylint, pytest and mypy pass, format, and produce one commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/coverage_store.py` (new)
- `src/mcp_tools_py/utils/project_config.py`
- `tests/test_code_checker_pytest/test_coverage_store.py` (new)
- `tests/test_project_config.py`

## WHAT

In `project_config.py`:

```python
def get_test_directories(project_dir: str) -> list[str]: ...
    # _load_pyproject + _read_test_dirs; raises ValueError on invalid pyproject.toml
```

In `coverage_store.py`:

```python
STORE_DIR = os.path.join(".mcp-tools-py", "coverage")
METADATA_FILE = "last_run.json"
STORE_VERSION = 1

def freshness_roots(project_dir, coverage_source: list[str] | None, test_folder: str) -> list[str]: ...
def hash_python_files(project_dir: str, roots: list[str]) -> dict[str, str]: ...
def load_saved(project_dir: str) -> dict[str, Any] | None: ...
def write_saved(project_dir: str, saved: dict[str, Any], new_data_file: str | None) -> None: ...
def clear_saved(project_dir: str) -> None: ...
```

## HOW

- This step has no callers yet. Step 8 wires it in, so don't add these names to `vulture_whitelist.py`.
- `write_saved` sets the newest run's `data_file` and adds `version`. Everything else in `saved` comes from the caller. See the structure in the summary.
- `json.dumps(saved, separators=(",", ":"))` keeps the file compact whatever the target's `[json] pretty_print` is.

## ALGORITHM

```
freshness_roots: resolve_coverage_source(project_dir, None), or [] if it returns an error string
    + explicit coverage_source + get_test_directories (ValueError -> []) + [test_folder]
    dedupe by norm_path, keep existing directories only
hash: os.walk each root, in place prune hidden dirs, __pycache__ and dirs containing pyvenv.cfg
    sha256 each .py with hashlib.file_digest; key is the POSIX path relative to project_dir
    an OSError on one file stores "unreadable" and doesn't raise
write_saved: makedirs; write .gitignore ("*") if absent
    if new_data_file exists: copy to run-<uuid4>.coverage, set runs[-1]["data_file"], else None
    write a unique temp file in the store directory; os.replace it to last_run.json
    delete every run-*.coverage not referenced by runs; temp file removed if the replace fails
```

## DATA

- `load_saved` returns the dict, or `None` when the file is absent, not valid JSON, not a dict, has a different `version`, lacks any of `report`, `hashes`, `roots`, `sources`, `fail_under`, `runs`, or has the wrong shape. The right shape is: `report` is a dict with a dict under `files`; `hashes` is a dict; `roots` and `sources` are lists; `runs` is a list of dicts, each with `selection`, `data_file`, `failed_collectors`, `failed_tests` and `generic_warning`. This is the only guard against corrupt metadata, because the reuse branch (step 9) sits outside the tool's `try`.
- `clear_saved` does `shutil.rmtree` on the store directory when it exists and creates nothing otherwise. Its `OSError` propagates to the caller.
- `write_saved` lets `OSError` propagate too. Step 8 turns that into a one-line note.

## TESTS

`test_coverage_store.py`, using real files in `tmp_path`:

- Roots: source, explicit directory, test directories and `test_folder`; a package name in `coverage_source` is skipped; `where = ["."]` with explicit `coverage_source` doesn't include `.` and doesn't raise.
- Hashing prunes `.venv` (a directory holding `pyvenv.cfg`), hidden directories and `__pycache__`, and ignores non-`.py` files.
- Editing, adding and deleting a file each change the mapping.
- Keys use forward slashes.
- Round trip: `write_saved` then `load_saved` returns the same data, and the file holds no newline even with a pretty-printed input.
- `.gitignore` containing `*` exists after a save and is recreated if deleted.
- A missing `new_data_file` is tolerated (`data_file` is `None`).
- The data file gets a unique name, and an unreferenced `run-*.coverage` is deleted after the replace, while a referenced one stays.
- Parametrized `load_saved` → `None`: no file, corrupt JSON, a JSON list, a wrong version, a missing key, `report` not a dict, `report` with no `files`, `files` not a dict, `runs` not a list, a run entry that isn't a dict, a run entry missing a key.
- `clear_saved` removes the data; on a project with no store it creates nothing.

`test_project_config.py`: `get_test_directories` returns `testpaths`, falls back to `["tests"]`, and raises `ValueError` on invalid TOML.
