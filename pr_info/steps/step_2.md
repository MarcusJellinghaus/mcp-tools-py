# Step 2 — `effective_config` and `addopts_notes`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_2.md`), and
> issue #294 (Part 1, decisions 6, 9, 10, 11, 15, Constraints "Strictness follows
> pytest's order", "`-o addopts=` does not clear `PYTEST_ADDOPTS`", "`PYTEST_ADDOPTS`
> lookup", "`markers=[]`", "`-o addopts=` and `-c` are scanned only in the call and
> `PYTEST_ADDOPTS`"). Step 1 is done. Implement step 2 only: tests first, then code,
> run the checks listed in the summary, then commit (one commit).

## WHERE

- Modified: `src/mcp_tools_py/code_checker_pytest/pytest_config.py`
- New: `tests/test_code_checker_pytest/test_effective_config.py`

## WHAT

```python
INI_WAY_OUT = 'extra_args=["-o", "addopts="]'
ENV_WAY_OUT = 'env_vars={"PYTEST_ADDOPTS": ""}'

@dataclass(frozen=True)
class OptionValue:
    value: str
    source: str  # "pyproject.toml" | "-o" | "PYTEST_ADDOPTS" | "markers" | "extra_args"

@dataclass(frozen=True)
class EffectiveConfig:
    config: PytestConfig | None   # None: config unreadable
    not_read: str | None          # config.not_read, or the -c/--config-file value
    ini_source: str               # "pyproject.toml", "-o" (call) or "PYTEST_ADDOPTS" (-o inside it)
    ini_tokens: list[str]         # applied ini addopts; [] when none, cleared or not read
    env_tokens: list[str]         # shlex.split(PYTEST_ADDOPTS); [] when unset/empty/unparsable
    m: OptionValue | None         # effective -m; value "" = explicit empty -m
    k: OptionValue | None         # effective -k
    numprocesses: bool            # last -n/--numprocesses value is not "0"
    strict_markers: bool          # effective, all sources
    project_strict_markers: bool  # project config alone: config.addopts + table keys

def effective_config(
    project_dir: str,
    markers: list[str] | None,
    cleaned_args: list[str],
    env_vars: dict[str, str] | None,
) -> EffectiveConfig: ...

def addopts_notes(effective: EffectiveConfig) -> list[str]: ...
```

Private helpers (one each, keep small):

```python
def _option_events(tokens: list[str]) -> list[tuple[str, str]]   # (canonical option, value)
def _env_addopts(env_vars: dict[str, str] | None) -> str
def _split(value: str) -> list[str]                                # shlex.split; ValueError -> []
def _strict_markers_on(tokens: list[str], table: PytestConfig | None) -> bool
def _render_line(label: str, tokens: list[str], replaced_by: str | None, way_out: str | None) -> str
```

`_parse_bool` from step 1 is reused for `-o strict_markers=v` / `-o strict=v`.

## HOW

- `_option_events` is the single scanner. Spec table:
  `{"-m": "-m", "-k": "-k", "-n": "-n", "--numprocesses": "-n", "-o": "-o",
  "--override-ini": "-o", "-c": "-c", "--config-file": "-c"}` plus the flags
  `--strict-markers`, `--strict` (value `""`). Spellings: `X v` (consumes next),
  `--long=v`, `-Xv`, `-X=v` (strip one leading `=`).
- `_env_addopts`: start from `os.environ.get("PYTEST_ADDOPTS", "")`; an `env_vars`
  key equal to `PYTEST_ADDOPTS` (case-insensitive when `os.name == "nt"`) replaces it.
- Call tokens: `["-m", " and ".join(markers)]` when `markers` is non-empty (source
  `markers`), then `cleaned_args` (source `extra_args`). `markers=[]` adds nothing.
- `read_pytest_config(project_dir)` from step 1 supplies `config`.

## ALGORITHM

```
config = read_pytest_config(dir); env = _env_addopts(env_vars); env_tokens = _split(env)
pass 1 over env_tokens then call tokens: last "-c" -> not_read; last "-o addopts=X" -> (X, origin)
not_read = -c value or (config.not_read if config) ; ini = [] if not_read or config is None
ini = _split(X) with source "-o"/"PYTEST_ADDOPTS" if override else config.addopts ("pyproject.toml")
    # _split never raises: unbalanced quotes give [], so today's error path is unchanged
pass 2 over [(ini_source, ini), ("PYTEST_ADDOPTS", env), ("markers", m_tok), ("extra_args", args)]:
    last -m / -k -> OptionValue(value, source); last -n -> numprocesses = value != "0"
strict: sm, s = table values; walk all tokens in order: --strict-markers/-o strict_markers=v -> sm; --strict/-o strict=v -> s; on = sm if sm is not None else bool(s)
```

`project_strict_markers` = `_strict_markers_on(config.addopts, config)`: the walk over
the project's ini `addopts` only, starting from the table keys `strict_markers` /
`strict` (decision 13). False when config is None or not read.

## DATA — `addopts_notes` output

