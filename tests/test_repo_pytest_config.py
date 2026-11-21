"""Integration test for this repo's own pytest config."""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[1]
_UNREGISTERED = "unregistered_probe_marker"


@pytest.fixture(autouse=True)
def _no_outer_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep an outer traced run from leaking into the nested one."""
    monkeypatch.delenv("COVERAGE_PROCESS_CONFIG", raising=False)


def test_unregistered_marker_fails_collection(tmp_path: Path) -> None:
    """A test marked with an unregistered marker fails collection (--strict-markers)."""
    test_file = tmp_path / "test_marked.py"
    test_file.write_text(
        f"import pytest\n\n\n@pytest.mark.{_UNREGISTERED}\ndef test_marked():\n    pass\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(_REPO_ROOT / "pyproject.toml"),
            # Without it pytest walks every directory from the drive root down.
            "--confcutdir",
            str(tmp_path),
            "-n",
            "0",
            "-p",
            "no:cacheprovider",
            str(test_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert f"'{_UNREGISTERED}' not found in `markers` configuration option" in output, (
        output
    )
