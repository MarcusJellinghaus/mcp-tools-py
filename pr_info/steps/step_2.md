# Step 2 — Honest timeouts and the retry path

One commit. Issue steps 2 and 3 are a single edit: the retry hint is one line of the same
message, and `runners.run_mypy_check` already holds everything both need — the command,
`cwd`, the interpreter, `cache_dir` and the resolved `timeout_seconds`. No new module, no
signature change, no plumbing.

## WHERE

| File | Change |
|------|--------|
| `src/mcp_tools_py/code_checker_mypy/runners.py` | Two private helpers + the `if result.timed_out:` branch |
| `src/mcp_tools_py/checker_tools/__init__.py` | `_format_mypy_result` (`:130`) — the headline |
| `tests/test_code_checker_mypy/test_runners.py` | Two tests |
| `tests/test_checker_tools.py` | `_format_mypy_result` tests (`:96-107`) — one added, the existing two keep passing |
| `tests/test_error_transparency.py` | `TestMypyTimeout` (`:220-239`) — existing coverage of this branch; must keep passing |

`TestMypyTimeout::test_timeout_reported_as_timeout` already asserts the branch reports
`timed out`, names the limit (`5 seconds`) and does **not** leak the raw
`Process timed out after` string from `execute_command`. That last assertion constrains
the new message: `timed out after {timeout_seconds} seconds` must not be prefixed with
`Process`. Leave the class as it is and do not restate its assertions in the two new
tests — those cover what it does not: the cache line, the command/cwd/interpreter block
and the retry hint.

## WHAT

### `runners.py` — two helpers

```python
def _resolve_cache_dir(project_dir: str, cache_dir: str | None) -> str | None:
    """Resolve the cache directory mypy will actually use, or None if unknown."""


def _describe_cache(cache_path: str) -> str:
    """Describe a mypy cache directory: existence, total bytes, newest mtime."""
```

`_describe_cache` states facts only. It must **not** call the cache "warm": a killed run
leaves a partial cache that looks identical from outside. Size and mtime across
successive calls are what make the issue's measurement 2 readable.

`_resolve_cache_dir` exists because `cache_dir` is a `[tool.mypy]` key like any other.
After step 1 the project owns it, so the server cannot assume `.mypy_cache`: reporting a
path mypy may never have written would be exactly the kind of confident-but-wrong
statement step 2 exists to remove. It returns `None` when it cannot say, and the message
then names the config that owns the setting instead of guessing a path.

### `runners.py` — the timeout branch

Replaces the current body of `if result.timed_out:` (`:152-158`), which returns only
`f"timed out after {timeout_seconds} seconds"`.

```python
if result.timed_out:
    cache_path = _resolve_cache_dir(project_dir, cache_dir)
    return MypyResult(return_code=1, messages=[], error="\n".join([...]))
```

Message content, in order:

1. `timed out after {timeout_seconds} seconds`
2. when `cache_path` is not `None`, `Cache: {_describe_cache(cache_path)}`; when it is,
   one line saying the cache directory is set by the project's mypy config and was not
   resolved, with **no** size or mtime. Either way, followed by one line saying a killed
   run leaves a partial cache and that comparing size and mtime across runs shows
   whether successive runs are making progress
3. `Command: {" ".join(command)}`, then `cwd:` and `interpreter:` on their own lines
4. that a cold mypy cache on a large project can take longer than the limit
5. `Retry with a larger timeout_seconds (this run used {timeout_seconds}).`

### `checker_tools/__init__.py` — the headline

`_format_mypy_result` (`:130`) returns `f"Mypy found type issues that need attention:\n\n{mypy_prompt}"`
for every non-`None` prompt, so the honest message above arrives under a false headline.
`get_mypy_prompt` already prefixes any failure with `Mypy execution failed:`, so branching
on that prefix needs no change to its `str | None` contract:

```python
if mypy_prompt.startswith("Mypy execution failed:"):
    return mypy_prompt
```

The failure text is returned as-is — it already names itself. The two existing branches
are untouched.

**Do not use `format_command`** from the subprocess shim here, despite it being the
obvious reuse: it truncates at 200 characters, and a truncated command line defeats the
reproducibility this message exists to provide. `" ".join(command)` matches what the two
existing `logger` calls in this file already do.

`timeout_seconds` is the value `ToolServer.resolve_timeout` produced and passed down, so
interpolating the parameter satisfies "name the value actually resolved" — no constant
and no second lookup.

## HOW

Needs `from datetime import datetime` and `import tomllib` in `runners.py`; `os` and
`Path`/`os.walk` as preferred. `tomllib` is stdlib on the declared floor (3.11) and
`utils/project_config.py:249-264` already reads `pyproject.toml` this way — read the
`[tool.mypy]` table directly rather than widening that module's `[tool.mcp-tools-py]`
helper. No new imports from `mcp_coder_utils` — checked, it has no directory-size
utility, so these small helpers are not duplicates.

