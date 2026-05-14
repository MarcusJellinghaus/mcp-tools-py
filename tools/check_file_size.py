"""Fail if any git-tracked text file exceeds a line-count threshold.

Replacement for ``mcp-coder check file-size`` for use in CI. Exists only
because the upstream invocation hits the irreducible mcp-coder ↔
mcp-tools-py URL cycle (chore #107 Section 3). Behaviour matches the
upstream check: list git-tracked files, count lines (skipping binary),
ignore allowlisted paths, fail on any non-allowlisted file > max-lines.

Usage:
    python tools/check_file_size.py --max-lines 750 --allowlist-file .large-files-allowlist
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def load_allowlist(path: Path) -> set[str]:
    """Read allowlist file; ignore blank lines and ``#`` comments.

    Returns:
        Allowlisted paths normalised to OS-native separators.
    """
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.add(stripped.replace("/", os.sep).replace("\\", os.sep))
    return out


def list_tracked_files() -> list[str]:
    """Return git-tracked file paths relative to the repo root.

    Returns:
        Paths from ``git ls-files`` (always forward-slash from git).
    """
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def count_lines(file_path: Path) -> int:
    """Count lines in a file as UTF-8 text.

    Returns:
        Line count, or ``-1`` if the file isn't valid UTF-8 (binary).
    """
    try:
        with file_path.open(encoding="utf-8") as f:
            return sum(1 for _ in f)
    except (UnicodeDecodeError, OSError):
        return -1


def main() -> int:
    """CLI entry point.

    Returns:
        ``0`` if all files pass, ``1`` if any non-allowlisted file is too large.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-lines", type=int, required=True)
    parser.add_argument("--allowlist-file", type=Path, required=True)
    args = parser.parse_args()

    allowlist = load_allowlist(args.allowlist_file)
    tracked = list_tracked_files()

    violations: list[tuple[str, int]] = []
    checked = 0
    allowlisted_hits = 0
    for rel in tracked:
        normalised = rel.replace("/", os.sep).replace("\\", os.sep)
        lines = count_lines(Path(rel))
        if lines < 0:
            continue
        checked += 1
        if lines > args.max_lines:
            if normalised in allowlist:
                allowlisted_hits += 1
            else:
                violations.append((rel, lines))

    if violations:
        print(
            f"File size check failed: {len(violations)} file(s) exceed "
            f"{args.max_lines} lines"
        )
        print()
        print("Violations:")
        for path, lines in sorted(violations, key=lambda x: -x[1]):
            print(f"  - {path}: {lines} lines")
        return 1

    print(
        f"File size check passed: {checked} files checked, "
        f"{allowlisted_hits} allowlisted"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
