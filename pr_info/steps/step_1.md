# Step 1 — Shim `utils/user_app_data.py` + import contract + shim docs

## LLM prompt
Read `pr_info/steps/summary.md`, then implement **this step only** (`pr_info/steps/step_1.md`).
Write the test first, then the shim, then update `.importlinter` and the docs listed below.
Run `run_format_code`, pylint, pytest (`markers=["not integration"]`), mypy and lint-imports; all must pass. Make one commit.

## WHERE
- Create `src/mcp_tools_py/utils/user_app_data.py`
- Modify `.importlinter` (`mcp_coder_utils_isolation` → `ignore_imports`)
- Modify `tests/test_shim_reexports.py`
- Modify `.claude/CLAUDE.md` (shim table under "Shared libraries")
- Modify `docs/architecture/architecture.md` (two "three shim modules" places + Module Overview)

## WHAT
```python
"""Per-user app-data directory — thin re-export shim over mcp_coder_utils.user_app_data."""

from mcp_coder_utils.user_app_data import get_user_app_data_dir  # noqa: F401

__all__ = ["get_user_app_data_dir"]
```
Follow the style of `utils/file_utils.py`.

## HOW
- `.importlinter`: add `mcp_tools_py.utils.user_app_data -> mcp_coder_utils`. Target the top-level package, because `include_external_packages = True` collapses externals.
- Test (write first):
  ```python
  def test_user_app_data_reexport() -> None:
      from mcp_coder_utils.user_app_data import get_user_app_data_dir as upstream
      from mcp_tools_py.utils.user_app_data import get_user_app_data_dir
      assert get_user_app_data_dir is upstream
  ```
- `.claude/CLAUDE.md` shim table: add the row
  `| User app-data dir (`get_user_app_data_dir`) | `mcp_tools_py.utils.user_app_data` |`.
- `docs/architecture/architecture.md`:
  - Dependency Rules bullet (~line 142) and the Architecture Enforcement paragraph (~line 283): replace "three shim modules" with the four shims (`log_utils`, `utils/file_utils.py`, `utils/subprocess_runner.py`, `utils/user_app_data.py`). Also say that `toolkit` and `toolkit_checks` import `mcp_coder_utils` directly and are exempted in `ignore_imports`. Replace the wrong sentence "Only the shim exemptions remain as `ignore_imports`" with one that matches `.importlinter`.
  - Module Overview: add a bullet `utils/user_app_data.py` — thin re-export shim over `mcp_coder_utils.user_app_data`: `get_user_app_data_dir()` (the `~/.mcp_coder` directory for `config.toml`).

## DATA
No runtime data. `get_user_app_data_dir("mcp_coder")` returns `Path.home() / ".mcp_coder"`. It may raise `RuntimeError` when no home directory can be found; callers (step 3) guard it.

## Precondition
If `mcp_coder_utils.user_app_data` cannot be imported in the project environment, write one line to `pr_info/.blocked.txt` and stop.
