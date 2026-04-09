"""Print uv pip install commands for GitHub dependency overrides.

Bootstrap helper for reinstall_local.bat. Reads [tool.mcp-coder.install-from-github]
from pyproject.toml without requiring any installed packages.

Output format (one command per line):
    uv pip install "pkg1" "pkg2"
"""

import tomllib
from pathlib import Path


def main() -> None:
    """Read GitHub install config and print uv pip install commands."""
    project_dir = Path(__file__).resolve().parent.parent
    path = project_dir / "pyproject.toml"

    with open(path, "rb") as f:
        data = tomllib.load(f)

    gh = data.get("tool", {}).get("mcp-coder", {}).get("install-from-github", {})
    packages = gh.get("packages", [])

    if packages:
        quoted = " ".join(f'"{p}"' for p in packages)
        print(f"uv pip install {quoted}")


if __name__ == "__main__":
    main()
