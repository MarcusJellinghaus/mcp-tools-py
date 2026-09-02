# Step 2 — Honest timeouts and the retry path

One commit. Issue steps 2 and 3 are a single edit: the retry hint is one line of the same
message, and `runners.run_mypy_check` already holds everything both need — the command,
`cwd`, the interpreter, `cache_dir` and the resolved `timeout_seconds`. No new module, no
signature change, no plumbing.

## WHERE

| File | Change |
|------|--------|
| `src/mcp_tools_py/code_checker_mypy/runners.py` | One private helper + the `if result.timed_out:` branch |
| `tests/test_code_checker_mypy/test_runners.py` | Two tests |

## WHAT

### `runners.py` — one helper

```python
def _describe_cache(cache_path: str) -> str:
    """Describe a mypy cache directory: existence, total bytes, newest mtime."""
```

Facts only. It must **not** call the cache "warm": a killed run leaves a partial cache
that looks identical from outside. Size and mtime across successive calls are what make
the issue's measurement 2 readable.

### `runners.py` — the timeout branch

Replaces the current body of `if result.timed_out:` (`:146-152`), which returns only
`f"timed out after {timeout_seconds} seconds"`.

```python
if result.timed_out:
    cache_path = os.path.join(project_dir, cache_dir or ".mypy_cache")
    return MypyResult(return_code=1, messages=[], error="\n".join([...]))
```

`os.path.join` already does the right thing for an absolute `cache_dir`, and mypy's own
default is `.mypy_cache` relative to cwd — which is `project_dir`.

Message content, in order:

1. `timed out after {timeout_seconds} seconds`
2. `Cache: {_describe_cache(cache_path)}`, followed by one line saying a killed run leaves
   a partial cache and that comparing size and mtime across runs shows whether successive
   runs are making progress
3. `Command: {" ".join(command)}`, then `cwd:` and `interpreter:` on their own lines
4. that a cold mypy cache on a large project can take longer than the limit
5. `Retry with a larger timeout_seconds (this run used {timeout_seconds}).`

**Do not use `format_command`** from the subprocess shim here, despite it being the
obvious reuse: it truncates at 200 characters, and a truncated command line defeats the
reproducibility this message exists to provide. `" ".join(command)` matches what the two
existing `logger` calls in this file already do.

`timeout_seconds` is the value `ToolServer.resolve_timeout` produced and passed down, so
interpolating the parameter satisfies "name the value actually resolved" — no constant
and no second lookup.

## HOW

Needs `from datetime import datetime` in `runners.py`; `os` and `Path`/`os.walk` as
preferred. No new imports from `mcp_coder_utils` — checked, it has no directory-size
utility, so this small helper is not a duplicate.

The message travels out unchanged: `reporting.get_mypy_prompt` prefixes it with
`Mypy execution failed:` and `CheckerTools._format_mypy_result` wraps it. Multi-line text
passes through both untouched.

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
branch returns today, only the `error` text grows. `_describe_cache` returns one line.

## TESTS (write first)

Same faked `execute_command` helper as step 1, this time returning
`CommandResult(return_code=1, stdout="", stderr="", timed_out=True)`.

1. **`test_timeout_message_is_actionable`** — assert `result.error` contains: the timeout
   value, the resolved cache path, `cwd`, the interpreter path, `mypy` from the command,
   and `timeout_seconds` (the retry hint). Assert on substrings, not on exact formatting.
2. **`test_timeout_message_reports_cache_state`** — parametrized over
   `_describe_cache`: a missing directory says so; a directory holding a known file
   reports a byte count and a timestamp. Build the cache dir under `tmp_path` and pass it
   as `cache_dir`.

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
> `runners.py` plus one private `_describe_cache` helper. Do not add a module, change any
> signature, or touch `_format_mypy_result`.
>
> Write both tests first. Use `" ".join(command)`, not `format_command` — that helper
> truncates at 200 characters and would make the reported command unreproducible.
>
> The cache description must state facts only (exists / bytes / newest mtime) and must
> never call the cache warm: a killed run leaves a partial cache that looks the same from
> outside.
>
> Use MCP tools for all file and git operations. Run `run_format_code` before committing,
> then pylint, pytest (`-n auto`) and mypy.
