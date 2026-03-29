# Issue #131: Align logging to stdlib-only pattern

## Goal

Remove the dual-logger anti-pattern where modules create both `logger` (stdlib) and `structured_logger` (structlog), consolidating to stdlib-only logging at the module level. Structlog remains in `log_utils.py` infrastructure only.

## Architectural / Design Changes

### Before
```
Every module:
  import logging
  import structlog
  logger = logging.getLogger(__name__)
  structured_logger = structlog.get_logger(__name__)
  
  # Ad-hoc dual logging:
  logger.info("Starting check on: %s", path)
  structured_logger.info("Starting check", project_dir=str(path))
```

### After
```
Every module (except log_utils.py):
  import logging
  logger = logging.getLogger(__name__)
  
  # Single consolidated call with extra fields:
  logger.info("Starting check", extra={"project_dir": str(path)})

log_utils.py (only place structlog lives):
  - Structlog configured internally for JSON file pipeline
  - Public API unchanged: setup_logging(), log_function_call
```

### Key Design Decisions

1. **stdlib `extra={}` replaces structlog kwargs** — The `extra` dict on stdlib log calls carries structured fields. When JSON file logging is configured, structlog's `ProcessorFormatter` picks these up automatically. No information is lost.

2. **No new features in log_utils.py yet** — The issue requires a 1:1 mirror of p_coder's `log_utils.py`, but that reference project is not available. Phase B (log_utils rewrite + new test files) is deferred until p_coder access is provided. The module cleanup in Phase A is fully independent.

3. **Single responsibility** — Each module only does `logging.getLogger(__name__)`. Structured logging configuration is solely `log_utils.py`'s concern.

4. **Lazy formatting preserved** — All log calls use `%s` formatting, not f-strings, per the issue requirements.

## Scope

### Phase A: Module cleanup (this PR)

**Files modified (10 — remove structlog + consolidate log calls):**
- `src/mcp_tools_py/main.py`
- `src/mcp_tools_py/server.py`
- `src/mcp_tools_py/checker_tools.py`
- `src/mcp_tools_py/utils/subprocess_runner.py`
- `src/mcp_tools_py/code_checker_pytest/runners.py`
- `src/mcp_tools_py/code_checker_pylint/parsers.py`
- `src/mcp_tools_py/code_checker_pylint/runners.py`
- `src/mcp_tools_py/code_checker_pylint/reporting.py`
- `src/mcp_tools_py/code_checker_mypy/parsers.py`
- `src/mcp_tools_py/code_checker_mypy/runners.py`

**Files modified (2 — dead import removal only):**
- `src/mcp_tools_py/code_checker_pytest/reporting.py`
- `src/mcp_tools_py/code_checker_mypy/reporting.py`

**Files not affected (already stdlib-only):**
- `refactoring/rope_tools.py`, `inspect_library.py`, `utility_tools.py`, all model files, all utils files

### Phase B: log_utils.py rewrite (deferred — needs p_coder reference)

**Blocked files:**
- `src/mcp_tools_py/log_utils.py` — full rewrite to mirror p_coder
- `tests/test_log_utils.py` — delete (moves to `tests/utils/`)
- `tests/utils/__init__.py` — new
- `tests/utils/test_log_utils.py` — new (mirror p_coder)
- `tests/utils/test_log_utils_redaction.py` — new (mirror p_coder)

## Constraints

- `structlog` stays in `pyproject.toml` — used internally by `log_utils.py`
- No module outside `log_utils.py` may import `structlog` after this PR
- Existing tests must continue to pass (the public API doesn't change)
- Architecture boundaries (`tach.toml`, `.importlinter`) are unaffected
