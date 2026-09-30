# Step 1 — Remove `-s` in `sanitize_extra_args` and record `show_output`

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_1.md`. Use TDD: rewrite and extend the tests in `tests/test_code_checker_pytest/test_extra_args.py` first, then change `SanitizedArgs` and `sanitize_extra_args`. Run pylint, pytest (`-n auto`) and mypy until all pass. Make exactly one commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/models.py`
- `src/mcp_tools_py/code_checker_pytest/utils.py`
- `tests/test_code_checker_pytest/test_extra_args.py`

## WHAT

```python
@dataclass
class SanitizedArgs:
    cleaned_args: List[str]
    verbosity: int
    notes: List[str]
    has_path_args: bool = False
    show_output: bool = False          # new

def sanitize_extra_args(extra_args, markers, project_dir="") -> SanitizedArgs  # signature unchanged
```

Module-level constants in `utils.py`:

```python
_SWITCH_LETTERS = set("xvsql")
SHOW_OUTPUT_NOTE = (
    "Note: -s was not passed to pytest. It was turned into the captured-output "
    "display: output printed by passing tests is shown below."
)
```

## HOW

- Keep the existing `for` loop and its `skip_next` handling. Switch to `enumerate` so `--capture` can look at the next argument.
- Delete the old exact-match `-v`/`-vv`/`-vvv` branch, because the new split branch covers it.
- Delete the whole xdist-aware `-s` strip block and its note.
- Leave path detection unchanged. It runs on the cleaned list.
- Docstring limitations:
  - Remove the "pass through as-is" bullet and the xdist bullet.
  - Add: split only single-dash tokens made entirely of `x v s q l` letters.
  - Add: an `-s` in `addopts` or `PYTEST_ADDOPTS` still disables capture.
  - Add: prints at import or collection time are not shown.
  - Keep the `-m=slow` bullet.

## ALGORITHM

```
for i, arg in enumerate(extra_args):
    if skip_next: skip_next = False; continue
    if len(arg) > 1 and arg[0] == "-" and arg[1] != "-" and set(arg[1:]) <= _SWITCH_LETTERS:
        if "v" in arg: verbosity = arg.count("v")
        if "s" in arg: show_output = True
        cleaned += [f"-{c}" for c in arg[1:] if c in "xql"]; continue
    if arg == "--capture=no": show_output = True; continue
    if arg == "--capture" and next arg == "no": show_output = True; skip_next = True; continue
    ... existing "tests" and "-m" branches, then cleaned.append(arg)
if show_output: notes.append(SHOW_OUTPUT_NOTE)
```

## DATA

| Input | `cleaned_args` | `verbosity` | `show_output` |
|---|---|---|---|
| `["-s"]` | `[]` | 2 | True |
| `["--capture=no"]` | `[]` | 2 | True |
| `["--capture", "no"]` | `[]` | 2 | True |
| `["-xvs"]` | `["-x"]` | 1 | True |
| `["-qs"]` | `["-q"]` | 2 | True |
| `["-vv", "-xvs"]` | `["-x"]` | 1 | True |
| `["-s", "-n", "auto"]` | `["-n", "auto"]` | 2 | True |
| `["-s", "-n", "0"]` | `["-n", "0"]` | 2 | True |
| `["-v"]` / `["-vvv"]` | `[]` | 1 / 3 | False |

These arguments pass through unchanged, with `show_output` False: `-vrs`, `-rfEs`, `-ktest_s`, `-kfoo`, `-xktest_pass`, `-oxfail_strict=true`, `["-p", "no:cacheprovider"]`, `["-n", "2"]`, `--capture=sys`, `["--capture", "tee-sys"]`, `--capture=fd`.

## Tests (write first)

In `tests/test_code_checker_pytest/test_extra_args.py`:

- Delete `test_lone_s_flag_passes_through`, `test_s_stripped_when_xdist_active`, `test_s_preserved_with_n_zero` and `test_numprocesses_long_form_does_not_trigger_strip`.
- Add a `parametrize` test over the `-s` spelling rows in the DATA table. It checks `cleaned_args`, `verbosity` and `show_output`, and that `SHOW_OUTPUT_NOTE` is in `notes` exactly once, including for `["-s", "--capture=no"]`.
- Add a `parametrize` test over the passthrough list. It checks that `cleaned_args` equals the input, `show_output` is False and `notes == []`.
- Update `test_combined_deduplication`:
  - input `["-s", "-vvv", "-m", "slow", "tests", "-x"]` with markers `["unit"]`
  - expected `cleaned_args == ["-x"]`, `verbosity == 3`, `show_output` True
  - two notes: the `-m` note and `SHOW_OUTPUT_NOTE`
- Keep the existing verbosity parametrize test. It still passes.
