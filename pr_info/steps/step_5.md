# Step 5 — `marker_hint.py`: expression scan and marker notes

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_5.md`), and
> issue #294 (Part 2, decisions 11, 13, 15, 17, 19, Constraints "`-m` name
> extraction", "Strictness", "Why the hint requires an unregistered name"). Steps 1–4
> are done. Implement step 5 only: tests first, then code, run the checks listed in
> the summary, then commit (one commit).

## WHERE

- New: `src/mcp_tools_py/code_checker_pytest/marker_hint.py`
- New: `tests/test_code_checker_pytest/test_marker_hint.py`

## WHAT

```python
BUILTIN_MARKERS = frozenset({"skip", "skipif", "xfail", "parametrize", "usefixtures",
                             "filterwarnings", "tryfirst", "trylast"})
STRICT_SUGGESTION = (
    "To have pytest reject unknown -m names (pytest 9+), turn on strict markers in "
    "the project config (--strict-markers in addopts, or strict_markers = true); "
    "tests carrying unregistered marks then fail collection."
)
RERUN_TIP = (
    "Under pytest-xdist pytest's own message is lost; to see it, "
    'rerun with extra_args=["-n", "0"].'
)

def scan_expression(expr: str) -> tuple[list[tuple[str, bool]], bool]:
    """Names in a -m expression with their negation, and whether it parses."""

def unknown_marker_names(error_line: str) -> list[str]:
    """Names from pytest's 'Unknown marker(s) in '-m' expression: …' line."""

def marker_notes(
    effective: EffectiveConfig, exit_code: int | None, marker_error: str | None
) -> list[str]:
    """pytest's -m ERROR line, the marker hint, the strict suggestion, the rerun tip."""
```

## HOW

- Imports `EffectiveConfig` from `code_checker_pytest.pytest_config`. No `_pytest`
  import (private API; the server's pytest can differ from the project's).
- Lexer regex, pytest's grammar: whitespace skipped; `(`, `)`, `,`, `=`; quoted
  strings `'…'` / `"…"`; ident `[\w:+\-.\[\]\\/]+`. Any other character → invalid,
  skipped. `and` / `or` / `not` are keywords.
- Not used by production code yet (step 6); vulture sees the tests.

## ALGORITHM — `scan_expression` (single pass, no recursion)

```
stack=[0]; pending=0; operand=True; valid=True; names=[]
for tok: if operand: "not"->pending+=1 | "("->stack.push((stack[-1]+pending)%2), pending=0
                     | ident->names+=(tok,(stack[-1]+pending)%2==1), pending=0, operand=False,
                              and if next tok is "(": read kwargs up to ")": one or more
                              `ident = value` separated by ","; value = ident or quoted string;
                              anything else, or no ")" -> valid=False
                     | else -> valid=False
         else: "and"/"or"->operand=True | ")"->pop if len(stack)>1 else valid=False
               | ident -> names+=(tok, False), valid=False | else -> valid=False
valid = valid and not operand and len(stack)==1
```

`True` / `False` / `None` at top level are names; inside kwargs they are skipped.

## ALGORITHM — `marker_notes`

```
notes = [marker_error] if exit_code == 4 and marker_error else []
m = effective.m; if not m or not m.value.strip(): return notes
cfg usable = effective.config is not None and effective.not_read is None
if usable and marker_error startswith "ERROR: Unknown marker(s)": counted = unknown_marker_names(marker_error)
elif usable and (exit 5 or (exit 4 and marker_error) or (exit 3 and effective.strict_markers)):
    counted = unregistered names from scan_expression(m.value) where not negated, or strict on, or not valid
if counted: notes += [hint(counted, cfg.markers)] + ([STRICT_SUGGESTION] if not effective.project_strict_markers else [])
if exit_code == 3 and effective.numprocesses: notes.append(RERUN_TIP)
```

Registered = `cfg.markers ∪ BUILTIN_MARKERS`. Counted names deduplicated, order kept.

## DATA — hint text

- one name: ``"`unit` is not registered in the project config. Registered: integration, slow"``
- several: ``"`a`, `b` are not registered in the project config. Registered: …"``
- project registers none: ``"`unit` is not registered in the project config. The project config registers none."``
- `Registered:` lists `cfg.markers` only (project markers, config order), not built-ins.

## Tests (write first) — `test_marker_hint.py`

`marker_notes` strict suggestion: table `strict_markers = true`, no `addopts` flag,
exit 5, `-m unit` → hint without `STRICT_SUGGESTION` (decision 13).

`scan_expression`:
- `unit` → `[("unit", False)]`, valid; `not unit` → negated; `not not unit` → not negated.
- `not (a or b) and c` → a, b negated, c not; `(not a) or b`.
- `mark(key="v", n=1, flag=True)` → only `mark`; top-level `True` is a name.
- `a b`, `a and`, `(a`, `a)`, `'x'`, `a $ b`, `mark()`, `mark(x)` → invalid, names
  still returned.
- `a.b:c/d[1]+e-f\\g` is one name.

`unknown_marker_names`: `a, b.c` from pytest 9's exact text; no match → `[]`.

`marker_notes` (build `EffectiveConfig` via `effective_config` on `tmp_path`):
- exit 5, `-m unit`, no strict, registers `integration, slow` → hint + suggestion.
- exit 5, `-m skip` → no notes.
- exit 5, `-m "not unit"` non-strict → none; `not not unit` → hint.
- exit 5, all names registered → none; no `-m` → none.
- exit 4 unrelated (`marker_error=None`) → none.
- exit 4 `Unknown marker(s) … : unit.` with config strict → ERROR line + hint, no
  suggestion; names come from the message even if the expression has others.
- exit 4 `Wrong expression passed to '-m'` with only registered names → only the
  ERROR line.
- exit 3, `-n 4`, strict on, unregistered → hint + `RERUN_TIP`; strict off → only
  `RERUN_TIP`; `-n 0` → no tip; no `-n` → no tip.
- `PYTEST_ADDOPTS="-o strict_markers=false"` + ini `--strict-markers`, exit 5,
  `-m "not unit"` → no hint (strict off); `-m unit` → hint without suggestion.
- `pytest.ini` present (or `-c x.ini`) → no hint even on exit 4 `Unknown marker(s)`,
  but the ERROR line stays; exit 3 under `-n` still gets `RERUN_TIP`.
- registers none → `The project config registers none.`
- toolkit contract: `markers=UNATTENDED_EXCLUDED_MARKERS`, `extra_args=["-o",
  "strict_markers=false"]`, ini `--strict-markers`, exit 5 → no notes.
