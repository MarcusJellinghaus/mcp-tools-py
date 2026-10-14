# Step 3 — library_search.py: directory search core

Part of the plan in `pr_info/steps/summary.md` (issue #228). Read that file first.

This step implements only the filesystem-walk + glob + content-search core, as pure
functions over a plain `Path` — no MCP tool, no scope resolution yet (that's step 4).
Keeping it separate makes it testable with nothing but `tmp_path`.

## Precondition

None beyond the repository being in the state left by steps 1–2 (not required by
this step's code, but keeps the step sequence consistent). If
`src/mcp_tools_py/library_search.py` already exists with different content than
expected from a prior partial attempt, write one line to `pr_info/.blocked.txt` and
stop.

## WHERE

- New file `src/mcp_tools_py/library_search.py`
- New file `tests/test_library_search.py`

## WHAT

- `_collect_files(root: Path) -> list[str]`
- `_match_glob(glob: str, files: list[str]) -> list[str]`
- `_search_content(files: list[str], compiled: re.Pattern[str], root: Path, context_lines: int, max_results: int, max_result_lines: int) -> dict[str, Any]`
- `search_in_directory(root: Path, glob: Optional[str] = None, pattern: Optional[str] = None, context_lines: int = 0, max_results: int = 50, max_result_lines: int = 200) -> dict[str, Any]`

## HOW

Mirrors `mcp_workspace.file_tools.search`'s `_match_glob`/`_search_content`/
`search_files` shape and behaviour (same `pathspec.GitIgnoreSpec` glob semantics —
already a project dependency — same `char_budget = max_result_lines * 120`
truncation, same invalid-regex-as-literal-text fallback with the same note text,
same `skipped_files`/`matched_files` conventions), reimplemented locally since the
project-tree/gitignore-shaped original isn't a drop-in share for an arbitrary
site-packages directory. Two deliberate differences from that original, per the
plan: no "must supply glob or pattern" requirement (omitting both simply lists
everything under `root`), and no brace-detection `glob_note`. No imports from
`mcp_tools_py.utils` in this step — the module stays scope-resolution-agnostic
until step 4.

## ALGORITHM

`_collect_files`: `os.walk(root)`, pruning `__pycache__` and `*.dist-info`
directories in place, collecting `.py`/`.pyi` files as sorted root-relative
posix paths.

`search_in_directory`:
```
files = _collect_files(root)
if glob is not None: files = _match_glob(glob, files)    # may raise ValueError
if pattern is not None:
    compile pattern, falling back to re.escape(pattern) + a note on re.error
    result = _search_content(files, compiled, root, context_lines, max_results, max_result_lines)
else:
    result = {"mode": "file_search", "files": files[:max_results],
               "total_files": len(files), "truncated": len(files) > max_results}
result["scope_root"] = str(root.resolve())
return result
```

## DATA

Same result dict shape as `mcp_workspace.search_files`: `mode` (`"content_search"`
or `"file_search"`), `details`/`files`, `total_matches`/`total_files`, `truncated`,
optional `note` (invalid-regex fallback), optional `matched_files` (only when
truncated), optional `skipped_files` (only when non-empty) — plus `scope_root`
(absolute path string), present in every result regardless of mode.

## Tests (write first, see them fail, then implement)

`tests/test_library_search.py`, building small fixture trees under `tmp_path`
(`.py`/`.pyi` files, a `__pycache__/` dir, a `some.dist-info/` dir):

- file-search mode lists `.py` and `.pyi`, excludes `__pycache__`/`*.dist-info`
  content.
- a bare `"*.py"` glob matches files at any depth (confirms the
  `pathspec`/wildmatch semantic, not `fnmatch`'s depth-anchored one).
- content search: a basic match, `context_lines`, and `max_results`/
  `max_result_lines` truncation (verify `char_budget = max_result_lines * 120` is
  respected).
- an invalid regex pattern falls back to literal-text search and adds `note`.
- `scope_root` is present and absolute in both file-search and content-search
  results.
- neither `glob` nor `pattern` given → lists everything under `root` (confirms the
  dropped-validation decision; no `ValueError`).
- an unreadable/binary file under `root` is skipped and listed in `skipped_files`
  for a content search.

## Commit

One commit: `feat(library_search): add directory search core`

## LLM prompt

> Read `pr_info/steps/summary.md` for context, then implement
> `pr_info/steps/step_3.md` only. Write the tests described under "Tests" into a new
> `tests/test_library_search.py` first, confirm they fail (module does not exist
> yet), then create `src/mcp_tools_py/library_search.py` with `_collect_files`,
> `_match_glob`, `_search_content` and `search_in_directory` exactly as specified
> under WHAT/HOW/ALGORITHM/DATA. Do not add any MCP tool, registrar class, or import
> from `mcp_tools_py.utils` in this step — that is step 4. Re-run the tests until
> they pass. Run `mcp__mcp-tools-py__run_pylint_check`,
> `mcp__mcp-tools-py__run_pytest_check` (`extra_args=["-n", "auto", "-m", "not
> integration"]`) and `mcp__mcp-tools-py__run_mypy_check` — all must pass. Then run
> `mcp__mcp-tools-py__run_format_code`, stage the two new files, and create exactly
> one commit: `feat(library_search): add directory search core`. If the precondition
> above does not hold, write one line to `pr_info/.blocked.txt` and stop instead.
