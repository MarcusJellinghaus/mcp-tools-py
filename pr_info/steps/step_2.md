# Step 2 — Parser path fixes (ruff `ValueError`, bandit cwd)

## LLM prompt

Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_2.md`) only.
Tests first, then the fix. Run pylint, pytest (`-n auto`), mypy; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/utils/ruff_parsing.py` — `parse_ruff_json_output`
- `src/mcp_tools_py/code_checker_bandit/parsers.py` — `parse_bandit_json_output`
- Tests: `tests/test_code_checker_ruff/test_parsers.py`, `tests/test_code_checker_bandit/test_parsers.py`

## WHAT

No signature changes. Only the filename normalisation inside the loops.

## ALGORITHM

Ruff:
```
try: filename = os.path.relpath(filename, project_dir)
except ValueError: pass  # other drive: keep the path unchanged
```
Bandit:
```
try: filename = os.path.relpath(os.path.join(project_dir, filename), project_dir)
except ValueError: pass
```
`os.path.join` returns `filename` unchanged when it is already absolute, so absolute bandit paths
still work.

## DATA

Unchanged `RuffMessage` / `BanditMessage`; `filename` is project-relative, or the original path when
`relpath` fails.

## Tests

- Ruff: patch `mcp_tools_py.utils.ruff_parsing.os.path.relpath` with `side_effect=ValueError`; the
  message keeps the original absolute filename and no exception escapes.
- Bandit: `monkeypatch.chdir(tmp_path / "elsewhere")`, `project_dir = tmp_path / "proj"`, bandit entry
  `filename: "src/a.py"` → parsed filename `os.path.join("src", "a.py")`.
- Bandit: `relpath` raising `ValueError` keeps the path unchanged.
