# Step 3 — Docs and MCP tool docstrings

Read [summary.md](summary.md) first. Use its kind/check table and error rules as
the source of truth.

Precondition: `src/mcp_tools_py/utils/project_config.py` defines
`_read_script_dirs` (Step 2). If not, write one line to `pr_info/.blocked.txt` and
stop.

## LLM prompt

> Implement Step 3 of `pr_info/steps/summary.md` as described in
> `pr_info/steps/step_3.md`: update the docs and the `target_directories` docstrings
> of seven MCP tools. No logic changes. Run `run_format_code`, then pylint, pytest
> (`markers=["not integration"]`) and mypy; all must pass. Produce exactly one commit.

## WHERE / WHAT

### Docstrings: the `target_directories` arg of each MCP tool

These are the texts LLMs read, so keep each one to one or two lines.

| File | New wording (keep the existing first sentence) |
|---|---|
| `formatter/formatter_tools.py` (`run_format_code`) | "Defaults to auto-detection from pyproject.toml: source, test and `[tool.mcp-tools-py] script-directories` folders." |
| `checker_tools/ruff_check_tool.py`, `ruff_fix_tool.py`, `pylint_tool.py` | "Auto-detected from pyproject.toml when None: source, test and `[tool.mcp-tools-py] script-directories` folders." |
| `checker_tools/mypy_tool.py` | same as above, keeping its existing examples |
| `checker_tools/vulture_tool.py`, `bandit_tool.py` | "Auto-detected from pyproject.toml when None: source and test folders; `[tool.mcp-tools-py] script-directories` is not included." |

### `docs/pyproject-configuration.md`

- Intro (line 5): mention `script-directories` among the `[tool.mcp-tools-py]`
  keys.
- New section `## [tool.mcp-tools-py] script-directories — extra code folders`,
  placed after the `formatter` section. Contents:
  - the TOML example and the kind/check table from the summary;
  - lookup: an explicit `target_directories` wins and the key isn't read; a missing
    key or `[]` changes nothing;
  - entry rules: relative folder names only; no files, globs, absolute or
    drive/root-prefixed paths, `..`, `""` or `.`; entries are normalised;
  - errors: a missing folder, nesting within the key, or overlap with an existing
    source or test folder is an error naming the key, and nothing runs. The flat
    layout (`where = ["."]`) always overlaps. Example message;
  - vulture and bandit validate the key but get no scripts;
  - mypy can still report `Duplicate module named` for same-named files in
    separate folders; that stays a `[tool.mypy]` concern;
  - older mcp-tools-py ignores the key silently.
- "Target directory auto-detection" (lines 307–331): add a row for script dirs
  (`[tool.mcp-tools-py] script-directories`, fallback none, formatter/ruff/pylint/mypy
  only). State that existing script folders alone are enough, and link to the new
  section.

### `docs/README.md`

In the "Project Configuration" bullet, extend the text listing the
`[tool.mcp-tools-py]` topics: "subprocess timeouts, formatter selection and script
folders (`script-directories`)".

### `docs/architecture/architecture.md` (line 185, `utils/project_config.py`)

- Add that target-directory resolution includes `[tool.mcp-tools-py]
  script-directories` for formatter, ruff, pylint and mypy.
- Correct the "single reader" claim. `read_pyproject_tool_tables` reads the
  `[tool]` table for timeout resolution, formatter resolution, the pytest config
  reader and the `ruff_imports` notice. Target-directory, test-path and
  coverage-source resolution read the file through `_load_pyproject`, and
  `check_line_length_conflicts` reads it itself.

### `README.md`

- "Target Directory Auto-Detection" (lines 45–62): add the bullet **Script dirs**
  from `[tool.mcp-tools-py] script-directories` (formatter, ruff check, ruff fix,
  pylint and mypy only; not vulture or bandit), with a link to
  `docs/pyproject-configuration.md`.
- Parameter-table rows for `target_directories` (pylint at line 35, mypy at line
  97, and any other row that says "Auto-detected from `pyproject.toml` when
  omitted"; search for it): append "incl. `script-directories`" for pylint, mypy,
  ruff and format, and "excl. `script-directories`" for vulture and bandit.

## ALGORITHM / DATA

None. Docs only.
