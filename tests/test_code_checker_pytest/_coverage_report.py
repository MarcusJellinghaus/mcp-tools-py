"""Builders for coverage JSON reports, shared by the digest tests."""

from typing import Any

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
