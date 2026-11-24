# Step 5 — CPU sampler: platform seam, raw `GetSystemTimes`, exact math, median

## LLM prompt
Read `pr_info/steps/summary.md`, then implement **this step only** (`pr_info/steps/step_5.md`).
First extend the autouse fixture in `tests/conftest.py` and write `tests/test_code_checker_pytest/test_workers_cpu.py`, then add the functions to `src/mcp_tools_py/code_checker_pytest/workers.py`.
Run `run_format_code`, pylint, pytest (`markers=["not integration"]`) and mypy; all must pass. Make one commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/workers.py`
- `tests/conftest.py` (`_isolate_pytest_workers`)
- Create `tests/test_code_checker_pytest/test_workers_cpu.py`

## WHAT
```python
SystemTimes = tuple[int, int, int]   # (idle, kernel, user), 100-ns units; kernel includes idle

def _is_windows() -> bool: ...                                   # sys.platform == "win32"
def _get_system_times() -> SystemTimes | None: ...               # raw kernel32 call
def idle_fraction(before: SystemTimes, after: SystemTimes) -> Fraction | None: ...
def sample_idle(interval: float = 0.1) -> Fraction | None: ...   # median of 5 deltas
def workers_for(logical: int, idle: Fraction) -> int: ...
```

## HOW
- `_get_system_times`: put the Windows-only code inside `if sys.platform == "win32":` and return `None` from its `else:` branch. mypy silently skips whichever platform-check branch doesn't apply, so this passes `mypy --strict` with `warn_unreachable` on both Linux CI and Windows. An early `return None` guard leaves the code after it unreachable on Linux; a trailing `return None` after the block is unreachable on Windows. Use three `ctypes.c_ulonglong` (same layout as `FILETIME`) passed via `ctypes.byref` to `ctypes.windll.kernel32.GetSystemTimes`. A return of 0 → `None`. Wrap the call in `try/except (OSError, AttributeError, ctypes.ArgumentError)` → `None`.
- `_is_windows()` is the single seam for "should sizing sample?". It is **not** used for env-key case matching (step 6 uses `os.name`).
- `sample_idle` looks up `_get_system_times` through the module global, so the autouse patch applies.
- Extend `_isolate_pytest_workers` in `tests/conftest.py`:
  ```python
  monkeypatch.setattr(f"{_WORKERS}._is_windows", lambda: False)
  monkeypatch.setattr(f"{_WORKERS}._get_system_times", lambda: None)
  ```
- Tests of the real `_is_windows` / `_get_system_times` must import them at module import time, before the autouse patch:
  `from mcp_tools_py.code_checker_pytest.workers import _get_system_times as real_get_system_times`. Mark the raw-wrapper test `@pytest.mark.skipif(sys.platform != "win32", reason=...)`.

## ALGORITHM
```
idle_fraction:  d_idle = a.idle - b.idle; d_total = (a.kernel - b.kernel) + (a.user - b.user)
                return None if d_total <= 0 else Fraction(d_idle, d_total)
sample_idle:    readings = [first]; repeat 5×: sleep(interval); append reading   # any None → return None
                fractions = [idle_fraction(x, y) for x, y in pairwise(readings)]   # any None → None
                return sorted(fractions)[2]                                         # exact median of 5
workers_for:    n = (logical * idle.numerator) // (2 * idle.denominator)
                return n if n >= 2 else 0
```
Integer / `Fraction` arithmetic only. No floats.

## DATA
- `workers_for(24, Fraction(1))` → 12 (0 % load); `Fraction(3, 4)` → 9; `Fraction(1, 2)` → 6; `Fraction(1, 4)` → 3; `Fraction(1, 6)` → **2** (load exactly 5/6, the boundary); `Fraction(4, 25)` (84 % load) → 0; `Fraction(0)` → 0.
- `workers_for(24, Fraction(23, 24))` → 11 (idle machine: 11–12).

## Tests (write first) — `test_workers_cpu.py`
- `workers_for` table above, including the 5/6 boundary → 2 and ~100 % load → 0 (serial).
- `idle_fraction`: normal delta; zero total delta → `None`.
- `sample_idle(interval=0)` with `_get_system_times` monkeypatched to a generator of 6 readings: one burst sample among four steady ones → the median ignores the burst. Any `None` reading → `None`. A zero delta → `None`.
- Autouse default: `_is_windows()` is `False` and `sample_idle(interval=0)` is `None`.
- Windows only (skipif): `real_get_system_times()` returns three non-negative ints with `kernel >= idle`.

## Precondition
If mypy reports errors in the ctypes code that the `sys.platform` guard cannot resolve, write one line to `pr_info/.blocked.txt` and stop.
