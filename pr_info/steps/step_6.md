# Step 6 — `resolve_steps`, the step→tool mapping, both entry points wired

The step that makes the two ruff runners reachable and fixes the actual bug: on a
ruff-migrated repo, `run_format_code` with no `steps` must stop running black.

This is the largest step. It is not splittable — `resolve_steps` and the two defaulting
sites must change together or one entry point disagrees with the other, which is the
exact failure the issue exists to prevent.

## WHERE

**Modify**
- `src/mcp_tools_py/formatter/runner.py`
- `src/mcp_tools_py/formatter/formatter_tools.py`
- `src/mcp_tools_py/formatter/__init__.py`
- `src/mcp_tools_py/utils/project_config.py` — new public `read_pyproject_tool_tables(Path)`;
  `_read_mcp_tools_section` delegates to it
- `tests/test_formatter_runner.py`
- `tests/test_formatter_tools.py`

**Create** `tests/test_formatter_resolution.py`

`resolve_steps` goes in `runner.py`, **not** a new module. The issue asks for a standalone
*function* in `formatter/`; `runner.py` already owns `validate_steps` and the step tables,
and `formatter_tools.py` already imports from it.

## WHAT

### `runner.py`

```python
_BLACK_STEPS: list[str] = ["isort", "black"]
_RUFF_STEPS: list[str] = ["ruff_imports", "ruff_format"]

_VALID_STEPS: set[str] = {"isort", "black", "ruff_imports", "ruff_format"}

_STEP_RUNNERS: dict[str, Callable[..., FormatterResult]] = {
    "isort": run_isort,
    "black": run_black,
    "ruff_imports": run_ruff_imports,
    "ruff_format": run_ruff_format,
}

# A step is not a tool name. Both ruff steps map to tool `ruff`.
# Typed `ToolName`, not `str`: `ToolContext.resolve_timeout(tool: ToolName)` takes a
# `Literal`, so a `str` here fails the strict-mypy gate at the call site.
_STEP_TOOLS: dict[str, ToolName] = {
    "isort": "isort",
    "black": "black",
    "ruff_imports": "ruff",
    "ruff_format": "ruff",
}


def step_tool(step: str) -> ToolName:
    """Tool a step invokes — for availability, timeouts and line-length checks."""


def resolve_steps(project_root: Path) -> list[str]:
    """Steps to run when the caller named none.

    Raises:
        ValueError: If no formatter is declared, or two are.
    """


def validate_steps(steps: list[str]) -> None:
    """Reject unknown step names and an empty list."""
```

**`DEFAULT_STEPS` is deleted.** Verified: its only consumers are the two defaulting sites
this step replaces. mcp_coder imports `FormatterResult`, `run_black` and `run_isort` —
never `DEFAULT_STEPS`. No deprecation shim.

Ruff steps go **before** black steps in the ordering convention: `ruff_imports` then
`ruff_format`, mirroring isort → black.

### Resolution rule

```
resolve_steps(project_root):
    section = [tool.mcp-tools-py] from project_root/pyproject.toml
    if "formatter" in section:
        "ruff"  -> _RUFF_STEPS
        "black" -> _BLACK_STEPS
        other   -> ValueError naming the key, the file and the two valid values
    has_ruff  = [tool.ruff.format] table present
    has_black = [tool.black] table present
    both    -> ValueError    # never guess between two formatters
    neither -> ValueError
    return _RUFF_STEPS if has_ruff else _BLACK_STEPS
```

**Both error messages must name the key and the file**, so the fix is obvious from the
message alone. Something like:

> Cannot tell which formatter to use: `<root>/pyproject.toml` declares both `[tool.black]`
> and `[tool.ruff.format]`. Set `[tool.mcp-tools-py] formatter = "black"` or `"ruff"`.

> No formatter declared: `<root>/pyproject.toml` has neither `[tool.black]` nor
> `[tool.ruff.format]`. Set `[tool.mcp-tools-py] formatter = "black"` or `"ruff"`.

**One reader, one parameter type.** `resolve_steps` needs three lookups from the same file
— `[tool.mcp-tools-py] formatter`, `[tool.black]` and `[tool.ruff.format]` — so it must not
read `pyproject.toml` twice. Add one public helper to `utils/project_config.py`:

```python
def read_pyproject_tool_tables(project_root: Path) -> dict[str, object]:
    """The `[tool]` table of `project_root/pyproject.toml`, empty when absent."""
```

`resolve_steps(project_root: Path)` calls it once and takes all three answers from the
returned mapping. **`Path` is the parameter type throughout** — the existing
`_read_mcp_tools_section(project_dir: str)` takes a `str`, so do not call it from
`resolve_steps`: rewrite it to delegate to the new helper (converting its own `str`
argument once) rather than parsing the file a second time. `get_check_timeout`'s use of
`_read_mcp_tools_section` is unaffected, and `_read_mcp_tools_section` stays private —
publicising it is no longer needed.

