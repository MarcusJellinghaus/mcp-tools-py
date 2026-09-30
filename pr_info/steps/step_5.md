# Step 5 — Selection echo

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_5.md`).
> Implement only this step, TDD: write the tests first, then the code. Run
> pylint, pytest (`-n auto`), mypy and `run_format_code`; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/coverage.py`
- `tests/test_code_checker_pytest/test_coverage.py`

## WHAT

```python
def selection_line(
    markers: list[str] | None,
    cleaned_args: list[str],
    path_args: list[str],
    addopts: str | None,
) -> str:
    """One line naming everything that narrowed the run, or saying nothing did."""

def _option_value(tokens: list[str], flag: str) -> str | None:
    """Last value given for a short option (`-m X` or `-mX`); pytest keeps the last."""
```

## HOW

Four narrowing mechanisms (issue, *The selection trap*): the `markers` parameter,
`-m` in `addopts`, `-k`, path arguments. `-m` in `extra_args` is equivalent to
`markers` (sanitize already drops it when `markers` is given). `addopts` is
tokenised with `shlex.split`; on `ValueError` treat it as no tokens.

The command line overrides `addopts` (addopts is prepended), so report the
**effective** marker expression and `-k`, labelled with their source.

## ALGORITHM

```
cmd_m = " and ".join(markers) if markers else _option_value(cleaned_args, "-m")
add = shlex.split(addopts or "")
parts = []
if cmd_m: parts.append(f"markers '{cmd_m}'")
elif (m := _option_value(add, "-m")): parts.append(f"addopts -m '{m}'")
same for -k (cleaned_args first, then addopts)
if path_args: parts.append("paths " + ", ".join(path_args))
return "selection: " + ("; ".join(parts) if parts else "full suite (no markers, -k or path arguments)")
```

## DATA

`"selection: addopts -m 'not integration'; -k 'install'"` /
`"selection: full suite (no markers, -k or path arguments)"`

## Tests

- nothing narrowing → full-suite line
- `markers=["a", "b"]` → `markers 'a and b'`
- `-m` in `cleaned_args` without `markers` → reported
- `addopts="-n auto -m 'not integration'"` → `addopts -m 'not integration'`
- command-line `-m` wins over addopts `-m`
- `-k` in args, `-kfoo` joined form, `-k` in addopts
- path args listed
- unbalanced quotes in addopts do not raise
