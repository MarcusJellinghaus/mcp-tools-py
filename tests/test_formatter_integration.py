"""End-to-end formatter tests: real projects, real formatter binaries, no mocks."""

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mcp_tools_py.formatter.formatter_tools import FormatterTools
from mcp_tools_py.formatter.runner import run_format_code
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.tool_context import ToolContext

_RUFF_PYPROJECT = '[tool.ruff.format]\nquote-style = "double"\n'
_BLACK_PYPROJECT = "[tool.black]\nline-length = 88\n"

# Stdlib-only imports: no first-party/third-party classification can differ.
_FORMATTED = (
    b"import os\n"
    b"import sys\n"
    b"\n"
    b"\n"
    b"def main() -> None:\n"
    b"    print(os.sep, sys.argv)\n"
)
_UNFORMATTED = "import sys\nimport os\n\n\ndef add( a,b ):\n    return a+b\n"
_BLACK_EXPECTED = "import os\nimport sys\n\n\ndef add(a, b):\n    return a + b\n"


def _project(tmp_path: Path, pyproject: str, files: Mapping[str, str | bytes]) -> Path:
    """Write a project with a pyproject.toml and some source files."""
    (tmp_path / "pyproject.toml").write_text(pyproject)
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        # Bytes on disk, so no platform newline translation.
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
    return tmp_path


def _text(path: Path) -> str:
    return path.read_bytes().decode().replace("\r\n", "\n")


def _capture_mcp_run_format_code(project_dir: Path) -> Any:
    """Register FormatterTools against the real tool env and capture the tool."""
    context = ToolContext(
        project_dir=project_dir, environment=PythonEnvironment.resolve()
    )
    captured: dict[str, Any] = {}

    def capture(fn: Any) -> Any:
        captured[fn.__name__] = fn
        return fn

    mock_mcp = MagicMock()
    mock_mcp.tool.return_value = capture
    FormatterTools(context).register(mock_mcp)
    return captured["run_format_code"]


class TestNoChurn:
    """A migrated ruff repo is left byte-for-byte alone."""

    @pytest.mark.parametrize(
        "pyproject",
        [
            pytest.param(_RUFF_PYPROJECT, id="detected"),
            pytest.param(
                _RUFF_PYPROJECT + '\n[tool.mcp-tools-py]\nformatter = "ruff"\n',
                id="explicit_key",
            ),
        ],
    )
    def test_ruff_repo_formatted_source_unchanged(
        self, tmp_path: Path, pyproject: str
    ) -> None:
        """Acceptance: no diff on a ruff-formatted repo with default steps."""
        root = _project(tmp_path, pyproject, {"src/mod.py": _FORMATTED})
        before = (root / "src" / "mod.py").read_bytes()

        results = run_format_code(sys.executable, root, ["src"], steps=None)

        assert (root / "src" / "mod.py").read_bytes() == before
        assert list(results) == ["ruff_imports", "ruff_format"]
        assert all(r.success for r in results.values())


class TestBlackRepo:
    """Repos that have not migrated keep isort + black."""

    def test_black_repo_resolves_to_isort_black(self, tmp_path: Path) -> None:
        """Acceptance: a [tool.black] repo is sorted and formatted by isort+black."""
        root = _project(tmp_path, _BLACK_PYPROJECT, {"src/mod.py": _UNFORMATTED})

        results = run_format_code(sys.executable, root, ["src"], steps=None)

        assert list(results) == ["isort", "black"]
        assert all(r.success for r in results.values())
        assert _text(root / "src" / "mod.py") == _BLACK_EXPECTED

    def test_explicit_isort_black_on_ruff_repo(self, tmp_path: Path) -> None:
        """Acceptance: explicit ["isort", "black"] overrides detection unchanged."""
        root = _project(tmp_path, _RUFF_PYPROJECT, {"src/mod.py": _UNFORMATTED})

        results = run_format_code(
            sys.executable, root, ["src"], steps=["isort", "black"]
        )

        assert list(results) == ["isort", "black"]
        for result in results.values():
            assert result.success
            assert result.unparsable_files == []
            assert any(p.endswith("mod.py") for p in result.files_changed)
        assert _text(root / "src" / "mod.py") == _BLACK_EXPECTED

    def test_python_executable_is_inert(self, tmp_path: Path) -> None:
        """Acceptance: a bogus python_executable does not change which binary runs."""
        root = _project(tmp_path, _BLACK_PYPROJECT, {"src/mod.py": _UNFORMATTED})

        results = run_format_code("/nonexistent/python", root, ["src"])

        assert all(r.success for r in results.values())
        assert _text(root / "src" / "mod.py") == _BLACK_EXPECTED


