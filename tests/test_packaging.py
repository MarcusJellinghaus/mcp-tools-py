"""Check that the target scripts are shipped, not merely present in the tree.

`probe.py` is data as far as the parent is concerned: it is located by path
and never imported, so a packaging change could drop it from the wheel
without any import breaking.  Only inspecting a built wheel catches that.
"""

import sys
import zipfile
from pathlib import Path

import pytest

from mcp_tools_py.utils.subprocess_runner import execute_command

_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.integration
def test_target_scripts_ship_in_the_wheel(tmp_path: Path) -> None:
    """A built wheel contains the target_scripts package and its probe."""
    pytest.importorskip("build")

    result = execute_command(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
        cwd=str(_REPO_ROOT),
        timeout_seconds=300,
    )
    assert result.return_code == 0, result.stdout + result.stderr

    wheels = sorted(tmp_path.glob("*.whl"))
    assert wheels, "build produced no wheel"
    names = zipfile.ZipFile(wheels[0]).namelist()

    assert "mcp_tools_py/utils/target_scripts/__init__.py" in names
    assert "mcp_tools_py/utils/target_scripts/probe.py" in names
