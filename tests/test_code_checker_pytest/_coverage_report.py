"""Builders for coverage JSON reports and saved data, shared by the coverage tests."""

from pathlib import Path
from typing import Any

from mcp_tools_py.code_checker_pytest.coverage_store import METADATA_FILE, STORE_DIR

_SELECTION = "selection: full suite (no markers, -k or path arguments)"


def _file(
    stmts: int,
    missing: list[int],
    functions: dict[str, list[int]] | None = None,
) -> dict[str, Any]:
    """One file entry of the coverage JSON."""
    covered = stmts - len(missing)
    entry: dict[str, Any] = {
        "summary": {
            "num_statements": stmts,
            "covered_lines": covered,
            "missing_lines": len(missing),
            "percent_covered": 100.0 * covered / stmts if stmts else 100.0,
        },
        "missing_lines": missing,
    }
    if functions is not None:
        entry["functions"] = {
            name: {"missing_lines": lines} for name, lines in functions.items()
        }
    return entry


def _report(files: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """A coverage JSON with totals summed from files."""
    stmts = sum(f["summary"]["num_statements"] for f in files.values())
    missed = sum(f["summary"]["missing_lines"] for f in files.values())
    return {
        "totals": {
            "num_statements": stmts,
            "missing_lines": missed,
            "covered_lines": stmts - missed,
            "percent_covered": 100.0 * (stmts - missed) / stmts if stmts else 100.0,
        },
        "files": files,
    }


def _run(**changes: Any) -> dict[str, Any]:
    """One run entry, as the callers build it."""
    return {
        "selection": _SELECTION,
        "data_file": None,
        "failed_collectors": 0,
        "failed_tests": 0,
        "generic_warning": False,
        **changes,
    }


def _saved(**changes: Any) -> dict[str, Any]:
    """The dict a caller passes to write_saved."""
    return {
        "report": {"files": {"src/a.py": {"summary": {"num_statements": 1}}}},
        "hashes": {"src/a.py": "abc"},
        "roots": ["src", "tests"],
        "sources": ["src"],
        "fail_under": 0.0,
        "runs": [_run()],
        **changes,
    }


def _write_source(project: Path, relative: str, content: str = "x = 1\n") -> Path:
    """Write one file below the project, with its parent directories."""
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_metadata(project: Path, content: bytes) -> None:
    """Put raw content where load_saved reads the metadata."""
    store = project / STORE_DIR
    store.mkdir(parents=True)
    (store / METADATA_FILE).write_bytes(content)
