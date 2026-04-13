# Step 1: Update `read_github_deps.py` — path guard + `packages-no-deps` support

> **Context**: See [summary.md](summary.md) for overall plan. This is step 1 of 2.

## Goal

Update `tools/read_github_deps.py` to match the mcp-coder-utils version:
1. Add `path.exists()` guard — return early if `pyproject.toml` is missing
2. Add `packages-no-deps` support — emit `uv pip install --no-deps "pkg"` for those entries

## TDD: Write Tests First

### WHERE
- `tests/test_read_github_deps.py` (new file)

### WHAT — Test Functions

```python
def test_packages_generates_install_command(tmp_path, capsys):
    """Existing 'packages' key produces 'uv pip install "pkg"' lines."""

def test_packages_no_deps_generates_no_deps_command(tmp_path, capsys):
    """'packages-no-deps' key produces 'uv pip install --no-deps "pkg"' lines."""

def test_both_packages_and_no_deps(tmp_path, capsys):
    """Both keys produce correct commands (packages first, then no-deps)."""

def test_missing_pyproject_returns_silently(tmp_path, capsys):
    """When pyproject.toml doesn't exist, no output, no error."""

def test_empty_config_returns_silently(tmp_path, capsys):
    """When install-from-github section is absent, no output."""
```

### HOW — Test Strategy
- Use `tmp_path` to create temporary `pyproject.toml` files with controlled content
- Monkeypatch `Path(__file__)` resolution or pass project_dir as parameter to `main()`
- Capture stdout via `capsys`

### DATA — Test pyproject.toml Fixtures

```toml
# packages only
[tool.mcp-coder.install-from-github]
packages = ["pkg-a @ git+https://github.com/org/pkg-a.git"]

# packages-no-deps only
[tool.mcp-coder.install-from-github]
packages-no-deps = ["pkg-b @ git+https://github.com/org/pkg-b.git"]

# both
[tool.mcp-coder.install-from-github]
packages = ["pkg-a @ git+https://github.com/org/pkg-a.git"]
packages-no-deps = ["pkg-b @ git+https://github.com/org/pkg-b.git"]
```

## Implementation

### WHERE
- `tools/read_github_deps.py`

### WHAT — Updated `main()` Signature

```python
def main(project_dir: Path | None = None) -> None:
```

Adding optional `project_dir` parameter enables testability without monkeypatching.

### ALGORITHM (pseudocode)

```
if project_dir is None: project_dir = Path(__file__).resolve().parent.parent
path = project_dir / "pyproject.toml"
if not path.exists(): return
data = tomllib.load(path)
gh = data["tool"]["mcp-coder"]["install-from-github"]  # with .get() chain
for pkg in gh.get("packages", []): print(f'uv pip install "{pkg}"')
for pkg in gh.get("packages-no-deps", []): print(f'uv pip install --no-deps "{pkg}"')
```

### DATA — Output Format

```
uv pip install "pkg-a @ git+https://..." "pkg-b @ git+https://..."
uv pip install --no-deps "pkg-c @ git+https://..."
```

Note: `packages` entries are grouped into one command (existing behavior). `packages-no-deps` entries are emitted as a separate command with `--no-deps`.

## Checks
- Run pylint, pytest, mypy — all must pass
- Commit: `feat: add packages-no-deps support and path guard to read_github_deps.py (#157)`

---

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_1.md.
Implement step 1: Update tools/read_github_deps.py with TDD.
1. Create tests/test_read_github_deps.py with the specified tests
2. Update tools/read_github_deps.py: add project_dir parameter, path.exists() guard, packages-no-deps support
3. Run all checks (pylint, pytest, mypy) and fix any issues
4. Commit with message: feat: add packages-no-deps support and path guard to read_github_deps.py (#157)
```