class TestParseError:
    """An unparsable file fails the step without stopping the other files."""

    _FILES = {
        "src/good.py": "import sys\nimport os\nx = [1,2]\n",
        "src/bad.py": "def broken(:\n",
    }

    def test_default_steps_continue_past_unparsable_file(self, tmp_path: Path) -> None:
        """Acceptance: success=False, unparsable_files set, the rest still processed."""
        root = _project(tmp_path, _RUFF_PYPROJECT, self._FILES)

        results = run_format_code(sys.executable, root, ["src"])

        assert list(results) == ["ruff_imports", "ruff_format"]
        for step in ("ruff_imports", "ruff_format"):
            assert results[step].success is False
            assert "src/bad.py" in results[step].unparsable_files
        good = _text(root / "src" / "good.py")
        assert "import os\nimport sys\n" in good
        assert "x = [1, 2]" in good

    def test_check_only_names_unparsable_file(self, tmp_path: Path) -> None:
        """Acceptance: check mode names the file it could not read."""
        root = _project(tmp_path, _RUFF_PYPROJECT, self._FILES)

        results = run_format_code(
            sys.executable, root, ["src"], steps=["ruff_format"], check_only=True
        )

        assert results["ruff_format"].success is False
        assert "src/bad.py" in results["ruff_format"].unparsable_files


class TestResolutionErrors:
    """Caller and configuration errors surface at both entry points."""

    def test_empty_steps_rejected_by_runner(self, tmp_path: Path) -> None:
        """Acceptance: steps=[] raises at the runner layer."""
        root = _project(tmp_path, _RUFF_PYPROJECT, {"src/mod.py": _FORMATTED})

        with pytest.raises(ValueError, match="must not be empty"):
            run_format_code(sys.executable, root, ["src"], steps=[])

    def test_empty_steps_rejected_by_mcp_tool(self, tmp_path: Path) -> None:
        """Acceptance: steps=[] returns an error string at the MCP layer."""
        root = _project(tmp_path, _RUFF_PYPROJECT, {"src/mod.py": _FORMATTED})
        run_format = _capture_mcp_run_format_code(root)

        result = run_format(steps=[], target_directories=["src"])

        assert result.startswith("Error:")
        assert "must not be empty" in result

    @pytest.mark.parametrize(
        "pyproject",
        [
            pytest.param(_RUFF_PYPROJECT + "\n" + _BLACK_PYPROJECT, id="both"),
            pytest.param('[project]\nname = "demo"\n', id="neither"),
        ],
    )
    def test_ambiguous_formatter_names_key_and_file(
        self, tmp_path: Path, pyproject: str
    ) -> None:
        """Acceptance: both or neither declared errors, naming the key and file."""
        root = _project(tmp_path, pyproject, {"src/mod.py": _FORMATTED})

        with pytest.raises(ValueError) as exc_info:
            run_format_code(sys.executable, root, ["src"])

        message = str(exc_info.value)
        assert "[tool.mcp-tools-py] formatter" in message
        assert str(root / "pyproject.toml") in message


class TestVersionLine:
    """Each step's output names the formatter version it ran."""

    @pytest.mark.parametrize(
        ("pyproject", "tools"),
        [
            pytest.param(
                _RUFF_PYPROJECT,
                {"ruff_imports": "ruff", "ruff_format": "ruff"},
                id="ruff",
            ),
            pytest.param(
                _BLACK_PYPROJECT, {"isort": "isort", "black": "black"}, id="black"
            ),
        ],
    )
    def test_first_output_line_names_tool_and_version(
        self, tmp_path: Path, pyproject: str, tools: dict[str, str]
    ) -> None:
        """Acceptance: every step's output starts with '<tool> <version>'."""
        root = _project(tmp_path, pyproject, {"src/mod.py": _FORMATTED})

        results = run_format_code(sys.executable, root, ["src"])

        assert list(results) == list(tools)
        for step, tool in tools.items():
            name, version = results[step].output.splitlines()[0].split(maxsplit=1)
            assert name == tool
            assert version != "unknown"


class TestMcpLayerAgrees:
    """The MCP tool resolves the same default steps as the runner."""

    def test_mcp_default_steps_match_runner(self, tmp_path: Path) -> None:
        """Acceptance: one defaulting rule, two entry points."""
        root = _project(tmp_path, _RUFF_PYPROJECT, {"src/mod.py": _FORMATTED})
        run_format = _capture_mcp_run_format_code(root)

        result = run_format(target_directories=["src"])

        assert "## ruff_imports" in result
        assert "## ruff_format" in result
        assert "## black" not in result