A missing `pyproject.toml` yields an empty mapping and falls through to the "neither
declared" error, which is the right answer. A malformed one propagates the existing
`ValueError`, which both entry points already handle.

**Rollout is safe:** mcp_coder, mcp-workspace, mcp-config and mcp-coder-utils all have
`[tool.black]`, so every repo in the fleet resolves to black and none is broken by the new
error.

### `validate_steps` rejects `[]`

Both defaulting sites are `steps or DEFAULT_STEPS` today, so `[]` currently falls back to
the defaults. Switching to a `steps is None` check would silently turn it into a zero-step
run. An empty step list is a caller error — not a request for the defaults, and not a
no-op.

### Both entry points

`runner.py::run_format_code`:

```python
resolved_steps = resolve_steps(project_root) if steps is None else steps
validate_steps(resolved_steps)
```

`formatter_tools.py::run_format_code` — same rule, wrapped:

```python
try:
    resolved_steps = resolve_steps(self.context.project_dir) if steps is None else steps
    validate_steps(resolved_steps)
except ValueError as exc:
    return f"Error: {exc}"
```

The MCP layer needs the resolved list *before* calling the runner — for the availability
loop, the timeout dict, `check_line_length_conflicts` and result section ordering. The
runner resolves again when `steps is None`; that is a cheap TOML read and keeps a direct
runner caller honest.

**The MCP-registered `run_format_code` must not gain a `python_executable` parameter.**
Its first parameter stays `steps`. The deprecated parameter exists only on the runner
layer, which is what mcp_coder calls.

### Step→tool mapping at the three call sites

```python
for step in resolved_steps:
    tool = step_tool(step)
    if not self.context.is_tool_available(tool):
        return f"Error: {self.context.unavailable_message(tool)}"

warnings = check_line_length_conflicts(
    str(self.context.project_dir), sorted({step_tool(s) for s in resolved_steps})
)

timeouts = {step: self.context.resolve_timeout(step_tool(step)) for step in resolved_steps}
```

That timeout dict literal — currently hardcoded to isort and black regardless of the
requested steps — is the thing that changes. `ToolContext.resolve_timeout` needs no
behavioural change, and `ToolName` in `utils/project_config.py` already includes `ruff` —
but it is typed `resolve_timeout(tool: ToolName)`, a `Literal`, so `step_tool` must return
`ToolName` rather than `str` or the strict-mypy gate fails here. `runner.py` imports
`ToolName` from `utils/project_config.py`, which it already depends on for
`DEFAULT_CHECK_TIMEOUT`.

`check_line_length_conflicts` takes a deduplicated list because both ruff steps map to the
same tool. It only tests membership (`project_config.py:200`), so duplicates are harmless
today — dedup is for a readable argument, not to prevent a doubled warning.

Note `timeouts` stays keyed by **step**, because `runner.py` looks it up by step.

### `_unparsable_block`'s explanation is isort-specific and must change

`formatter_tools.py:116-121` renders every step's `unparsable_files` with a hardcoded
three-line preamble ending in `"Known limitation (Windows, piped stdout)."`. That
explanation is true only of isort, which exits 0 and skips files it could not read on a
piped stdout. For the ruff steps a populated `unparsable_files` means a **genuine syntax
error in the source**, so the current wording tells the caller the opposite of what
happened.

Replace the third line with wording that covers both causes, and keep the first two lines
(the count and "a clean result here does NOT mean CI will pass"), which stay true for
every step:

> `The file could not be parsed, or the formatter could not read it (isort on Windows with piped stdout).`

Test: a `FormatterResult` with a populated `unparsable_files` on a **ruff** step renders a
block that does not claim a Windows piped-stdout limitation as the cause. Existing
isort-path assertions on this text are updated to the new wording, not duplicated.

### `formatter/__init__.py`

Export `resolve_steps`. Drop `DEFAULT_STEPS`. The step lists stay private.

```python
__all__ = ["FormatterTools", "FormatterResult", "resolve_steps", "run_format_code"]
```

## DATA

`resolve_steps(project_root: Path) -> list[str]` — one of the two private lists, always
non-empty, ordered by execution.

## TESTS

**Write first.**

`tests/test_formatter_resolution.py` — one `pytest.mark.parametrize` over the five cases,
not five functions:

| `pyproject.toml` | expected |
|---|---|
| `formatter = "black"` | `["isort", "black"]` |
| `formatter = "ruff"` | `["ruff_imports", "ruff_format"]` |
| `[tool.black]` only | `["isort", "black"]` |
| `[tool.ruff.format]` only | `["ruff_imports", "ruff_format"]` |
| both | `ValueError` |
| neither | `ValueError` |

