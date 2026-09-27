"""Captured lint-imports output samples shared by this package's tests."""

MODULE_PATH = "mcp_tools_py.code_checker_lint_imports.runners"


# Captured from import-linter 2.x on 2026-05-04 (clean run, this repo).
CLEAN_OUTPUT = """\
=================
import-linter 2.0
=================

---------
Contracts
---------

Analyzed 50 files, 100 dependencies.

Layered Architecture KEPT
Forbidden imports KEPT
Independence KEPT

---
Contracts: 3 kept, 0 broken.
"""


# Captured from import-linter 2.x on 2026-05-04 (synthetic broken run).
BROKEN_OUTPUT = """\
=================
import-linter 2.0
=================

---------
Contracts
---------

Analyzed 50 files, 100 dependencies.

Layered Architecture BROKEN [12 violations]
Forbidden imports KEPT

---
Contracts: 1 kept, 1 broken.
"""


# Captured from import-linter 2.x on 2026-05-04 (synthetic warnings run).
WARNINGS_OUTPUT = """\
=================
import-linter 2.0
=================

Analyzed 50 files, 100 dependencies.

No matches for ignored import mcp_coder.mcp_workspace_git -> mcp_workspace.git_operations.

Layered Architecture KEPT

Contracts: 1 kept, 0 broken.
"""


# Verbatim wrapped form from issue #171 reproduction.
WRAPPED_WARNING_OUTPUT = """\
Analyzed 50 files, 100 dependencies.

No matches for ignored import mcp_coder.mcp_workspace_git -> 
mcp_workspace.git_operations.

Layered Architecture KEPT

Contracts: 1 kept, 0 broken.
"""


# Captured from import-linter 2.x on 2026-05-04 (malformed/error run).
MALFORMED_OUTPUT = """\
Could not read any configuration. Please check that .importlinter exists.
"""
