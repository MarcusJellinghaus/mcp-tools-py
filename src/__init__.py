"""Version of the installed mcp-tools-py distribution."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mcp-tools-py")
except PackageNotFoundError:
    # Package is not installed
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
