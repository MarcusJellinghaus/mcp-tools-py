# Step 5 — `test@unattended`

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_5.md`.
> Write the tests first, then the implementation. Run pylint, mypy and pytest
> (`extra_args=["-n", "auto", "-m", "not integration"]`), format the code, and
> make exactly one commit.

## WHERE

- `src/mcp_tools_py/toolkit.py` — new constants, `describe`, `_run_test`,
  `prompt_fragments`
- `tests/test_toolkit.py`, `tests/test_toolkit_test.py`

## WHAT

```python
UNATTENDED_EXCLUDED_MARKERS: list[str] = [
    "not claude_cli_integration",
    "not copilot_cli_integration",
    "not langchain_integration",
    "not llm_integration",
    "not jenkins_integration",
    "not install_integration",
]
_STRICT_MARKERS_OFF: list[str] = ["-o", "strict_markers=false"]
```

Comment on the constant: same list as mcp-coder's
`workflows/rebase_automated.py::AUTOMATED_EXCLUDED_MARKERS`; it is the single
home of the list.

## HOW

- `describe()`: test depths `["quick", "standard", "unattended", "full"]`;
  the `llm_permissions["test"]` comprehension iterates the same four depths.
- `_run_test`:
  - `markers = {"quick": ["not integration"], "unattended": list(UNATTENDED_EXCLUDED_MARKERS)}.get(depth)`
  - `extra_args = list(_STRICT_MARKERS_OFF) if depth == "unattended" else []`
  - in the `full` block, `extra_args.extend(cov_args)` instead of
    reassigning.
- `prompt_fragments()`: add `"check_instructions.unattended"`, built with
  `json.dumps` from both constants. It names the six markers it deselects and
  must **not** mention "external" or reuse mcp-coder's "so tests that reach
  external services are excluded".

## ALGORITHM

```
names = ", ".join(m.removeprefix("not ") for m in UNATTENDED_EXCLUDED_MARKERS)
text = ("When you run `mcp__mcp-tools-py__run_pytest_check`, pass "
        f"markers={json.dumps(UNATTENDED_EXCLUDED_MARKERS)} and "
        f"extra_args={json.dumps(_STRICT_MARKERS_OFF)}. This deselects tests marked "
        f"{names}; the -o option stops projects using --strict-markers from "
        "rejecting marker names they do not register.")
```

## DATA

`json.dumps(_STRICT_MARKERS_OFF)` renders `["-o", "strict_markers=false"]` —
two list items, never one string.

## Tests (write first)

- `tests/test_toolkit.py`: `_EXPECTED_ACTIONS["test"]` and
  `_EXPECTED_PERMISSIONS["test"]` gain `unattended`;
  `test_contains_required_keys` expects the new key; new
  `test_unattended_instructions` asserts every marker string is in the
  fragment, `'extra_args=["-o", "strict_markers=false"]'` is in it, and
  `"external"` is not.
- `tests/test_toolkit_test.py`:
  - `test_unattended_passes_markers_and_strict_markers_off`: patch
    `check_code_with_pytest` (use `_run_with`-style helper with depth
    `"unattended"`), assert `markers == UNATTENDED_EXCLUDED_MARKERS` and
    `extra_args == ["-o", "strict_markers=false"]`.
  - `test_unattended_in_strict_marker_project_is_ok` (real run, no
    `integration` marker): pyproject
    `[tool.pytest.ini_options]\naddopts = "--strict-markers"\n`, tests file with
    a passing test and an `@pytest.mark.llm_integration` test that fails →
    status `"ok"`.
