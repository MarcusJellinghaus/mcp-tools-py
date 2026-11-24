# Step 3 — `report_data.py` basics

## LLM prompt
Read `pr_info/steps/summary.md` (design change 3) and this file; issue #293 "Data shape", "xdist longrepr header"
and "Paths" constraints define the inputs. Implement test-first. Run pylint, mypy and the non-integration pytest
suite. One commit.

## WHERE
- Create `src/mcp_tools_py/code_checker_pytest/report_data.py`
- `src/mcp_tools_py/code_checker_pytest/models.py`: `Warning.lineno: int | None = None`
- Tests: new `tests/test_code_checker_pytest/test_report_data.py`

## WHAT
```python
def strip_xdist_header(longrepr: str | None) -> str | None:
    """Drop a leading "[gwN] ..." line; None when nothing remains."""

def relative_path(path: str, root: str) -> str:
    """`path` relative to `root` in posix form; `path` as given when that is not possible."""

def format_log_record(record: LogRecord) -> str:
    """One record in pytest's default log format, then exc_text lines if any."""
```

## ALGORITHM
```
strip_xdist_header: if text and re.match(r"\[gw\d+\]", first line): text = rest; return text or None
relative_path:
    if path.startswith("<"): return path                     # <frozen ...>, <string>
    try rel = os.path.relpath(path, root) except ValueError: return path   # other drive
    return path if rel.startswith("..") else Path(rel).as_posix()
format_log_record: f"{r.levelname:<8} {r.name}:{r.filename}:{r.lineno} {r.msg}" + ("\n" + r.exc_text if r.exc_text)
```

## DATA
- `strip_xdist_header("[gw0] win32 -- Python 3.12 C:\\py.exe")` → `None`;
  `"[gw1] linux -- Python\nE  boom"` → `"E  boom"`; text without header unchanged.
- `format_log_record(...)` → `"WARNING  app:mod.py:12 disk low"`.

## Tests (write first)
Header strip (with/without header, header only); `relative_path` inside root, outside root, `<frozen os>`,
other drive (patch `os.path.relpath` to raise `ValueError`); log formatting with and without `exc_text`;
`parse_pytest_report` keeps an int `lineno` on warnings.