Plus:

1. Both error messages contain `"formatter"`, `"mcp-tools-py"` and the path to
   `pyproject.toml`. Acceptance criterion — assert on content, not just the exception type.
2. The explicit key wins when it contradicts the tables: `formatter = "black"` alongside
   `[tool.ruff.format]` only → black steps.
3. An unrecognised `formatter` value raises, naming both valid values.
4. No `pyproject.toml` at all → the "neither declared" error.

`tests/test_formatter_runner.py`:

5. `steps=[]` raises `ValueError` — not a fallback to the defaults, not a zero-step run.
6. `steps=None` calls `resolve_steps`; an explicit list does not.
7. `["isort", "black"]` passed explicitly behaves exactly as before. **Regression
   criterion** — keep the existing tests in this module and add nothing that weakens them.
   "As before" covers which steps run, in which order, with which `success`,
   `files_changed` and `unparsable_files`; it does **not** cover `output` text, which step 3
   deliberately changed by prepending the version banner.
8. A bogus `python_executable` does not change which binary runs, end to end through
   `run_format_code`.

`tests/test_formatter_tools.py`:

9. `steps=[]` returns an error string from the MCP layer.
10. Timeouts for ruff steps resolve via tool `ruff`:
    `{"ruff_imports": 120, "ruff_format": 120}`.
11. The existing `{"isort": 120, "black": 120}` assertion still holds.
12. Availability for a ruff step is checked against tool `ruff`, and its error message
    names `ruff`.

**Fixture fix — `test_default_steps_isort_then_black` at line 59 and friends.** Several
tests in this module call `run_format` without `steps`, against a `tool_context` whose
`project_dir` is an empty tmp directory. Those now hit the "neither declared" error. Add a
module-scoped autouse fixture writing a minimal `pyproject.toml` with
`[tool.mcp-tools-py] formatter = "black"` into `tool_context.project_dir`.

Do **not** change the shared `tool_context` fixture in `tests/conftest.py` — timeout tests
elsewhere depend on there being no `pyproject.toml`.

## DONE WHEN

pylint / pytest / mypy / tach / lint-imports pass. Check `check_file_size` on `runner.py`.

---

## LLM PROMPT

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_6.md`.
>
> In `src/mcp_tools_py/formatter/runner.py` add `resolve_steps(project_root)`, private
> `_BLACK_STEPS` / `_RUFF_STEPS`, a `_STEP_TOOLS` mapping with a `step_tool()` accessor —
> both typed `ToolName`, not `str`, because `resolve_timeout` takes that `Literal` —
> and the two ruff entries in `_VALID_STEPS` and `_STEP_RUNNERS`. Make `validate_steps`
> reject an empty list. **Delete `DEFAULT_STEPS`** — it has no consumer outside the two
> defaulting sites you are replacing, so no deprecation shim.
>
> Resolution: `[tool.mcp-tools-py] formatter` wins; otherwise detect `[tool.ruff.format]`
> versus `[tool.black]`; both present or neither present is an error. Both error messages
> must name the key and the path to `pyproject.toml`. Read the file **once**, through a new
> public `read_pyproject_tool_tables(project_root: Path)` in `utils/project_config.py`, and
> have the existing `_read_mcp_tools_section` delegate to it. `Path` is the parameter type
> throughout `resolve_steps`.
>
> Also fix `_unparsable_block` in `formatter_tools.py`: its
> `"Known limitation (Windows, piped stdout)"` line is isort-specific and would now be
> printed for genuine ruff syntax errors. Reword it to cover both causes.
>
> Wire both defaulting sites — `runner.py::run_format_code` and the MCP-registered
> `formatter_tools.py::run_format_code` — to call `resolve_steps` when `steps is None`, so
> there is exactly one defaulting rule. In `formatter_tools.py`, route availability,
> `check_line_length_conflicts` and the timeout dict through `step_tool()`; the hardcoded
> `{"isort": ..., "black": ...}` literal is what changes.
>
> **The MCP-registered `run_format_code` must not gain a `python_executable` parameter.**
> Its first parameter stays `steps`.
>
> Write the tests first. Use one parametrized test for the five resolution cases. Add a
> module-scoped autouse fixture in `tests/test_formatter_tools.py` writing a
> `[tool.mcp-tools-py] formatter = "black"` pyproject.toml into the tool_context's project
> dir — several tests there call `run_format` with no steps and would otherwise hit the
> "neither declared" error. Do not change the shared `tool_context` fixture in
> `tests/conftest.py`.
>
> Keep the existing explicit-`["isort", "black"]` tests passing unchanged; that is a stated
> regression criterion.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check` and
> `run_lint_imports_check`. All must pass. Then make exactly one commit.
