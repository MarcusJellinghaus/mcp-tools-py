# Step 6 — String-reference report (not rewritten)

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_6.md` only. Use TDD: write the tests first, then the change. Run pylint, pytest (`-n auto`) and mypy through the MCP tools and make them pass. Run `run_format_code`, then make one commit.

## WHERE

- `src/mcp_tools_py/refactoring/rope_tools.py`
- `src/mcp_tools_py/refactoring/__init__.py`: the `move_symbol` docstring
- `tests/test_refactoring/test_rope_tools.py`

## WHAT

```python
def _module_dotted(project_dir: Path, rel_file: str) -> str: ...
def _string_ref_lines(
    project_dir: Path, source_file: str, names: list[str]
) -> list[str]: ...
```

## ALGORITHM

`_module_dotted`:
```
path = project_dir / rel_file
parts = [] if path.name == "__init__.py" else [path.stem]
current = path.parent
while current != project_dir and (current / "__init__.py").exists():
    parts.insert(0, current.name); current = current.parent
return ".".join(parts)
```

For example, `src/mcp_tools_py/x.py` becomes `mcp_tools_py.x`.

`_string_ref_lines`:
```
targets = [f"{_module_dotted(...)}.{n}" for n in names]
with _with_rope_project(project_dir) as project: rels = sorted(r.path for r in project.get_python_files())
for rel in rels: tree = ast.parse(read(rel)), skipping SyntaxError/ValueError/UnicodeDecodeError/OSError
    for node in ast.walk(tree): if str Constant s and any(s == t or s.startswith(t + ".")):
        hits.append(f"  {rel}:{node.lineno}: {s!r} (not rewritten)")
return ["String references to moved names (not rewritten):", *hits] if hits else []
```

## HOW

- Dry run: after the symbol loop, which leaves the tree unmodified, add `_string_ref_lines(project_dir, source_file, symbol_names)` before the notes.
- Real run: call it after `_remove_self_imports` and add it before the notes.
- The source file is part of `get_python_files()`, so it gets scanned in both modes.
- Never rewrite anything.
- Add to the tool docstring in `refactoring/__init__.py`: string literals that refer to moved names, such as `@patch("pkg.mod.name")`, are listed but not rewritten. `patch.object(mod, "name")` and strings that go through a re-exporting module aren't detected.

## DATA

`list[str]` of output lines. It's empty when there are no hits, and then the section is left out.

## Tests

Add `test_x.py` to the sample project at its root, where there's no `__init__.py`. It contains a line with `"src.foo.my_func"` and a line with `"src.foo.my_func_other"`.

- `test_move_symbol_dry_run_reports_string_refs`: a dry run of `my_func` contains `String references to moved names (not rewritten):` and `test_x.py:<line>: 'src.foo.my_func'`, and doesn't contain `my_func_other`.
- `test_move_symbol_real_run_reports_string_refs`: the same check for a real run. Also check that `test_x.py` is unchanged on disk.
- `test_module_dotted`: `src/foo.py` gives `src.foo`, `src/__init__.py` gives `src`, and a file in a dir without `__init__.py` gives just its stem.

Keep `test_rope_tools.py` under 750 lines. Check with `check_file_size(max_lines=750)`.
