# Step 1 — Shared helpers `utils/report_counts.py`

## LLM prompt

Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_1.md`) only.
Write the tests first, then the module. Run pylint, pytest (`-n auto`), mypy and lint-imports; all must
pass. One commit.

## WHERE

- Create `src/mcp_tools_py/utils/report_counts.py`
- Create `tests/test_report_counts.py`

## WHAT

```python
def plural(count: int, word: str) -> str: ...
def format_dir_split(paths: Iterable[str]) -> str: ...
def format_total_line(tool: str, issues: int, rules: int) -> str: ...
def _top_level_dir(path: str) -> str: ...  # private
```

## HOW

Stdlib only (`os`, `re`, `collections.Counter`). No project imports. Imported later by the four
`code_checker_*` reporting modules and allowed by the `layers` contract.

## ALGORITHM

```
_top_level_dir(path):
    if path == "Command line": return "(outside)"
    p = path.replace("\\", "/")
    if p.startswith("/") or re.match(r"^[A-Za-z]:", p) or p == ".." or p.startswith("../"): return "(outside)"
    p = p.removeprefix("./"); head, sep, _ = p.partition("/")
    return head if sep else "(root)"
format_dir_split(paths): counts = Counter(map(_top_level_dir, paths))
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return "(" + ", ".join(f"{k}: {v}" for k, v in items) + ")"
```

## DATA

- `plural(1, "issue") == "1 issue"`, `plural(0, "rule") == "0 rules"`, `plural(3, "occurrence") == "3 occurrences"`
- `format_dir_split(["src/a.py", "tests\\b.py", "tests/c.py", "setup.py"]) == "(tests: 2, (root): 1, src: 1)"`
  (ties alphabetical: `"(root)" < "src"`)
- `format_total_line("ruff", 143, 8) == "ruff found 143 issues across 8 rules"`
- `format_total_line("mypy", 1, 1) == "mypy found 1 issue across 1 rule"`

## Tests (`tests/test_report_counts.py`)

- `plural` singular/plural/zero.
- `_top_level_dir` via `format_dir_split`: `/` and `\` separators; root file → `(root)`;
  `C:\x\a.py`, `/abs/a.py`, `../a.py`, `..`, `Command line` → `(outside)`; nested `src/pkg/tests/a.py` → `src`.
- Order: count descending, ties alphabetical.
- `format_total_line` singular and plural, and `0 issues across 0 rules`.
