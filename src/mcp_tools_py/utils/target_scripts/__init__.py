"""Scripts executed by the *target* interpreter, never by the server's own.

Each module here is run by absolute file path under an interpreter that does
not have ``mcp_tools_py`` installed, so it must import from the standard
library only.  That is a consequence of the invocation, not a style rule:
running a file by path puts only that file's directory on ``sys.path``, so a
package-relative import would fail at runtime.  The
``target-scripts-stdlib-only`` contract in ``.importlinter`` enforces it.

Contrast with ``mcp_tools_py.refactoring.rope_cli``, which runs under
``sys.executable`` via ``-m`` and may import the project freely.
"""
