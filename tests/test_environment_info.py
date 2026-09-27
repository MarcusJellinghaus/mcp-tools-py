"""Tests for the one-shot environment probe and its parsed result."""

import json
import logging
import platform
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.utils.environment_info import (
    PROBED_MODULES,
    get_environment_info,
    locate_packages,
    probe_script_path,
)
from mcp_tools_py.utils.subprocess_runner import execute_command
from tests.conftest import make_command_result
from tests.test_tool_availability._helpers import _create_server, _dummy_python

_BLOB = json.dumps(
    {
        "version": "3.11.9",
        "sys_path": ["/first", "/second"],
        "distributions": {"pylint": "3.2.0"},
        "importable": {"pylint": True, "pytest": True, "mypy": False},
    }
)


class TestGetEnvironmentInfo:
    """Test parsing, caching and the fail-open failure shape."""

    def test_parses_well_formed_blob(self) -> None:
        """A well-formed probe blob becomes an EnvironmentInfo."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout=_BLOB)

            info = get_environment_info("/some/python")

            assert info.version == "3.11.9"
            assert info.sys_path == ("/first", "/second")
            assert info.distributions == {"pylint": "3.2.0"}
            assert info.importable["pytest"] is True
            assert info.importable["mypy"] is False
            assert info.error is None

    def test_success_is_cached(self) -> None:
        """A successful probe runs once per interpreter path."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout=_BLOB)

            first = get_environment_info("/some/python")
            second = get_environment_info("/some/python")

            assert first is second
            mock_exec.assert_called_once()

    def test_failure_is_cached_and_fails_open(self) -> None:
        """A non-zero exit is remembered, and reports every module available."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=1, stderr="no such file"
            )

            first = get_environment_info("/some/python")
            second = get_environment_info("/some/python")

            mock_exec.assert_called_once()
            assert first.error is not None
            assert second.error is not None
            assert "no such file" in first.error
            assert all(first.importable[name] for name in PROBED_MODULES)

    def test_timeout_fails_open(self) -> None:
        """A probe that times out sets error rather than raising."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=-1,
                timed_out=True,
                execution_error="Process timed out after 30 seconds",
            )

            info = get_environment_info("/some/python")

            assert info.error is not None
            assert "timed out" in info.error
            assert all(info.importable[name] for name in PROBED_MODULES)

    def test_unparsable_stdout_fails_open(self) -> None:
        """Output that is not the expected JSON sets error rather than raising."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout="not json at all")

            info = get_environment_info("/some/python")

            assert info.error is not None
            assert "unparsable" in info.error
            assert all(info.importable[name] for name in PROBED_MODULES)

    def test_not_probed_until_first_use(self, tmp_path: Path) -> None:
        """Constructing a server runs no probe."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )

            mock_exec.assert_not_called()


class TestToolVersionLogging:
    """The startup diagnostic naming the tool distributions the probe found."""

    _LOGGER = "mcp_tools_py.utils.environment_info"

    @staticmethod
    def _version_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
        """Collect the records reporting tool versions.

        Args:
            caplog: pytest's log capture for the finished call.

        Returns:
            The messages of every record naming tool versions.
        """
        return [
            record.getMessage()
            for record in caplog.records
            if record.getMessage().startswith("tool versions in ")
        ]

    def test_success_logs_every_found_distribution(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A successful probe logs one record naming each `python -m` tool found.

        The console-script distributions are left out: they come from the tool
        env, which this probe never describes.
        """
        blob = json.dumps(
            {
                "version": "3.11.9",
                "sys_path": [],
                "distributions": {"pylint": "3.2.0", "import-linter": "2.0"},
                "importable": {},
            }
        )
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout=blob)

            with caplog.at_level(logging.INFO, logger=self._LOGGER):
                get_environment_info("/some/python")

        messages = self._version_messages(caplog)
        assert len(messages) == 1
        assert "/some/python" in messages[0]
        assert "pylint 3.2.0" in messages[0]
        assert "import-linter" not in messages[0]

    def test_failure_logs_no_versions(self, caplog: pytest.LogCaptureFixture) -> None:
        """A failed probe has no versions to report, so it logs none."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=1, stderr="no such file"
            )

            with caplog.at_level(logging.INFO, logger=self._LOGGER):
                get_environment_info("/some/python")

        assert self._version_messages(caplog) == []


