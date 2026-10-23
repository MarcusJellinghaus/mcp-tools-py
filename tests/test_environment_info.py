"""Tests for the one-shot environment probe and its parsed result."""

import json
import logging
import platform
import site
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.utils.environment_info import (
    PROBE_TIMEOUT_SECONDS,
    PROBED_MODULES,
    TOOL_DISTRIBUTIONS,
    TOOL_MODULES,
    EnvironmentInfo,
    get_environment_info,
    locate_packages,
    probe_script_path,
    resolve_scope,
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

    def test_stdlib_failure_when_probe_untrustworthy(self) -> None:
        """A failed probe leaves `stdlib` unresolved, and says why."""
        info = EnvironmentInfo(
            version="",
            sys_path=(),
            distributions={},
            importable={},
            error="boom",
        )
        with (
            patch(
                "mcp_tools_py.utils.environment_info.get_environment_info",
                return_value=info,
            ),
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
        ):
            resolution = resolve_scope("/stdlib-fail/python", "stdlib")

            assert resolution.directory is None
            assert resolution.error is not None
            assert "boom" in resolution.error
            mock_exec.assert_not_called()

    def test_package_scope_runs_the_scope_subcommand(self) -> None:
        """A non-stdlib scope runs `probe.py scope NAME` uncached."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout="/some/dir\n")

            resolution = resolve_scope("/scope-pkg/python", "mypy")

            assert resolution.directory == "/some/dir"
            assert resolution.error is None
            mock_exec.assert_called_once_with(
                ["/scope-pkg/python", str(probe_script_path()), "scope", "mypy"],
                timeout_seconds=PROBE_TIMEOUT_SECONDS,
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

    def test_real_child_reports_the_user_site_directory(self) -> None:
        """The user site directory counts as a site directory.

        A project installed with `pip install --user` resolves there, and
        prepending that whole tree to PYTHONPATH would put it ahead of the tool
        environment's own grimp and click.
        """
        result = execute_command(
            [sys.executable, str(probe_script_path()), "locate", "json"],
            timeout_seconds=60,
        )

        assert result.return_code == 0, result.stderr
        site_dirs = [Path(d) for d in json.loads(result.stdout)["site_dirs"]]
        assert Path(site.getusersitepackages()) in site_dirs

    def test_real_child_locates_a_dotted_name_from_its_root(
        self, tmp_path: Path
    ) -> None:
        """A dotted name reports the directory its root is importable from.

        grimp raises `NotATopLevelModule` only when the parent has a location,
        so `ns.pkg` under a namespace `ns` is a root package import-linter
        accepts.  Reporting `<root>/ns` would put a directory on PYTHONPATH
        that imports nothing, and the bridge would fail without saying so.
        """
        package = tmp_path / "ns" / "pkg"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")

        result = execute_command(
            [sys.executable, str(probe_script_path()), "locate", "ns.pkg"],
            timeout_seconds=60,
            env={"PYTHONPATH": str(tmp_path)},
        )

        assert result.return_code == 0, result.stderr
        blob = json.loads(result.stdout)
        directories = blob["packages"]["ns.pkg"]
        assert [Path(directory) for directory in directories] == [tmp_path]

    def test_real_child_reports_the_stdlib_directory(self) -> None:
        """The info blob names this interpreter's stdlib directory."""
        result = execute_command(
            [sys.executable, str(probe_script_path()), "info", "json"],
            timeout_seconds=60,
        )

        assert result.return_code == 0, result.stderr
        blob = json.loads(result.stdout)
        stdlib = Path(blob["stdlib"])
        assert stdlib.is_dir()
        assert (stdlib / "os.py").is_file()

    def test_real_child_resolves_a_package_scope(self) -> None:
        """`scope NAME` resolves a package name to its own directory."""
        result = execute_command(
            [sys.executable, str(probe_script_path()), "scope", "json"],
            timeout_seconds=60,
        )

        assert result.return_code == 0, result.stderr
        assert (Path(result.stdout.strip()) / "__init__.py").is_file()

    def test_real_child_resolves_a_dotted_module_scope(self) -> None:
        """A dotted module name resolves to its root package's directory."""
        package_result = execute_command(
            [sys.executable, str(probe_script_path()), "scope", "json"],
            timeout_seconds=60,
        )
        module_result = execute_command(
            [sys.executable, str(probe_script_path()), "scope", "json.decoder"],
            timeout_seconds=60,
        )

        assert package_result.return_code == 0, package_result.stderr
        assert module_result.return_code == 0, module_result.stderr
        assert Path(module_result.stdout.strip()) == Path(package_result.stdout.strip())

    def test_real_child_scope_reports_unknown_name(self) -> None:
        """An unresolvable name fails with a message naming it."""
        result = execute_command(
            [sys.executable, str(probe_script_path()), "scope", "nosuchmodule_xyz123"],
            timeout_seconds=60,
        )

        assert result.return_code != 0
        assert "nosuchmodule_xyz123" in result.stderr

    def test_real_child_resolves_a_non_ascii_scope_path(self, tmp_path: Path) -> None:
        """A resolved directory containing non-ASCII characters is not mangled.

        A venv or site-packages path can contain an accented username or
        similar; the reported directory must survive stdout's default
        encoding on Windows rather than raising UnicodeEncodeError.
        """
        root = tmp_path / "café"
        package = root / "pkg"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")

        result = execute_command(
            [sys.executable, str(probe_script_path()), "scope", "pkg"],
            timeout_seconds=60,
            env={"PYTHONPATH": str(root)},
        )

        assert result.return_code == 0, result.stderr
        assert Path(result.stdout.strip()) == package
