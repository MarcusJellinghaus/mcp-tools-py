# User Configuration

Machine-wide settings for mcp-tools-py, kept in mcp-coder's user config.

---

## Where

`~/.mcp_coder/config.toml`, section `[mcp_tools_py]`:

```toml
[mcp_tools_py]
pytest_workers = "auto"   # "auto" | "all" | integer >= 0 (0 = serial)
```

- This is the **user** section `[mcp_tools_py]`. It is distinct from the
  **project** section `[tool.mcp-tools-py]` in `pyproject.toml`
  ([Project Configuration](pyproject-configuration.md)).
- The file is read on every pytest run, so a change applies without
  restarting the server.
- There is no env var and no server flag for this setting.

---

## `pytest_workers`

Defines how many pytest-xdist workers `-n auto` starts. If the file or the key
is missing, the value is `"auto"`.

| Value | Windows | Other OS |
|---|---|---|
| `"auto"` (default) | load-based formula ([below](#formula)) | xdist's default `-n auto` |
| `"all"` | xdist's default `-n auto` (sizing off) | xdist's default `-n auto` |
| integer `N` | `N` workers, `0` = serial | `N` workers, `0` = serial |

- Types are strict: the string `"4"` is invalid, and so is `true`.
- An integer is used as given; it is not capped at the number of CPUs.
- `pytest_workers = 1` still runs under xdist with one worker. Only `0` is
  serial.

---

## Scope

The setting only defines what `-n auto` / `-n logical` means. It applies when
the effective `-n` is `auto` or `logical`, wherever that comes from: the
project's `addopts`, `PYTEST_ADDOPTS` or the caller's `extra_args`.

- A numeric `-n N`, from the caller or the project, is never changed.
- With no `-n` anywhere, nothing is added, so a project without pytest-xdist is
  unaffected.
- The command line and the project's `addopts` are never rewritten. The count
  reaches xdist through `PYTEST_XDIST_AUTO_NUM_WORKERS` on the pytest
  subprocess.
- A caller's `-n auto` in `extra_args` does not bypass sizing; a numeric `-n N`
  does.

---

## Resolution order

For one pytest run:

1. If the effective `-n` is not `auto` or `logical`, sizing doesn't apply.
2. If `PYTEST_XDIST_AUTO_NUM_WORKERS` is already set, in the caller's
   `env_vars` or the server's environment, it is left alone and reported as the
   source. `pytest_workers` is not applied and the CPU is not sampled, but
   `config.toml` is still read, so a problem with it still shows on the
   `workers:` line.
   - Only a non-empty value counts as set (xdist treats `""` as unset).
   - When both the caller's `env_vars` and the server environment have it, the
     caller's value wins. On Windows the key matches case-insensitively.
   - A non-integer value is left alone; xdist ignores it and uses its default.
3. `pytest_workers = "all"`: the variable is not set (xdist's default).
   An integer `N`: the variable is set to `N`.
4. `pytest_workers = "auto"`: on Windows, the CPU load is sampled and the
   variable is set to the [formula](#formula)'s count. If sampling fails, or
   the number of logical CPUs is unknown, the variable is not set (xdist's
   default). On other operating systems the variable is not set.

The caller's `env_vars` are never modified; the variable is added to a copy.

---

## Formula

```
n = floor(0.5 × logical cores × (1 − CPU load))
```

If `n < 2`, the run is serial (`PYTEST_XDIST_AUTO_NUM_WORKERS=0`), because
xdist's startup costs more than one worker saves. The arithmetic is exact, so
the boundaries below hold exactly.

| Load | 0 % | 25 % | 50 % | 75 % | ≥ 84 % |
|---|---|---|---|---|---|
| Workers on 24 logical / 12 physical cores | 12 | 9 | 6 | 3 | serial |

With 24 logical cores, the run is serial above 83.3 % load (load > 5/6).

Why half the logical cores: with SMT, Windows reports load across all logical
processors, so 50 % can already mean every physical core is busy. Half the
logical cores roughly matches the physical cores, so an idle machine keeps
roughly xdist's default speed. A machine without SMT gets half its cores when
idle.

**Small machines** are serial under most loads, because `n ≥ 2` needs
`logical × (1 − load) ≥ 4`:

| Logical cores | Serial above |
|---|---|
| 4 | 0 % load |
| 8 | 50 % load |
| 12 | 66.7 % load |

**Sampling:** the median of 5 intervals of 100 ms each, from kernel32
`GetSystemTimes` (through `ctypes`, no extra dependency). It runs only on the
`auto` path on Windows and costs about 0.5 s per run; every other path costs
nothing. Sessions that start at the same moment all see the same low load and
all pick the maximum; runs are not coordinated.

---

## Reporting

A `workers:` line is prepended to the reply of `run_pytest_check` and to the
toolkit's `test` action result when:

- the effective `-n` is `auto` or `logical`, or
- `pytest_workers` is set in `config.toml`, valid or not (an unreadable or
  invalid-TOML `config.toml` counts as set).

A count of `0` is always shown as `serial`.

| Situation | Line |
|---|---|
| `auto`, Windows | `workers: 3 (auto, Windows, CPU load 71 %)` |
| `auto`, Windows, `n < 2` | `workers: serial (auto, Windows, CPU load 92 %)` |
| `auto`, Windows, sampling failed | `workers: xdist default (auto, Windows, CPU load unavailable)` |
| `auto`, other OS | `workers: xdist default (auto, not Windows)` |
| `"all"` | `workers: xdist default (all, config.toml)` |
| integer | `workers: 4 (config.toml)`, `workers: serial (config.toml)` |
| pre-set variable | `workers: 6 (PYTEST_XDIST_AUTO_NUM_WORKERS)`, `workers: serial (PYTEST_XDIST_AUTO_NUM_WORKERS)` |
| pre-set non-integer | `workers: xdist default (PYTEST_XDIST_AUTO_NUM_WORKERS="x" is not an integer)` |
| numeric `-n`, config set | `workers: 8 (-n 8 from pyproject.toml addopts; pytest_workers applies to -n auto only)` |
| `-n 0`, config set | `workers: serial (-n 0 from extra_args; pytest_workers applies to -n auto only)` |
| no `-n`, config set | `workers: no -n (pytest_workers applies to -n auto only)` |

The source of a numeric `-n` is named `pyproject.toml addopts`, `-o addopts`,
`PYTEST_ADDOPTS` or `extra_args`.

`run_pytest_check` reports a run sized to serial like a run without xdist: the
hints meant for parallel runs (the `addopts` line on a deselected run, the
"rerun with `-n 0`" tip) are not shown.

---

## Invalid values and files

- **Missing file:** silent; the value is `auto`.
- **Invalid value** (anything other than `"auto"`, `"all"` or an integer
  ≥ 0), **unreadable file** or **invalid TOML:** a warning in the server log,
  then fallback to `auto`. The problem is appended to the `workers:` line, and
  the verify item is a `warning`. Examples:
  - `workers: 6 (auto, Windows, CPU load 48 %; ignored pytest_workers = "x" in config.toml)`
  - `workers: no -n (pytest_workers applies to -n auto only; ignored config.toml: invalid TOML)`
  - `…; ignored config.toml: unreadable` (also when no home directory can be
    found)

The problem goes into the reply, not only the log, because an agent never sees
the server log.

---

## Verify

`PythonToolkit.verify()` has a `pytest_workers` item for `action` `None` and
`"test"`. It reads `config.toml` but never samples the CPU.

| Status | Message | Hint |
|---|---|---|
| `ok` | `auto (default)`, `auto (config.toml)`, `all (config.toml)`, `4 (config.toml)` | — |
| `warning` | `ignored pytest_workers = "x" in config.toml; using auto` | `Valid values: "auto", "all", or an integer >= 0 (0 = serial).` |
| `warning` | `ignored config.toml: invalid TOML; using auto` (or `unreadable`) | `Fix or remove ~/.mcp_coder/config.toml.` |

It warns rather than errors, because at run time the value falls back to
`auto` and pytest keeps working.

---

## Timeouts

On a busy Windows machine, `auto` can resolve to serial, and a serial run takes
longer. If it hits the 300 s default `timeout_seconds` of `run_pytest_check`:

- raise `timeout_seconds` for the call (or the project's `pytest-timeout` in
  [`[tool.mcp-tools-py]`](pyproject-configuration.md)),
- set `pytest_workers` to `"all"` or a fixed integer, or
- pass a numeric `-n N` in `extra_args`.

---

## Known limitations

- **pytest config outside `pyproject.toml`:** a `-n auto` in `pytest.ini`,
  `.pytest.ini`, `pytest.toml`, `.pytest.toml`, `tox.ini`, `setup.cfg`, or in a
  file passed via `-c` / `--config-file`, is not seen. Sizing doesn't apply and
  the run uses xdist's default. A caller's `-n auto` in `extra_args` is still
  sized.
- **Requested, not actual, count:** the `workers:` line shows the requested
  count when something else decides the count: a project `conftest.py`
  implementing `pytest_xdist_auto_num_workers` (overrides the variable),
  `--maxprocesses` (caps the count) or `--pdb` (forces serial).
