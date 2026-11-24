# Step 1 — Shared short-group splitter

## LLM prompt
Read `pr_info/steps/summary.md` (design change 1) and this file. Implement step 1 test-first: write the tests
below, see them fail, then implement. Run pylint, mypy and the non-integration pytest suite; all must pass. One
commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/utils.py`
- `src/mcp_tools_py/code_checker_pytest/pytest_config.py` (`_option_spans`)
- Tests: new `tests/test_code_checker_pytest/test_short_groups.py`; update
  `tests/test_code_checker_pytest/test_extra_args.py`

## WHAT
```python
# utils.py
_SHORT_VALUE_LETTERS = frozenset(o[1] for o in _ONE_VALUE_OPTIONS if len(o) == 2)  # W c k m n o p r

def split_short_group(arg: str) -> tuple[str, str | None, str]:
    """Split a single-dash token: (switch letters, value letter or None, inline value)."""
```
- `_values_taken(arg)`: short branch becomes `_, letter, value = split_short_group(arg); return 1 if letter and not value else 0`.
- `_scan_args`: unchanged (uses `_values_taken`).
- `sanitize_extra_args`: the `_SWITCH_LETTERS` branch is replaced by a generic short-group branch;
  `_SWITCH_LETTERS` is deleted. The `-m` branch must run **before** the group branch.
- `pytest_config._option_spans`: the `token[:2] in _VALUE_OPTIONS` branch is replaced by a split-based branch.

## ALGORITHM
```
split_short_group(arg):            # caller guarantees arg starts with "-" and not "--", len > 1
    body = arg[1:]
    for pos, letter in enumerate(body):
        if letter in _SHORT_VALUE_LETTERS: return body[:pos], letter, body[pos+1:]
    return body, None, ""
sanitize group branch (arg short, not "-m" handled above):
    switches, letter, value = split; if "s" not in switches and "v" not in switches: keep arg; continue
    if "s" in switches: show_output = True;  if "v" in switches: verbosity = switches.count("v")
    rest = switches without s/v + (letter + value if letter else "");  if rest: cleaned.append("-" + rest)
_option_spans short branch, only when token.startswith("-") and not token.startswith("--") and len(token) > 1:
    switches, letter, value = split(token); option = f"-{letter}"
    if letter and option in _VALUE_OPTIONS and value: span(i, i+1, option, value.removeprefix("="))   # -xmslow, -m=slow
    elif letter and option in _VALUE_OPTIONS and i+1 < len: span(i, i+2, option, tokens[i+1]); i += 1  # -xm slow
    positionals (no leading "-", e.g. tests/test_markers.py) never reach split_short_group
```

## DATA
- `split_short_group("-svrw") == ("sv", "r", "w")`, `("-vkrs") == ("v", "k", "rs")`,
  `("-pno:cacheprovider") == ("", "p", "no:cacheprovider")`, `("-vWerror") == ("v", "W", "error")`,
  `("-xvs") == ("xvs", None, "")`, `("-m") == ("", "m", "")`.
- `sanitize_extra_args(["-svrw"])` → `cleaned_args == ["-rw"]`, `verbosity == 1`, `show_output is True`.
- `sanitize_extra_args(["-rs"])` → unchanged, `show_output is False`. `["-vkrs"]` → `["-krs"]`, verbosity 1.

## Tests (write first)
`test_short_groups.py`:
- parametrized `split_short_group` cases above.
- `sanitize_extra_args`: `-svrw` → `-rw` + show_output; `-rs`, `-rfEs`, `-ktest_s`, `-xktest_pass` are not `-s`;
  `-vrs` → `["-rs"]`, verbosity 1; `-xvs` → `["-x"]` (existing behaviour kept); `-qs` → `["-q"]`.
- `effective_config` regression (#294 detection), env cleaned by the root conftest:
  `-pno:cacheprovider` → `numprocesses is False`; `-vWerror` sets no `-r`/`-n`; `["-xm", "slow"]` → `m.value == "slow"`;
  `-vkrs` → `k.value == "rs"`; `-nauto` → `numprocesses is True`; `-m=slow` → `"slow"`;
  `["-xm", "slow", "tests/x.py"]` → `m.value == "slow"` (separate-value branch, `slow` consumed).
- `_option_spans` regression: positionals with value-option letters (`tests/test_markers.py`, `tests/test_numbers.py`,
  `markers`) give no span; `effective_config` with them → `m is None`, `numprocesses is False`.
`test_extra_args.py`: move `["-vrs"]` out of `test_non_switch_args_pass_through` (it is now rewritten to `-rs`).
