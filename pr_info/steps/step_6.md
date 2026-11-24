# Step 6 — Resolver `resolve_workers` and the `workers:` line

## LLM prompt
Read `pr_info/steps/summary.md` (especially the "`workers:` line rules" table), then implement **this step only** (`pr_info/steps/step_6.md`).
First write `tests/test_code_checker_pytest/test_workers_resolve.py` (table-driven over every line example in the summary and issue #298), then add `WorkersPlan` and `resolve_workers` to `src/mcp_tools_py/code_checker_pytest/workers.py`.
Run `run_format_code`, pylint, pytest (`markers=["not integration"]`) and mypy; all must pass. Make one commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/workers.py`
- Create `tests/test_code_checker_pytest/test_workers_resolve.py`

## WHAT
```python
@dataclass(frozen=True)
class WorkersPlan:
    env: dict[str, str] | None   # pass to run_tests: env_vars unchanged, or a copy with ENV_KEY set
    serial: bool                 # the resolved / pre-set count is 0
    note: str | None             # "workers: ..." or None

def resolve_workers(effective: EffectiveConfig, env_vars: dict[str, str] | None) -> WorkersPlan: ...
def _is_env_key(key: str) -> bool: ...                    # key == ENV_KEY, or os.name == "nt" and key.upper() == ENV_KEY
def _preset(env_vars: dict[str, str] | None) -> str: ...  # caller's value wins (last match), else os.environ.get(ENV_KEY, "")
def _with_count(env_vars: dict[str, str] | None, count: int) -> dict[str, str]: ...  # copy without caller's variants + ENV_KEY
def _shown(count: int) -> str: ...                        # "serial" if count == 0 else str(count)
```
`EffectiveConfig` / `OptionValue` come from `pytest_config` (same package).

## HOW
- Never mutate `env_vars`. When nothing is injected, return the **same object** (`env=env_vars`).
- Case-insensitive key matching uses the real `os.name == "nt"`, never `_is_windows()`.
- `os.environ.get` is already case-insensitive on Windows.
- Source labels for a numeric `-n`: `{"pyproject.toml": "pyproject.toml addopts", "-o": "-o addopts"}`; other sources are shown as they are (`PYTEST_ADDOPTS`, `extra_args`).
- Never raises: the loader and sampler are already guarded.

## ALGORITHM
```
s = read_pytest_workers(); ign = [f"ignored {s.problem}"] if s.problem else []
line = lambda shown, *why: f"workers: {shown} ({'; '.join([*why, *ign])})"
n = effective.n
if n is None or n.value not in ("auto", "logical"):
    if not s.in_config: return Plan(env_vars, False, None)
    if n is None: return Plan(env_vars, False, line("no -n", "pytest_workers applies to -n auto only"))
    shown = "serial" if n.value == "0" else n.value
    return Plan(env_vars, False, line(shown, f"-n {n.value} from {label(n.source)}", "pytest_workers applies to -n auto only"))
pre = _preset(env_vars)
if pre: try int(pre) → Plan(env_vars, int == 0, line(_shown(int), ENV_KEY))
        except ValueError → Plan(env_vars, False, line("xdist default", f'{ENV_KEY}="{pre}" is not an integer'))
if s.value == "all": return Plan(env_vars, False, line("xdist default", "all, config.toml"))
if isinstance(s.value, int): count, why = s.value, "config.toml"
elif not _is_windows(): return Plan(env_vars, False, line("xdist default", "auto, not Windows"))
else: idle, logical = sample_idle(), os.cpu_count()
      if idle is None or logical is None: return Plan(env_vars, False, line("xdist default", "auto, Windows, CPU load unavailable"))
      count, why = workers_for(logical, idle), f"auto, Windows, CPU load {round(100 * (1 - idle))} %"
return Plan(_with_count(env_vars, count), count == 0, line(_shown(count), why))
```
(Sketch only. Write `line` as a small helper function, not a lambda.)

## DATA — expected lines (assert exact strings)
- `workers: 3 (auto, Windows, CPU load 71 %)` — 24 cores, idle 29/100
- `workers: serial (auto, Windows, CPU load 92 %)`
- `workers: 4 (config.toml)`; `workers: serial (config.toml)` for `0`; `workers: 1 (config.toml)` for `1`
- `workers: xdist default (all, config.toml)`
- `workers: xdist default (auto, not Windows)`
- `workers: xdist default (auto, Windows, CPU load unavailable)` — sampler `None`, or `os.cpu_count()` `None`
- `workers: 6 (PYTEST_XDIST_AUTO_NUM_WORKERS)`; `workers: serial (PYTEST_XDIST_AUTO_NUM_WORKERS)` for `"0"`
- `workers: xdist default (PYTEST_XDIST_AUTO_NUM_WORKERS="x" is not an integer)`
- `workers: 8 (-n 8 from pyproject.toml addopts; pytest_workers applies to -n auto only)` — config set
- `workers: serial (-n 0 from extra_args; pytest_workers applies to -n auto only)` — config set
- `workers: no -n (pytest_workers applies to -n auto only)` — config set, no `-n`
- `workers: no -n (pytest_workers applies to -n auto only; ignored config.toml: invalid TOML)`
- `workers: 6 (auto, Windows, CPU load 48 %; ignored pytest_workers = "x" in config.toml)`
- Numeric `-n` or no `-n`, config not set → `note is None`, `env is env_vars`.

## Tests (write first) — `test_workers_resolve.py`
- Build `EffectiveConfig` via the real `effective_config(str(tmp_path), None, extra_args, env_vars)` on a `tmp_path` project (with or without `[tool.pytest.ini_options] addopts`). Write config with the `user_config` fixture.
- For Windows cases, monkeypatch `workers._is_windows` → `True`, `workers.sample_idle` → a `Fraction`, and `workers.os.cpu_count` → `24`.
- Acceptance coverage:
  - ~100 % load (idle `Fraction(1, 100)`) → serial, env `"0"`.
  - Idle machine (idle `Fraction(1)` / `Fraction(23, 24)`) → 12 / 11.
- `-n logical` from `extra_args` is sized like `auto`.
- Pre-set: from `env_vars` and from `os.environ` (monkeypatch.setenv); a pre-set value skips sampling (assert `sample_idle` is not called) but still reports an invalid config. Empty `""` pre-set counts as unset (sizing applies). When both the caller and the server set it, the caller's value is reported.
- On `os.name == "nt"` only (skipif otherwise): a lowercase caller key `pytest_xdist_auto_num_workers=""` is dropped from the injected copy, so exactly one spelling is left.
- The caller's dict is never mutated (compare to a copy before/after). With nothing injected, `plan.env is env_vars`.
- An injected env contains the caller's other keys plus `ENV_KEY`.
