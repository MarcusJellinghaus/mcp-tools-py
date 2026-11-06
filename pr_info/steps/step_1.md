# Step 1: Runner reports every failed exit and exposes stderr

**Commit message:** `fix(mypy): report failed exits as errors and expose stderr`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, `pr_info/steps/step_1.md`. Implement this step only, tests first. Run the checks listed in the summary, fix what they report, then make exactly one commit.

## WHERE

- `src/mcp_tools_py/code_checker_mypy/models.py`
- `src/mcp_tools_py/code_checker_mypy/parsers.py`
- `src/mcp_tools_py/code_checker_mypy/runners.py`
- `tests/test_code_checker_mypy/test_parsers.py`
- `tests/test_code_checker_mypy/test_runners.py`

## WHAT

```python
# models.py: last field of MypyResult
stderr: str | None = None

# parsers.py
def strip_json_messages(output: str) -> str: ...

# runners.py: module level
MYPY_EXIT_PREFIX = "mypy exited with code"
```

Also add `AttributeError` to the `except (KeyError, TypeError, ValueError)` in `parse_mypy_json_output`.

## HOW

- `run_mypy_check` keeps its signature. Only the section after `raw_output` is built changes.
- Delete the whole `if result.return_code == 2:` block, including its "Mypy returned configuration error" log and the "Mypy configuration error" label. Reword the "mypy config errors" comment above `output_to_parse` to be neutral.
- Keep the timeout, execution-error and tool-missing paths as they are. Do not use `truncate_stderr` for the new error.
- Change the comment at `test_runners.py:25` from "2=config error" to "2=blocking or internal error".

## ALGORITHM

```python
parse_stderr = rc == 2 and not stdout.strip() and stderr.strip()
messages, parse_error = parse_mypy_json_output(stderr if parse_stderr else stdout)
errors_found = count of messages with severity "error"
if (not messages if rc == 1 else rc != 0 and errors_found == 0):
    return MypyResult(rc, [], error=f"{MYPY_EXIT_PREFIX} {rc}: {raw_output.strip() or 'no output'}", raw_output=raw_output)
if parse_error: return the existing parse-error result  # now reachable only at rc 0
stderr_text = strip_json_messages(stderr) if parse_stderr else stderr.strip()
return MypyResult(..., stderr=stderr_text or None)
```

`strip_json_messages` keeps each line unless `json.loads(line)` succeeds and returns a `dict`, which is the parser's definition of a message. It returns the kept lines joined with `\n` and stripped. Lines such as `null` or `123` are kept.

## DATA

- `MypyResult.error`: `"mypy exited with code 2: <stdout and stderr>"`, or `"mypy exited with code 3: no output"`.
- `MypyResult.stderr`: the non-JSON stderr text, or `None` when empty or when `error` is set.
- `raw_output`: unchanged content.

## Tests first

**`test_parsers.py`**
- `null`, `123` and `["a"]` lines give no exception, no messages and a parse error.
- A non-dict line alongside a valid message keeps the message and gives no error.
- `strip_json_messages` removes dict lines and keeps text, `null` and blank-only output (returns `""`).

**`test_runners.py`:** one parametrized test using `make_command_result` and a patched `execute_command`, with these cases:

| rc | stdout | stderr | Expected |
|---|---|---|---|
| 0 | empty | warning text | no `error`, `stderr` is the warning |
| 0 | empty | empty | no `error`, `stderr` is `None` |
| 1 | empty | traceback | `error` starts with `mypy exited with code 1`, keeps the end of a traceback longer than 500 characters, `stderr` is `None` |
| 1 | JSON error | warning text | message kept, `stderr` is the warning |
| 1 | JSON note | empty | no `error`, one message |
| 2 | empty | `Cannot decode file` | neutral error, no "configuration error" text |
| 2 | non-JSON | empty | neutral error |
| 2 | empty | warning line plus JSON error | one message, `stderr` is only the warning line |
| 2 | JSON error | `INTERNAL ERROR` text | message kept, `stderr` has the text |
| 2 | JSON note | `INTERNAL ERROR` text | neutral error containing the text |
| 2 | empty | empty | `error` ends with `no output` |
| 3 | empty | empty | `error` ends with `no output` |
| -11 | JSON note | empty | neutral error |
| 1 | `null` | empty | neutral error, no exception |
| 0 | `null` | empty | the parse error text |

Also assert `raw_output` holds stdout and stderr in a case that has both.
