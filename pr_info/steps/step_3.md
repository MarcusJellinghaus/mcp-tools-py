# Step 3 — `SanitizedArgs.path_args`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_3.md`).
> Implement only this step, TDD: write the tests first, then the code. Run
> pylint, pytest (`-n auto`), mypy and `run_format_code`; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/models.py`
- `src/mcp_tools_py/code_checker_pytest/utils.py` (`sanitize_extra_args`)
- `tests/test_code_checker_pytest/test_extra_args.py`

## WHAT

```python
@dataclass
class SanitizedArgs:
    cleaned_args: List[str]
    verbosity: int
    notes: List[str]
    has_path_args: bool = False
    path_args: List[str] = field(default_factory=list)
```

## HOW

In the existing path-detection loop of `sanitize_extra_args`, wherever
`has_path_args = True` is set, also `path_args.append(arg)`. Pass
`path_args=path_args` to the returned `SanitizedArgs`. The early-return branch
(no `extra_args`) keeps the default empty list. No other behaviour changes.

## DATA

`SanitizedArgs(..., has_path_args=True, path_args=["tests/test_x.py::test_a"])`.

## Tests

- existing path arg (shape match) → listed in `path_args`
- existing bare dir name (no shape match) → listed
- missing path and absolute path → not listed
- no `extra_args` → `path_args == []`
