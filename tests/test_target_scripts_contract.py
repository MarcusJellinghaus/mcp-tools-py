"""Prove the target-scripts contract actually bites.

The obvious spelling of this contract — naming an ancestor of the source
module as forbidden — is a silent no-op in import-linter: it neither errors
nor reports, so the contract passes while enforcing nothing.  Its presence in
`.importlinter` is therefore not evidence.  These tests build a miniature
package with the same shape and check that the contract breaks when a target
script imports a project module.
"""

import configparser
from pathlib import Path
from typing import Optional

import pytest

from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.subprocess_runner import execute_command

_CONTRACT_SECTION = "importlinter:contract:target-scripts-stdlib-only"
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _real_contract() -> configparser.SectionProxy:
    """Read the shipped contract, so the fixture cannot drift from it.

    Returns:
        The `.importlinter` section defining the target-scripts contract.
    """
    parser = configparser.ConfigParser()
    parser.read(_REPO_ROOT / ".importlinter", encoding="utf-8")
    return parser[_CONTRACT_SECTION]


def _lint_imports() -> Optional[Path]:
    """Locate the lint-imports console script.

    Returns:
        Path to the script, or None when it is not installed.
    """
    return PythonEnvironment.resolve().binary("lint-imports")


def _build_fixture(tmp_path: Path, probe_source: str) -> str:
    """Write a miniature package mirroring the real layout.

    Args:
        tmp_path: Directory to build in; becomes the working directory.
        probe_source: Contents of the fake `probe.py`.

    Returns:
        The contract name, as it appears in the lint-imports report.
    """
    contract = _real_contract()
    forbidden = contract["forbidden_modules"].strip().replace("mcp_tools_py", "fakepkg")
    source_modules = (
        contract["source_modules"].strip().replace("mcp_tools_py", "fakepkg")
    )

    package = tmp_path / "fakepkg"
    scripts = package / "utils" / "target_scripts"
    scripts.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "utils" / "__init__.py").write_text("", encoding="utf-8")
    (package / "utils" / "helper.py").write_text("thing = 1\n", encoding="utf-8")
    (scripts / "__init__.py").write_text("", encoding="utf-8")
    (scripts / "probe.py").write_text(probe_source, encoding="utf-8")

    (tmp_path / ".importlinter").write_text(
        "[importlinter]\n"
        "root_package = fakepkg\n"
        "\n"
        f"[{_CONTRACT_SECTION}]\n"
        f"name = {contract['name']}\n"
        f"type = {contract['type']}\n"
        f"source_modules =\n    {source_modules}\n"
        f"forbidden_modules =\n"
        + "".join(f"    {line.strip()}\n" for line in forbidden.splitlines()),
        encoding="utf-8",
    )
    return contract["name"]


def _run_lint_imports(tmp_path: Path) -> tuple[int, str]:
    """Run lint-imports against the fixture.

    Args:
        tmp_path: Directory holding the fixture and its `.importlinter`.

    Returns:
        The exit code and the combined report text.
    """
    script = _lint_imports()
    assert script is not None
    result = execute_command(
        [str(script), "--config", str(tmp_path / ".importlinter"), "--no-cache"],
        cwd=str(tmp_path),
        timeout_seconds=120,
    )
    return result.return_code, result.stdout + result.stderr


@pytest.mark.integration
def test_stdlib_only_probe_keeps_the_contract(tmp_path: Path) -> None:
    """A probe that imports nothing from the project passes."""
    if _lint_imports() is None:
        pytest.skip("lint-imports is not installed next to this interpreter")

    name = _build_fixture(tmp_path, "import json\n")

    return_code, report = _run_lint_imports(tmp_path)

    assert return_code == 0, report
    assert name in report
    assert "KEPT" in report


@pytest.mark.integration
def test_project_import_breaks_the_contract(tmp_path: Path) -> None:
    """A probe that imports a project module breaks the contract."""
    if _lint_imports() is None:
        pytest.skip("lint-imports is not installed next to this interpreter")

    name = _build_fixture(tmp_path, "from fakepkg.utils.helper import thing\n")

    return_code, report = _run_lint_imports(tmp_path)

    assert return_code != 0, report
    assert name in report
    assert "BROKEN" in report
