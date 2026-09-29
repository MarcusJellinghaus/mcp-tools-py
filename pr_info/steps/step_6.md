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
_STEP_TOOLS: dict[str, str] = {
    "isort": "isort",
    "black": "black",
    "ruff_imports": "ruff",
    "ruff_format": "ruff",
}


def step_tool(step: str) -> str:
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

Reuse `_read_mcp_tools_section` from `utils/project_config.py` for the first lookup —
export it under a public name rather than reaching for the private one. A missing
`pyproject.toml` falls through to the "neither declared" error, which is the right answer.

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
    str(self.context.project_dir), [step_tool(s) for s in resolved_steps]
)

timeouts = {step: self.context.resolve_timeout(step_tool(step)) for step in resolved_steps}
```

That timeout dict literal — currently hardcoded to isort and black regardless of the
requested steps — is the thing that changes. `ToolContext.resolve_timeout` is generic and
needs no change; `ToolName` in `utils/project_config.py` already includes `ruff`.

Note `timeouts` stays keyed by **step**, because `runner.py` looks it up by step.

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
> `_BLACK_STEPS` / `_RUFF_STEPS`, a `_STEP_TOOLS` mapping with a `step_tool()` accessor,
> and the two ruff entries in `_VALID_STEPS` and `_STEP_RUNNERS`. Make `validate_steps`
> reject an empty list. **Delete `DEFAULT_STEPS`** — it has no consumer outside the two
> defaulting sites you are replacing, so no deprecation shim.
>
> Resolution: `[tool.mcp-tools-py] formatter` wins; otherwise detect `[tool.ruff.format]`
> versus `[tool.black]`; both present or neither present is an error. Both error messages
> must name the key and the path to `pyproject.toml`.
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
