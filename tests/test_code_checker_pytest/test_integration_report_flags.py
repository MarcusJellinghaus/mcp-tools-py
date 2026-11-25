"""End-to-end tests of the report flags (-r, --durations, -s, --snapshot-update)."""

from pathlib import Path

import pytest

from mcp_tools_py.code_checker_pytest.report_extras import SNAPSHOT_NOTE
from tests.test_code_checker_pytest.test_integration_marker_hint import _tool

pytest.importorskip("xdist")

_CONFTEST = (
    "def pytest_addoption(parser):\n"
    '    parser.addoption("--snapshot-update", action="store_true")\n'
)
_MODULE_SKIP = (
    "import pytest\n\n"
    'pytest.skip("module gone", allow_module_level=True)\n\n\n'
    "def test_never():\n    pass\n"
)
_MARKED = (
    "import pytest\n\n"
    'pytestmark = pytest.mark.skip("r")\n\n\n'
    "def test_one():\n    pass\n\n\n"
    "def test_two():\n    pass\n"
)
_MAIN = """\
import logging
import time
import warnings

import pytest


@pytest.mark.skip(reason="decorated")
def test_decorated_one():
    pass


@pytest.mark.skip(reason="decorated")
def test_decorated_two():
    pass


@pytest.mark.xfail(reason="expected")
def test_xfail():
    assert False


@pytest.mark.parametrize("index", range(30))
def test_warns(index):
    warnings.warn("old", DeprecationWarning)


def test_logs():
    print("PRINT_PROBE")
    logging.getLogger("probe").warning("LOG_PROBE")


@pytest.fixture
def broken():
    yield
    raise RuntimeError("TEARDOWN_BOOM")


def test_teardown_fails(broken):
    pass


@pytest.fixture
def sleepy():
    time.sleep(0.05)
    yield
    time.sleep(0.05)


def test_slow(sleepy):
    time.sleep(0.05)
"""
_EMPTY_TABLE = "[tool.pytest.ini_options]\n"


def _write(project: Path, files: dict[str, str]) -> Path:
    """Write pyproject.toml, a root conftest and the given test modules.

    Returns:
        The project directory.
    """
    (project / "pyproject.toml").write_text(_EMPTY_TABLE, encoding="utf-8")
    (project / "conftest.py").write_text(_CONFTEST, encoding="utf-8")
    (project / "tests").mkdir()
    for name, text in files.items():
        (project / "tests" / name).write_text(text, encoding="utf-8")
    return project


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A project with skips, warnings, logs, a teardown error and a slow test."""
    return _write(
        tmp_path_factory.mktemp("report_flags"),
        {
            "test_module_skip.py": _MODULE_SKIP,
            "test_marked.py": _MARKED,
            "test_main.py": _MAIN,
        },
    )


@pytest.mark.integration
def test_ra_durations_and_s_show_every_section(project: Path) -> None:
    reply = _tool(project)(extra_args=["-n", "0", "-svra", "--durations=3"])

    assert "⏭️ Skipped: 5" in reply, reply
    assert "SKIPPED [1] tests/test_module_skip.py:3: module gone" in reply, reply
    assert "SKIPPED [2] tests/test_marked.py: r" in reply, reply
    decorated = [
        line
        for line in reply.splitlines()
        if line.startswith("SKIPPED [1] tests/test_main.py:")
    ]
    assert len(decorated) == 2, reply
    assert all(line.endswith(": decorated") for line in decorated), reply
    assert "expected" not in reply, reply
    assert "DeprecationWarning: old — 30×" in reply, reply
    assert "WARNING  probe:test_main.py:" in reply, reply
    assert "LOG_PROBE" in reply, reply
    assert "PRINT_PROBE" in reply, reply

    lines = reply.splitlines()
    start = lines.index("Slowest 3 durations:")
    rows = lines[start + 1 : start + 4]
    assert sorted(row.split()[1] for row in rows) == ["call", "setup", "teardown"]
    assert all(row.endswith("tests/test_main.py::test_slow") for row in rows), reply
    assert "hidden" not in reply, reply

    assert "TEARDOWN_BOOM" in reply, reply


@pytest.mark.integration
def test_xdist_shows_teardown_error_without_worker_header(project: Path) -> None:
    reply = _tool(project)(extra_args=["-n", "2"])

    assert "TEARDOWN_BOOM" in reply, reply
    assert "[gw" not in reply, reply
    assert "Test Teardown Longrepr:\n```\n\n" not in reply, reply


@pytest.mark.integration
def test_all_module_skipped_run_adds_count_and_reasons(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    skipped_only = _write(
        tmp_path_factory.mktemp("all_skipped"),
        {"test_a.py": _MODULE_SKIP, "test_b.py": _MODULE_SKIP},
    )

    reply = _tool(skipped_only)(extra_args=["-n", "0"])

    assert "No Tests Found" in reply, reply
    assert "⏭️ Skipped: 2" in reply, reply
    assert "SKIPPED [1] tests/test_a.py:3: module gone" in reply, reply
    assert "SKIPPED [1] tests/test_b.py:3: module gone" in reply, reply


@pytest.mark.integration
def test_svrw_with_snapshot_update(project: Path) -> None:
    reply = _tool(project)(extra_args=["--snapshot-update", "-n", "0", "-svrw"])

    assert SNAPSHOT_NOTE in reply, reply
    assert "DeprecationWarning: old — 30×" in reply, reply
    assert "LOG_PROBE" in reply, reply
    # -s is the tool's flag, not pytest's: capture stays on, the JSON has stdout.
    assert "PRINT_PROBE" in reply, reply
    assert "Skip reasons:" not in reply, reply
    assert "SKIPPED [" not in reply, reply
