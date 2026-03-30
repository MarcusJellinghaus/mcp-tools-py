# Step 1: Shared utility `utils/project_config.py` + tests

> **Context**: See [summary.md](summary.md) for full issue context.

## Goal

Create a shared utility that reads target directories from `pyproject.toml`. This will be used by `FormatterTools` (this PR) and later by checker tools (#136).

## WHERE

| Action | File |
|--------|------|
| Create | `src/mcp_tools_py/utils/project_config.py` |
| Create | `tests/test_project_config.py` |
| Modify | `src/mcp_tools_py/utils/__init__.py` |

## WHAT — Function signatures

```python
# src/mcp_tools_py/utils/project_config.py

def get_target_directories(project_dir: str) -> tuple[list[str], list[str]]:
    """Read source and test directories from pyproject.toml.

    Args:
        project_dir: Path to project root containing pyproject.toml.

    Returns:
        Tuple of (source_dirs, test_dirs) with warnings embedded.
        Raises ValueError if no directories exist on disk.
    """
```

Return type: `tuple[list[str], list[str]]` — a tuple of `(warnings, directories)` where directories = source_dirs + test_dirs combined, and warnings is a list of warning strings.

Actually, simpler: return a `TargetDirs` dataclass:

```python
@dataclasses.dataclass
class TargetDirs:
    directories: list[str]   # Combined source + test dirs that exist on disk
    warnings: list[str]      # Fallback warnings (empty if pyproject.toml had values)
```

## HOW — Integration

- Uses `tomllib` (stdlib Python 3.11+) to parse `pyproject.toml`
- No external dependencies needed
- Export both `get_target_directories` and `TargetDirs` from `utils/__init__.py`

## ALGORITHM (pseudocode)

```
1. Read & parse {project_dir}/pyproject.toml (if missing, use fallbacks for both)
2. src_dirs = toml[tool][setuptools][packages][find][where] or fallback ["src"] + warn
3. test_dirs = toml[tool][pytest][ini_options][testpaths] or fallback ["tests"] + warn
4. combined = src_dirs + test_dirs
5. Filter to dirs that exist on disk (os.path.isdir(project_dir / d))
6. If none exist → raise ValueError("No target directories found: {combined}")
7. Return TargetDirs(directories=existing, warnings=warnings)
```

## DATA — Return values

```python
# Success case (pyproject.toml has both sections):
TargetDirs(directories=["src", "tests"], warnings=[])

# Fallback case (missing sections):
TargetDirs(
    directories=["src", "tests"],
    warnings=[
        "Warning: [tool.setuptools.packages.find] where not found in pyproject.toml, defaulting to ['src']",
        "Warning: [tool.pytest.ini_options] testpaths not found in pyproject.toml, defaulting to ['tests']",
    ],
)

# Error case (no dirs exist):
ValueError("No target directories found: ['src', 'tests']")
```

## TESTS — `tests/test_project_config.py`

1. **test_reads_source_dirs_from_pyproject** — mock toml with `[tool.setuptools.packages.find] where = ["src"]`, verify returned
2. **test_reads_test_dirs_from_pyproject** — mock toml with `[tool.pytest.ini_options] testpaths = ["tests"]`, verify returned
3. **test_fallback_source_dirs_with_warning** — missing setuptools section → defaults to `["src"]` + warning string
4. **test_fallback_test_dirs_with_warning** — missing pytest section → defaults to `["tests"]` + warning string
5. **test_skips_nonexistent_dirs_silently** — dir doesn't exist on disk → filtered out
6. **test_raises_when_no_dirs_exist** — all dirs missing on disk → `ValueError`
7. **test_missing_pyproject_uses_all_fallbacks** — no pyproject.toml file → both fallbacks + both warnings

## LLM Prompt

```
Implement Step 1 of issue #10 (see pr_info/steps/summary.md and pr_info/steps/step_1.md).

Create `src/mcp_tools_py/utils/project_config.py` with a `get_target_directories()` function
and `TargetDirs` dataclass per the spec. Write tests first in `tests/test_project_config.py`,
then implement the function. Update `src/mcp_tools_py/utils/__init__.py` to export the new symbols.

Follow existing code patterns (see utils/file_utils.py for style reference).
Run pylint, mypy, and pytest checks after implementation. Commit when all pass.
```