- `not_read` → `["pytest config is in <file>, not read"]` and nothing else.
- `config is None` → `[]`.
- ini line, when `ini_tokens` and `ini_source != "PYTEST_ADDOPTS"`:
  - applied: `addopts (pyproject.toml): -n auto -m 'not slow' — to run without: extra_args=["-o", "addopts="]`
  - replaced (effective `m.source` differs from this line's source and the line has
    an `-m`): `addopts (pyproject.toml): -n auto; its -m 'not slow' was replaced by markers — to run without: extra_args=["-o", "addopts="]`
  - `ini_source == "-o"`: `addopts (-o): <tokens>`, no way out. When a later `-m`
    replaces an `-m` inside `<tokens>`, the same replaced form applies:
    `addopts (-o): -x; its -m slow was replaced by extra_args` (decision 6: a
    replaced `-m` is never shown as applied).
  - replaced `-m` is the whole `addopts` (nothing else left): no empty
    `<label>: ;` prefix. E.g. `addopts = "-m 'not slow'"` plus `markers=["fast"]` →
    `addopts (pyproject.toml): -m 'not slow' was replaced by markers — to run without: extra_args=["-o", "addopts="]`.
    Same rule for the `addopts (-o)` and env lines.
- env line, when `env_tokens`: `PYTEST_ADDOPTS: <tokens> — to run without: env_vars={"PYTEST_ADDOPTS": ""}`,
  same replaced form (replacing source `markers` or `extra_args`).
  - `-o addopts=X` inside `PYTEST_ADDOPTS` (`ini_source == "PYTEST_ADDOPTS"`) whose
    `-m` was replaced by the call: the `-o addopts=X` value is rendered with the
    same replaced-form helper as the `addopts (-o)` bullet, so its `-m` is not shown
    as applied: `PYTEST_ADDOPTS: -o addopts=-x; its -m slow was replaced by extra_args — to run without: env_vars={"PYTEST_ADDOPTS": ""}`.
- Values rendered with `shlex.join`; the replaced `-m` with `shlex.quote`; a line's
  `-m` tokens (all spellings) are removed from the shown values when replaced.
- One private helper renders every line (ini, `-o`, env, and the `-o addopts=X`
  value inside the env line):
  `_render_line(label, tokens, replaced_by, way_out) -> str` — drops the `-m`
  tokens when `replaced_by` is set and picks the `…; its -m X was replaced by S` or
  the `-m X was replaced by S` (nothing left) form; `way_out` is appended as
  ` — to run without: …` when given.

## Tests (write first) — `test_effective_config.py`

Use `tmp_path` projects with a `pyproject.toml`; set `PYTEST_ADDOPTS` via
`monkeypatch` or `env_vars`.

- `-m X`, `-mX`, `-m=X` in `extra_args` → `m.value == "X"`, source `extra_args`.
- `markers=["a","b"]` → `"a and b"`, source `markers`; `extra_args` `-mX` after it wins.
- `extra_args=["-m", ""]` with `addopts -m slow` → `m.value == ""`, source `extra_args`.
- list `addopts = ["-m", "not slow"]` → `m.value == "not slow"` (not `'not'`).
- `PYTEST_ADDOPTS="-m fast"` beats ini `-m slow`; call beats both.
- `-o addopts=`, `-oaddopts=`, `--override-ini addopts=`, `--override-ini=addopts=`
  in the call and in `PYTEST_ADDOPTS` → `ini_tokens == []`; `-o addopts=-x` in the
  call → `ini_source == "-o"`, tokens `["-x"]`.
- unbalanced quotes: `extra_args=["-o", "addopts=-m 'x"]` and
  `PYTEST_ADDOPTS="-o \"addopts=-m 'x\""` → `ini_tokens == []`, no raise; an
  unparsable `PYTEST_ADDOPTS` → `env_tokens == []`, no raise.
- `-c f.ini`, `-cf.ini`, `-c=f.ini`, `--config-file f.ini`, `--config-file=f.ini`
  (call and `PYTEST_ADDOPTS`) → `not_read == "f.ini"`; `-c` inside ini addopts ignored.
- `env_vars={"PYTEST_ADDOPTS": ""}` clears an inherited value; on Windows a
  lower-case key also matches (`skipif os.name != "nt"`).
- strictness: `strict_markers=false` + addopts `--strict-markers` → on;
  `strict_markers=false` + `--strict` → off; `-o strict_markers=false` beats
  `strict = true`; `PYTEST_ADDOPTS="-o strict_markers=false"` beats ini
  `--strict-markers` (and `project_strict_markers` stays True).
- table `strict_markers = true` with no `addopts` flag → `project_strict_markers`
  is True.
- `-n 4`, `-n0`, `--numprocesses=auto`, last wins; none → False.
- `addopts_notes`: applied line, replaced line (each replacing source: `markers`,
  `extra_args`, `PYTEST_ADDOPTS`), `addopts (-o)` line, `extra_args=["-o",
  "addopts=-x -m slow", "-m", "fast"]` → `addopts (-o): -x; its -m slow was replaced
  by extra_args` (no `-m slow` shown as applied), env line, both cleared → no ini
  line, not-read note, `config is None` → `[]`.
- `addopts_notes`, whole `addopts` replaced: `addopts = "-m 'not slow'"`,
  `markers=["fast"]` → exactly `addopts (pyproject.toml): -m 'not slow' was replaced by markers — to run without: extra_args=["-o", "addopts="]`
  (no `addopts (pyproject.toml): ;`).
- `addopts_notes`, `-o addopts=` inside `PYTEST_ADDOPTS`:
  `PYTEST_ADDOPTS="-o 'addopts=-x -m slow'"`, `extra_args=["-m", "fast"]` → no ini
  line; env line `PYTEST_ADDOPTS: -o addopts=-x; its -m slow was replaced by extra_args — to run without: env_vars={"PYTEST_ADDOPTS": ""}`
  (no `-m slow` shown as applied).
