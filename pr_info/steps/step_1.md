# Step 1: `from-global` import style preference

> **Context**: See [summary.md](summary.md) for full issue overview.

## Goal

Set rope's `preferred_import_style` to `"from-global"` so all rope operations produce
`from pkg.mod import symbol` instead of `import pkg.mod` with fully-qualified usage.

## WHERE

- `src/mcp_tools_py/refactoring/rope_tools.py` — `_with_rope_project()`
- `tests/test_refactoring/test_rope_tools.py` — new test

## WHAT

### Production change

In `_with_rope_project()`, after creating the `Project` object, set the preference:

```python
project.prefs["prefer_module_from_imports"] = True
```

> **Note**: Rope's `from-global` preference is controlled by `prefer_module_from_imports`
> on the project prefs object. This makes rope use `from X import Y` style.

### Test

```python
def test_move_symbol_uses_from_import_style(sample_project: Path) -> None:
    """move_symbol should produce 'from ... import' style, not 'import ...' style."""
```

## HOW

The `_with_rope_project()` context manager is used by all three `_*_impl` functions.
Setting the preference there applies globally — no other integration points needed.

## ALGORITHM

```
1. Create Project object (existing code)
2. Set project.prefs["prefer_module_from_imports"] = True  # NEW
3. yield project (existing code)
4. Close project (existing code)
```

## DATA

No change to return values. The effect is observable in generated import statements:
- Before: `import src.foo` + `src.foo.my_func()`
- After: `from src.foo import my_func` + `my_func()`

## TEST PLAN

1. Write test: move `my_func` from `foo.py` to `baz.py`, read `bar.py` (consumer),
   assert import line contains `from` and `import my_func` (not `import src.baz`
   followed by `src.baz.my_func`).
2. Run pylint, pytest (unit only), mypy.

## LLM PROMPT

```
Implement Step 1 from pr_info/steps/step_1.md (see pr_info/steps/summary.md for context).

Set rope's preferred import style to "from-global" in _with_rope_project() and add a
test that verifies move_symbol produces "from ... import" style imports in consumer files.

After making changes, run all three code quality checks (pylint, pytest unit tests, mypy).
Fix any issues before committing. Commit message: "feat(refactoring): set from-global import style in rope project"
```
