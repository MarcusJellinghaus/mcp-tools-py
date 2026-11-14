"""Tests for `target_scripts/probe.py`, run as a real child process."""

import json
import platform
import site
import sys
from pathlib import Path

from mcp_tools_py.utils.environment_info import probe_script_path
from mcp_tools_py.utils.subprocess_runner import execute_command


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

    def test_real_child_scope_stdlib_matches_info(self) -> None:
        """`scope stdlib` names the same directory the info blob does."""
        info_result = execute_command(
            [sys.executable, str(probe_script_path()), "info"],
            timeout_seconds=60,
        )
        scope_result = execute_command(
            [sys.executable, str(probe_script_path()), "scope", "stdlib"],
            timeout_seconds=60,
        )

        assert info_result.return_code == 0, info_result.stderr
        assert scope_result.return_code == 0, scope_result.stderr
        assert scope_result.stdout.strip() == json.loads(info_result.stdout)["stdlib"]

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