def _locate_blob(packages: dict[str, list[Path]], site_dirs: list[str]) -> str:
    """Build the JSON a `probe.py locate` run writes to stdout."""
    return json.dumps(
        {
            "packages": {
                name: [str(d) for d in dirs] for name, dirs in packages.items()
            },
            "site_dirs": site_dirs,
        }
    )


def _other_case(directory: Path) -> str:
    """Spell `directory` with the other drive-letter case, where there is one."""
    spelled = str(directory)
    if spelled[1:2] == ":":
        return spelled[0].swapcase() + spelled[1:]
    return spelled


class TestLocatePackages:
    """Test asking an interpreter where packages live, and the site-dir split."""

    def test_source_directory_is_usable(self, tmp_path: Path) -> None:
        """A directory under no site directory is one to prepend."""
        source = tmp_path / "repo" / "src"
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout=_locate_blob(
                    {"pkg": [source]}, [str(tmp_path / "venv" / "site-packages")]
                )
            )

            assert locate_packages("/some/python", ["pkg"]) == ([str(source)], {})

    def test_site_directory_itself_is_skipped(self, tmp_path: Path) -> None:
        """A located directory that is a site directory may not be prepended."""
        site = tmp_path / "venv" / "site-packages"
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout=_locate_blob({"pkg": [site]}, [str(site)])
            )

            assert locate_packages("/some/python", ["pkg"]) == (
                [],
                {"pkg": [str(site)]},
            )

    def test_directory_inside_site_directory_is_skipped(self, tmp_path: Path) -> None:
        """A subdirectory of a site directory is skipped, whatever its spelling."""
        site = tmp_path / "venv" / "site-packages"
        inside = site / "namespace"
        inside.mkdir(parents=True)
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout=_locate_blob({"pkg": [inside]}, [_other_case(site)])
            )

            assert locate_packages("/some/python", ["pkg"]) == (
                [],
                {"pkg": [str(inside)]},
            )

    def test_each_directory_lands_on_its_own_side(self, tmp_path: Path) -> None:
        """Source and site directories separate, and the skip keeps its name.

        Only `b` resolved into a site directory, so only `b` may be named as
        unbridged — `a` and `c` are handed over on PYTHONPATH.
        """
        first = tmp_path / "repo" / "src"
        site = tmp_path / "venv" / "site-packages"
        second = tmp_path / "other" / "src"
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout=_locate_blob(
                    {"a": [first], "b": [site], "c": [second]}, [str(site)]
                )
            )

            assert locate_packages("/some/python", ["a", "b", "c"]) == (
                [str(first), str(second)],
                {"b": [str(site)]},
            )

    def test_usable_directories_follow_request_order_without_repeats(
        self, tmp_path: Path
    ) -> None:
        """Two packages in one source tree contribute that tree once."""
        source = tmp_path / "repo" / "src"
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout=_locate_blob({"a": [source], "b": [source]}, [])
            )

            assert locate_packages("/some/python", ["a", "b"]) == ([str(source)], {})

    def test_unresolved_name_contributes_nothing(self, tmp_path: Path) -> None:
        """A name the probe left out is neither usable nor reported as skipped."""
        source = tmp_path / "repo" / "src"
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout=_locate_blob({"a": [source]}, [])
            )

            assert locate_packages("/some/python", ["a", "b"]) == ([str(source)], {})

    def test_timeout_reports_the_interpreter(self) -> None:
        """A probe that times out yields a reason naming the interpreter."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=-1,
                timed_out=True,
                execution_error="Process timed out after 30 seconds",
            )

            reason = locate_packages("/some/python", ["pkg"])

            assert isinstance(reason, str)
            assert "timed out" in reason
            assert "/some/python" in reason

    def test_failed_exit_reports_stderr(self) -> None:
        """A non-zero exit yields a reason quoting the child's stderr."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(return_code=1, stderr="boom")

            reason = locate_packages("/some/python", ["pkg"])

            assert isinstance(reason, str)
            assert "boom" in reason

    @pytest.mark.parametrize(
        "stdout",
        [
            "not json",
            '["/some/dir"]',
            '{"directories": ["/some/dir"], "site_dirs": []}',
            '{"packages": {"pkg": "/some/dir"}, "site_dirs": []}',
            '{"packages": {"pkg": [1]}, "site_dirs": []}',
        ],
    )
    def test_unexpected_stdout_is_unparsable(self, stdout: str) -> None:
        """Anything but a name-to-directories object is reported as unparsable."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout=stdout)

            reason = locate_packages("/some/python", ["pkg"])

            assert isinstance(reason, str)
            assert "unparsable" in reason

    def test_no_names_runs_no_subprocess(self) -> None:
        """Nothing to locate is answered without a probe."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            assert locate_packages("/some/python", []) == ([], {})

            mock_exec.assert_not_called()

    def test_directory_under_the_environment_root_is_usable(self) -> None:
        """A source tree directly under `sys.prefix` is not a site directory.

        `site.getsitepackages()` names `sys.prefix` itself on Windows, so a venv
        created at the project root would otherwise make every source tree
        under it read as a `site-packages` and suppress the bridge.  The real
        probe answers here, so the test fails if the bare root comes back.
        """
        probed = execute_command(
            [sys.executable, str(probe_script_path()), "locate", "mcp_tools_py"],
            timeout_seconds=60,
        )
        assert probed.return_code == 0, probed.stderr
        site_dirs = json.loads(probed.stdout)["site_dirs"]
        assert site_dirs
        assert not any(Path(d) == Path(sys.prefix) for d in site_dirs), site_dirs

        under_root = str(Path(sys.prefix) / "src")
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout=json.dumps(
                    {"packages": {"pkg": [under_root]}, "site_dirs": site_dirs}
                )
            )

            assert locate_packages(sys.executable, ["pkg"]) == ([under_root], {})

    def test_answer_is_not_cached(self, tmp_path: Path) -> None:
        """Each call probes again: the answer can change while the server runs."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout=_locate_blob({"pkg": [tmp_path / "src"]}, [])
            )

            locate_packages("/some/python", ["pkg"])
            locate_packages("/some/python", ["pkg"])

            assert mock_exec.call_count == 2


class TestProbeScript:
    """Test the script itself, run under the current interpreter."""

    def test_probe_script_path_exists(self) -> None:
        """The parent's path arithmetic points at a real file."""
        assert probe_script_path().is_file()

    def test_real_child_reports_importability(self) -> None:
        """The script answers about this interpreter, for real."""
        result = execute_command(
            [
                sys.executable,
                str(probe_script_path()),
                "info",
                "json",
                "pytest",
                "nosuchmodule_xyz",
            ],
            timeout_seconds=60,
        )

        assert result.return_code == 0, result.stderr
        blob = json.loads(result.stdout)
        assert blob["importable"] == {
            "json": True,
            "pytest": True,
            "nosuchmodule_xyz": False,
        }
        assert blob["version"] == platform.python_version()

    def test_real_child_locates_an_installed_package(self) -> None:
        """The script finds this interpreter's mcp_tools_py, and omits the rest.

        Whether that directory is a site-packages depends on how mcp_tools_py is
        installed here, so the assertion is on the located directories as a
        whole, before any split.  It is not compared against this process's
        ``mcp_tools_py.__file__`` either: pytest's ``pythonpath = ["src"]``
        imports the source tree here, while the child — which gets no such
        entry — finds whichever copy is installed.  What must hold of the
        answer in both cases is that the package really sits inside it.
        """
        result = execute_command(
            [
                sys.executable,
                str(probe_script_path()),
                "locate",
                "mcp_tools_py",
                "nosuchpkg_xyz",
            ],
            timeout_seconds=60,
        )

        assert result.return_code == 0, result.stderr
        blob = json.loads(result.stdout)
        assert blob["site_dirs"]
        assert list(blob["packages"]) == ["mcp_tools_py"]
        directories = blob["packages"]["mcp_tools_py"]
        assert len(directories) == 1
        found = Path(directories[0]).resolve()
        assert (found / "mcp_tools_py" / "__init__.py").is_file()
