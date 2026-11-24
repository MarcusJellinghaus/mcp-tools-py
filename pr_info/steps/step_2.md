# Step 2 — Report flags in `effective_config`

## LLM prompt
Read `pr_info/steps/summary.md` (design change 2) and this file; issue #293 D15/D17/D21 define the semantics.
Implement test-first. Run pylint, mypy and the non-integration pytest suite. One commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/pytest_config.py`
- Tests: `tests/test_code_checker_pytest/test_effective_config.py`

## WHAT
```python
@dataclass(frozen=True)
class OptionValue:
    value: str
    source: str
    label: str = ""          # call spelling: "-rs", "-r s", "--report-chars=s", "--durations 5"

@dataclass(frozen=True)
class EffectiveConfig:
    ...                       # existing fields unchanged
    options: dict[str, OptionValue] = field(default_factory=dict)   # every tracked option, last wins
```
- `_VALUE_OPTIONS` gains `"-r": "-r"`, `"--report-chars": "-r"`, `"--durations": "--durations"`,
  `"--durations-min": "--durations-min"`, `"--show-capture": "--show-capture"`.
- `_FLAG_OPTIONS` becomes a dict spelling → canonical name: `--strict-markers`, `--strict`,
  `--snapshot-update`, `--disable-warnings`, `--disable-pytest-warnings` → `--disable-warnings`.
- New private `_label(tokens, start, end, option, value) -> str`.

## HOW
- In `effective_config`, the `last` loop iterates `_option_spans(tokens)` (not `_option_events`) so it can build
  `OptionValue(value, source, _label(...))`. Pass `options=last` to `EffectiveConfig`.
- `_strict_markers_on` keeps matching on the canonical names `--strict-markers` / `--strict`.

## ALGORITHM
```
_label(tokens, start, end, option, value):
    if tokens[start].startswith("--"): return " ".join(tokens[start:end])
    if end - start == 2: return f"{option} {value}"      # "-r s"
    return f"{option}{value}"                             # "-rs", also from "-xrs"
```

## DATA
- `effective_config(dir, None, ["-r", "s"], None).options["-r"] == OptionValue("s", "extra_args", "-r s")`.
- ini `addopts = "-ra"` then call `-rw` → `options["-r"].value == "w"`, source `extra_args` (no merging).
- `--disable-pytest-warnings` → `"--disable-warnings" in options`.
- `--snapshot-update` in `PYTEST_ADDOPTS` → `options["--snapshot-update"].source == "PYTEST_ADDOPTS"`.

## Tests (write first)
Spellings `-rs`, `-r s`, `-rsw`, `--report-chars=s`, `--report-chars s`, `--durations 5`, `--durations=5`,
`--durations-min=0.1`, `--show-capture=log`; labels as above; source order ini → `PYTEST_ADDOPTS` → call;
existing `m`, `k`, `numprocesses`, strict-marker tests stay green.
