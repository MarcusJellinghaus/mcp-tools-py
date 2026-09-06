"""Everything a tool registrar needs, and nothing about the server.

Layer 1 and 2 of the environment model, seen from a registrar: the values a
tool needs to build its command line, plus the two questions it asks about
the target environment — is this tool there, and what do I say when it is
not.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mcp_tools_py.utils.environment_info import (
    TOOL_MODULES,
    TOOL_PACKAGES,
    get_environment_info,
)
from mcp_tools_py.utils.project_config import ToolName, get_check_timeout
from mcp_tools_py.utils.python_environment import PythonEnvironment

logger = logging.getLogger(__name__)

# Tools that are only ever run through their console script.  Derived from
# `TOOL_MODULES` rather than restated: the probe is asked about module names
# and so cannot answer for one of these.
CONSOLE_SCRIPT_TOOLS: frozenset[str] = frozenset(
    key for key, module in TOOL_MODULES.items() if module is None
)


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool registrar needs, and nothing about the server.

    Attributes:
        project_dir: Path to the project the tools run against.
        environment: The Python environment the tools run in.
        test_folder: Path to the test folder, relative to `project_dir`.
        keep_temp_files: Whether to keep temporary files after a test run.
        vulture_whitelist: Filename of the vulture whitelist.
        check_timeout: Server-level subprocess timeout in seconds, if any.
    """

    project_dir: Path
    environment: PythonEnvironment
    test_folder: str = "tests"
    keep_temp_files: bool = False
    vulture_whitelist: str = "vulture_whitelist.py"
    check_timeout: Optional[int] = None

    def is_tool_available(self, tool_name: str) -> bool:
        """Check whether `tool_name` can be run in this environment.

        A console-script-only tool is answered from the filesystem; the probe
        cannot answer for one, because it is asked about module names.  Every
        other tool is answered from the one-shot environment probe, which
        fails open: a probe that could not be trusted reports the tool
        available so the call proceeds and surfaces the real error.

        Args:
            tool_name: Tool key to look up.

        Returns:
            True if the tool is available.
        """
        if tool_name in CONSOLE_SCRIPT_TOOLS:
            available = self.environment.binary(tool_name) is not None
            if not available:
                logger.warning("%s", self.unavailable_message(tool_name))
            return available

        info = get_environment_info(str(self.environment.interpreter))
        if info.error:
            logger.warning(
                "cannot describe the environment at %s: %s. Assuming %s is available.",
                self.environment.interpreter,
                info.error,
                tool_name,
            )
        available = info.importable.get(tool_name, False)
        if not available:
            logger.warning("%s", self.unavailable_message(tool_name))
        return available

    def unavailable_message(self, tool_name: str) -> str:
        """Build the standard "tool not available" message for `tool_name`.

        Args:
            tool_name: Tool key that could not be run.

        Returns:
            A message naming --python-executable and the location searched.
            The distribution to install comes from `TOOL_PACKAGES`, which maps
            a key to its distribution when the two differ (import-linter
            provides `lint-imports`).  For a `python -m` tool the probe adds
            the Python version and, when the distribution is installed but the
            module will not import, says so — a broken install rather than a
            missing one.
        """
        name = TOOL_PACKAGES.get(tool_name, tool_name)
        if tool_name in CONSOLE_SCRIPT_TOOLS:
            return (
                f"{tool_name} is not available. No {tool_name} console script was "
                f"found in {self.environment.bin_dir}. Ensure --python-executable "
                f"points to an environment where {name} is installed. "
                f"Restart the server after installing."
            )

        info = get_environment_info(str(self.environment.interpreter))
        where = str(self.environment.interpreter)
        if not info.error:
            where = f"{where}, Python {info.version}"
        installed = info.distributions.get(name.lower())
        broken = (
            f" Distribution {name} {installed} is installed there, "
            f"so the installation is broken."
            if installed is not None
            else ""
        )
        return (
            f"{tool_name} is not available in the configured Python environment "
            f"({where}). Ensure --python-executable points to the environment "
            f"where {name} is installed.{broken} "
            f"Restart the server after installing."
        )

    def resolve_timeout(self, tool: ToolName, explicit: Optional[int] = None) -> int:
        """Resolve the subprocess timeout in seconds for one program.

        Args:
            tool: Name of the program the timeout applies to.
            explicit: Per-call timeout supplied by the caller, if any.

        Returns:
            Positive number of seconds.  A ``ValueError`` propagates when
            pyproject.toml is malformed or a configured value is invalid.
        """
        return get_check_timeout(
            str(self.project_dir), tool, explicit, self.check_timeout
        )