The message travels out unchanged: `reporting.get_mypy_prompt` prefixes it with
`Mypy execution failed:`, and with the change above `CheckerTools._format_mypy_result`
returns it as-is. Multi-line text passes through both untouched.

## ALGORITHM — `_resolve_cache_dir`

Mypy's config discovery order is `mypy.ini`, `.mypy.ini`, `pyproject.toml`, `setup.cfg`,
all relative to cwd — which is `project_dir`. Only `pyproject.toml` is parsed here; the
INI formats resolve to `None` rather than to a guess.

```
if cache_dir:                        return os.path.join(project_dir, cache_dir)
if mypy.ini or .mypy.ini exists:     return None      # wins over pyproject, not parsed
if pyproject.toml has [tool.mypy]:   return os.path.join(project_dir,
                                            its cache_dir or ".mypy_cache")
if setup.cfg exists:                 return None      # consulted next, not parsed
return os.path.join(project_dir, ".mypy_cache")       # mypy's documented default
```

`os.path.join` already does the right thing for an absolute value. A malformed
`pyproject.toml` or a non-string `cache_dir` returns `None` too: a timeout report is the
wrong place to raise.

## ALGORITHM — `_describe_cache`

```
if not a directory:          return "<path> (does not exist)"
try: stats = [f.stat() for f in Path(path).rglob("*") if f.is_file()]
except OSError as exc:       return "<path> (unreadable: <exc>)"
if not stats:                return "<path> (empty)"
return "<path> (<sum st_size> bytes across <len> files, newest <max st_mtime as ISO>)"
```

The single `except OSError` is load-bearing, not defensive padding: a killed mypy can
leave the cache mid-write, so files may vanish between `rglob` and `stat`.

## DATA

`MypyResult(return_code=1, messages=[], error=<multi-line str>)` — the same shape the
branch returns today, only the `error` text grows. `_describe_cache` returns one line;
`_resolve_cache_dir` returns a path or `None`.

## TESTS (write first)

Same patching pattern as step 1 — `@patch("mcp_tools_py.code_checker_mypy.runners.execute_command")`
with `make_command_result` from `tests/conftest.py` — this time
`make_command_result(return_code=1, timed_out=True)`.

1. **`test_timeout_message_is_actionable`** — assert `result.error` contains: the timeout
   value, the resolved cache path, `cwd`, the interpreter path, `mypy` from the command,
   and `timeout_seconds` (the retry hint). Assert on substrings, not on exact formatting.
2. **`test_timeout_message_reports_cache_state`** — parametrized over
   `_describe_cache`: a missing directory says so; a directory holding a known file
   reports a byte count and a timestamp. Build the cache dir under `tmp_path` and pass it
   as `cache_dir`.

   Same test function family covers `_resolve_cache_dir`, parametrized over `tmp_path`
   projects: no config → `.mypy_cache` under the project; `[tool.mypy] cache_dir = "x"`
   in `pyproject.toml` → `x` under the project, **not** `.mypy_cache`; a `mypy.ini`
   present → `None`; an explicit `cache_dir` argument wins over all of them. Assert that
   the `None` case produces a message with no byte count.

3. **`test_format_mypy_result_failure_keeps_its_own_headline`** in
   `tests/test_checker_tools.py`, beside the two existing `_format_mypy_result` tests
   (`:96-107`): a prompt starting `Mypy execution failed:` comes back without
   `Mypy found type issues`. `test_format_mypy_result_with_issues` (`:103`) must keep
   passing unchanged — a real type-issue prompt still gets the headline.

Do not assert the word "warm" is absent — assert the positive facts instead.

## VERIFICATION

```
mcp__mcp-tools-py__run_format_code
mcp__mcp-tools-py__run_pylint_check
mcp__mcp-tools-py__run_pytest_check   extra_args: ["-n", "auto"]
mcp__mcp-tools-py__run_mypy_check
```

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_2.md`, then implement step 2 on
> top of step 1.
>
> This is the issue's steps 2 and 3 together — one `if result.timed_out:` branch in
> `runners.py`, two private helpers (`_resolve_cache_dir`, `_describe_cache`), and a
> two-line early return in `_format_mypy_result` so a failure keeps its own headline. Do
> not add a module and do not change any signature.
>
> Write all three tests first. Use `" ".join(command)`, not `format_command` — that helper
> truncates at 200 characters and would make the reported command unreproducible.
>
> The cache description must state facts only (exists / bytes / newest mtime) and must
> never call the cache warm: a killed run leaves a partial cache that looks the same from
> outside. Do not hardcode `.mypy_cache`: after step 1 the project's `[tool.mypy]` owns
> `cache_dir` too, so resolve it, and when it cannot be resolved say so instead of
> reporting size and mtime for a path mypy may never have written.
>
> Use MCP tools for all file and git operations. Run `run_format_code` before committing,
> then pylint, pytest (`-n auto`) and mypy.
