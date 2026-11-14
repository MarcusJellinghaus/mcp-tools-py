"""Tests for the one-shot environment probe and its parsed result."""

import json
import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.inspect_library import _get_library_source
from mcp_tools_py.utils.environment_info import (
    PROBE_TIMEOUT_SECONDS,
    PROBED_MODULES,
    TOOL_DISTRIBUTIONS,
    TOOL_MODULES,
    EnvironmentInfo,
    ScopeResolution,
    get_environment_info,
    locate_packages,
    probe_script_path,
    resolve_scope,
    run_probe,
)
from mcp_tools_py.utils.subprocess_runner import CommandResult, execute_command
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


class TestToolTables:
    """Test the derived module and distribution tables."""

    def test_deptry_is_a_module_tool(self) -> None:
        """deptry runs as `python -m deptry`, so the probe asks about it."""
        assert TOOL_MODULES["deptry"] == "deptry"
        assert "deptry" in PROBED_MODULES
        assert "deptry" in TOOL_DISTRIBUTIONS


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

            assert locate_packages("/some/python", ["pkg"]) == ([str(source)], {}, [])

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
                [],
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
                [],
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
                [],
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

            assert locate_packages("/some/python", ["a", "b"]) == (
                [str(source)],
                {},
                [],
            )

    def test_unresolved_name_is_reported_alongside_a_resolved_one(
        self, tmp_path: Path
    ) -> None:
        """A name the probe left out is named, although `a` did resolve.

        The caller must be able to say lint-imports will build `b`'s graph
        from whatever copy sits next to the script.
        """
        source = tmp_path / "repo" / "src"
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout=_locate_blob({"a": [source]}, [])
            )

            assert locate_packages("/some/python", ["a", "b"]) == (
                [str(source)],
                {},
                ["b"],
            )

    def test_unresolved_name_is_reported_alongside_a_skipped_one(
        self, tmp_path: Path
    ) -> None:
        """A site-packages hit for `a` does not hide that `b` resolved nowhere."""
        site = tmp_path / "venv" / "site-packages"
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout=_locate_blob({"a": [site]}, [str(site)])
            )

            assert locate_packages("/some/python", ["a", "b"]) == (
                [],
                {"a": [str(site)]},
                ["b"],
            )

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
        """A non-zero exit yields a reason quoting the child's stderr.

        The reason leaves the requested names out: the caller has them, and
        repeating them here made its own message say them twice.
        """
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(return_code=1, stderr="boom")

            reason = locate_packages("/some/python", ["pkg"])

            assert isinstance(reason, str)
            assert reason == "probe of /some/python failed: boom"
            assert "could not locate" not in reason

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
            assert locate_packages("/some/python", []) == ([], {}, [])

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

            assert locate_packages(sys.executable, ["pkg"]) == ([under_root], {}, [])

    def test_answer_is_not_cached(self, tmp_path: Path) -> None:
        """Each call probes again: the answer can change while the server runs."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout=_locate_blob({"pkg": [tmp_path / "src"]}, [])
            )

            locate_packages("/some/python", ["pkg"])
            locate_packages("/some/python", ["pkg"])

            assert mock_exec.call_count == 2


class TestResolveScope:
    """Test turning a scope name into the one directory it names."""

    def test_stdlib_uses_cached_info_no_subprocess(self) -> None:
        """`scope="stdlib"` is answered from the cached probe, not a subprocess."""
        info = EnvironmentInfo(
            version="3.11.9",
            sys_path=(),
            distributions={},
            importable={},
            stdlib="/some/stdlib",
        )
        with (
            patch(
                "mcp_tools_py.utils.environment_info.get_environment_info",
                return_value=info,
            ),
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
        ):
            resolution = resolve_scope("/stdlib/python", "stdlib")

            assert resolution.directory == "/some/stdlib"
            assert resolution.error is None
            mock_exec.assert_not_called()

    @pytest.mark.parametrize(
        "retry, expected",
        [
            (
                make_command_result(stdout="/some/stdlib\n"),
                ScopeResolution(directory="/some/stdlib"),
            ),
            (
                make_command_result(
                    return_code=-1,
                    timed_out=True,
                    execution_error="Process timed out after 30 seconds",
                ),
                ScopeResolution(
                    error="resolving scope 'stdlib' timed out after "
                    f"{PROBE_TIMEOUT_SECONDS} seconds"
                ),
            ),
            (
                make_command_result(return_code=1, stderr="boom"),
                ScopeResolution(error="could not resolve scope 'stdlib': boom"),
            ),
        ],
    )
    def test_stdlib_retries_after_cached_failure(
        self, retry: CommandResult, expected: ScopeResolution
    ) -> None:
        """A cached failure sends `stdlib` to a fresh probe, and stays cached."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.side_effect = [
                make_command_result(return_code=1, stderr="info failed"),
                retry,
            ]

            assert resolve_scope("/stdlib-retry/python", "stdlib") == expected
            assert mock_exec.call_args.args[0][-2:] == ["scope", "stdlib"]

            error = get_environment_info("/stdlib-retry/python").error
            assert error is not None and "info failed" in error
            assert mock_exec.call_count == 2

    def test_package_scope_runs_the_scope_subcommand(self) -> None:
        """A non-stdlib scope runs `probe.py scope NAME` uncached."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout="/some/dir\n")

            resolution = resolve_scope("/scope-pkg/python", "mypy")

            assert resolution.directory == "/some/dir"
            assert resolution.error is None
            mock_exec.assert_called_once()
            assert mock_exec.call_args.args[0] == [
                "/scope-pkg/python",
                str(probe_script_path()),
                "scope",
                "mypy",
            ]
            assert (
                mock_exec.call_args.kwargs["timeout_seconds"] == PROBE_TIMEOUT_SECONDS
            )

    def test_timeout_is_reported(self) -> None:
        """A probe that times out yields a reason naming the scope."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=-1,
                timed_out=True,
                execution_error="Process timed out after 30 seconds",
            )

            resolution = resolve_scope("/scope-timeout/python", "mypy")

            assert resolution.directory is None
            assert resolution.error is not None
            assert "timed out" in resolution.error
            assert "mypy" in resolution.error

    def test_nonzero_exit_is_reported(self) -> None:
        """A non-zero exit yields a reason quoting the child's stderr."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=1, stderr="no module"
            )

            resolution = resolve_scope("/scope-fail/python", "mypy")

            assert resolution.directory is None
            assert resolution.error is not None
            assert "no module" in resolution.error

    def test_real_child_resolves_stdlib_package_scope(self) -> None:
        """Resolving `scope="json"` under the real interpreter finds its package."""
        resolution = resolve_scope(sys.executable, "json")

        assert resolution.error is None
        assert resolution.directory is not None
        assert (Path(resolution.directory) / "__init__.py").is_file()

    def test_dotted_scope_import_leaves_the_working_directory_untouched(
        self, side_effect_package: tuple[Path, Path]
    ) -> None:
        """Resolving `fake_pkg.sub` imports `fake_pkg`, but not in the project."""
        fake_project, cwd_record = side_effect_package

        resolution = resolve_scope(sys.executable, "fake_pkg.sub")

        assert resolution.error is None
        assert cwd_record.is_file()
        assert not (fake_project / "marker.txt").exists()
        assert not Path(cwd_record.read_text(encoding="utf-8")).exists()


class TestRunProbeWorkingDirectory:
    """Every probe runs in a fresh temporary working directory."""

    @pytest.mark.parametrize(
        "call_probe",
        [
            lambda: _get_library_source("json.encoder", 50, "/cwd-source/python"),
            lambda: resolve_scope("/cwd-scope/python", "json"),
            lambda: locate_packages("/cwd-locate/python", ["json"]),
            lambda: get_environment_info("/cwd-info/python"),
        ],
        ids=["source", "scope", "locate", "info"],
    )
    def test_every_probe_runs_outside_the_working_directory(
        self, call_probe: Callable[[], object]
    ) -> None:
        """No probe caller lets the child inherit the server's working directory."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout="{}")

            call_probe()

        cwd = mock_exec.call_args.kwargs["cwd"]
        assert cwd
        assert Path(cwd) != Path(os.getcwd())

    def test_temporary_directory_ignores_cleanup_errors(self) -> None:
        """A temp dir still held open on Windows must not fail the call."""
        with (
            patch(
                "mcp_tools_py.utils.environment_info.tempfile.TemporaryDirectory"
            ) as mock_tmp,
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
        ):
            mock_tmp.return_value.__enter__.return_value = "/probe-workdir"
            mock_exec.return_value = make_command_result()

            run_probe("/cleanup/python", "info")

        mock_tmp.assert_called_once_with(ignore_cleanup_errors=True)
        assert mock_exec.call_args.kwargs["cwd"] == "/probe-workdir"
