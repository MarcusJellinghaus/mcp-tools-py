# Decisions from Plan Review Discussion

| # | Topic | Decision | Rationale |
|---|-------|----------|-----------|
| 1 | structlog in `sanitize_extra_args()` | Remove - keep it a pure function | Notes are already returned in `SanitizedArgs.notes` and logged in `server.py`; logging in both places is redundant |
| 2 | Stripping bare `"tests"` from extra_args | Keep defensive stripping | Avoids potential confusion for pytest resolving relative vs absolute paths |
| 3 | Merge Step 3 into earlier step | Keep as separate Step 3 | Clean separation of concerns |
| 4 | `-n` flag deduplication | Skip - no handling needed | `-n` is not auto-added internally; no real duplication risk |
| 5 | Combined short flags (`-xvs`) | Document as known limitation | Combined flags pass through as-is; harmless in practice, keeps parser simple |
| 6 | Dead code in `_format_pytest_result_with_details` | Add brief code comment | Note branches are retained but currently inactive since `show_details` is always `True` |
