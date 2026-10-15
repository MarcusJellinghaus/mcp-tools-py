"""Directory search core: glob matching and content search over a plain Path.

Reimplements the glob/content-search shape of mcp_workspace's search_files
locally, since that original is project-tree/gitignore-shaped and not a
drop-in share for an arbitrary site-packages directory.
"""

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from pathspec import GitIgnoreSpec, RegexPattern

# Mirrors mcp_workspace.file_tools.search's truncation budget: a single
# pathological line must not crowd out the rest of the result.
_MAX_LINE_CHARS = 500


def _collect_files(root: Path) -> List[str]:
    """Walk root, collecting .py/.pyi files as sorted root-relative posix paths.

    Args:
        root: Directory to walk.

    Returns:
        Sorted root-relative paths (posix separators) to .py and .pyi files,
        excluding __pycache__ and *.dist-info directories.
    """
    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d != "__pycache__" and not d.endswith(".dist-info")
        ]
        for name in filenames:
            if name.endswith((".py", ".pyi")):
                abs_path = Path(dirpath) / name
                files.append(abs_path.relative_to(root).as_posix())
    return sorted(files)


def _match_glob(glob: str, files: List[str]) -> List[str]:
    """Match root-relative paths against a gitignore-semantics glob.

    Args:
        glob: Glob pattern, interpreted with gitignore/wildmatch semantics.
        files: Root-relative paths to filter.

    Returns:
        The subset of ``files`` matching ``glob``.

    Raises:
        ValueError: If the pattern cannot match anything by construction —
            a gitignore comment, a blank line, a negation-only pattern, or a
            pattern pathspec cannot compile (such as an unterminated ``[``).
    """
    win32 = sys.platform == "win32"
    spec = GitIgnoreSpec.from_lines([glob.lower() if win32 else glob])

    usable = any(
        isinstance(p, RegexPattern) and p.regex is not None and p.include
        for p in spec.patterns
    )
    if not usable:
        raise ValueError(
            f"Glob pattern {glob!r} matches nothing by construction "
            "(gitignore comment, blank, negation-only, or unparseable pattern)"
        )

    def _norm(p: str) -> str:
        return p.lower() if win32 else p

    return [f for f in files if spec.match_file(_norm(f))]


def _search_content(
    files: List[str],
    compiled: "re.Pattern[str]",
    root: Path,
    context_lines: int,
    max_results: int,
    max_result_lines: int,
) -> Dict[str, Any]:
    """Search file contents for regex matches.

    Returns:
        content_search result dict. Carries a ``skipped_files`` key listing
        root-relative paths that could not be read — present only when
        non-empty.
    """
    matches: List[Dict[str, Any]] = []
    total_matches = 0
    char_budget = max_result_lines * 120
    chars_used = 0
    truncated = False
    files_map: Dict[str, List[int]] = {}
    skipped: List[str] = []

    for rel_path in files:
        try:
            with open(root / rel_path, "r", encoding="utf-8") as f:
                file_lines = f.readlines()
        except UnicodeDecodeError:
            # Must precede the next handler: UnicodeDecodeError is a subclass
            # of ValueError. Binary files stay a silent skip.
            continue
        except OSError:
            skipped.append(rel_path)
            continue

        for i, line in enumerate(file_lines):
            if not compiled.search(line):
                continue

            total_matches += 1
            files_map.setdefault(rel_path, []).append(i + 1)

            if truncated:
                continue

            start = max(0, i - context_lines)
            end = min(len(file_lines), i + context_lines + 1)
            raw_lines = file_lines[start:end]
            capped = []
            for raw in raw_lines:
                stripped = raw.rstrip("\n")
                if len(stripped) > _MAX_LINE_CHARS:
                    stripped = (
                        stripped[:_MAX_LINE_CHARS]
                        + f" ... [line truncated: showing {_MAX_LINE_CHARS}"
                        f" of {len(stripped)} chars]"
                    )
                capped.append(stripped)
            context = "\n".join(capped)

            if len(matches) >= max_results or chars_used + len(context) > char_budget:
                truncated = True
                continue

            matches.append({"file": rel_path, "line": i + 1, "text": context})
            chars_used += len(context)

    result: Dict[str, Any] = {
        "mode": "content_search",
        "details": matches,
        "total_matches": total_matches,
        "truncated": truncated,
    }
    if truncated:
        result["matched_files"] = [
            {"file": f, "lines": lns} for f, lns in files_map.items()
        ]
    if skipped:
        result["skipped_files"] = skipped
    return result


def search_in_directory(
    root: Path,
    glob: Optional[str] = None,
    pattern: Optional[str] = None,
    context_lines: int = 0,
    max_results: int = 50,
    max_result_lines: int = 200,
) -> Dict[str, Any]:
    """Search .py/.pyi files under root by glob and/or regex content.

    Args:
        root: Directory to search.
        glob: Glob pattern with gitignore/wildmatch semantics. Omitting both
            glob and pattern lists everything under root.
        pattern: Python regex to match file contents. Invalid regex falls
            back to literal-text search.
        context_lines: Number of context lines around matches.
        max_results: Maximum number of results to return.
        max_result_lines: Maximum total lines in result output.

    Returns:
        Dict shaped like mcp_workspace.search_files's result, plus a
        top-level ``scope_root`` (absolute path string) present in every
        result regardless of mode.

    Raises:
        ValueError: If glob matches nothing by construction.
    """  # noqa: DOC502 - propagated from _match_glob.
    files = _collect_files(root)
    if glob is not None:
        files = _match_glob(glob, files)

    if pattern is not None:
        try:
            compiled = re.compile(pattern)
            note = None
        except re.error:
            compiled = re.compile(re.escape(pattern))
            note = (
                "Pattern treated as literal text (invalid regex). "
                "Use Python re syntax for regex search."
            )

        result = _search_content(
            files, compiled, root, context_lines, max_results, max_result_lines
        )
        if note is not None:
            result["note"] = note
    else:
        total = len(files)
        result = {
            "mode": "file_search",
            "files": files[:max_results],
            "total_files": total,
            "truncated": total > max_results,
        }

    result["scope_root"] = str(root.resolve())
    return result
