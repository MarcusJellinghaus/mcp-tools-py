# Step 2 — `EffectiveConfig.n`: keep the effective `-n` value and its source

## LLM prompt
Read `pr_info/steps/summary.md`, then implement **this step only** (`pr_info/steps/step_2.md`).
Write the tests first in `tests/test_code_checker_pytest/test_effective_config.py`, then extend `EffectiveConfig`.
Run `run_format_code`, pylint, pytest (`markers=["not integration"]`) and mypy; all must pass. Make one commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/pytest_config.py`
- `tests/test_code_checker_pytest/test_effective_config.py`

## WHAT
Add one field to the frozen dataclass `EffectiveConfig`, directly after `numprocesses`:
```python
    numprocesses: bool
    n: OptionValue | None
```
Docstring: `n: The effective -n / --numprocesses value and its source; None when there is none.`
In `effective_config()`, the local `numprocesses = last.get("-n")` already holds it. Pass `n=numprocesses` to the constructor. Keep `numprocesses=numprocesses is not None and numprocesses.value != "0"` unchanged.

## HOW
- `EffectiveConfig(` is constructed only in `effective_config()`, so no other caller changes.
- Existing assertions on `.numprocesses` must keep passing unchanged.

## ALGORITHM
None. The value is already computed by the existing `last` dict loop.

## DATA
`OptionValue(value, source)`. `source` is one of `pyproject.toml`, `-o`, `PYTEST_ADDOPTS`, `markers`, `extra_args`. `value` is as written (`"auto"`, `"logical"`, `"8"`, `"0"`).

## Tests (write first)
Parametrize over `tmp_path` projects / call args:
- `addopts = "-n auto"` in `pyproject.toml` → `n == OptionValue("auto", "pyproject.toml")`.
- `extra_args=["-n", "8"]` overriding addopts `-n auto` → `OptionValue("8", "extra_args")`.
- `extra_args=["-nlogical"]` and `["--numprocesses=auto"]` → value `logical` / `auto`, source `extra_args`.
- `env_vars={"PYTEST_ADDOPTS": "-n 3"}` → `OptionValue("3", "PYTEST_ADDOPTS")`.
- No `-n` anywhere → `n is None`.
