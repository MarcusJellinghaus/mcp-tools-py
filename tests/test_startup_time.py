"""Integration test: MCP server startup must stay well under Claude Code's limit.

Claude Code launches this server as a subprocess and gives up on it if it does
not become ready within ~5 seconds. All startup work is Python import time
(imports + FastMCP construction + tool registration); there is no IO at boot.
This test measures that work in a fresh interpreter and asserts it finishes
within a conservative budget, so a regression (e.g. re-introducing a heavy
eager import) fails in CI instead of in a user's session.
"""

import subprocess
import sys
import time

import pytest

# Conservative budget. Claude Code's real limit is ~5s; steady-state startup is
# ~1s. 2s leaves headroom for slow/cold CI while still catching a regression
# that re-adds a heavy eager import.
STARTUP_BUDGET_SECONDS = 2.0

# Times the work main() does before the blocking serve loop: import the server
# module and construct it (which imports FastMCP and registers every tool).
_MEASURE_CODE = """
import time
from pathlib import Path
start = time.perf_counter()
from mcp_tools_py.server import create_server
create_server(Path("."))
print(time.perf_counter() - start)
"""


def _measure_startup_seconds() -> float:
    """Run the startup work in a fresh interpreter and return its duration.

    Returns:
        Seconds spent importing and constructing the server.
    """
    result = subprocess.run(
        [sys.executable, "-c", _MEASURE_CODE],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip().splitlines()[-1])


@pytest.mark.integration
def test_server_startup_within_budget() -> None:
    """Server construct-time stays under the startup budget.

    A warm-up run first compiles bytecode (.pyc) and warms the OS file cache,
    so the measured run reflects steady-state import cost rather than one-time
    compilation noise.
    """
    _measure_startup_seconds()  # warm-up: compile .pyc, warm caches
    elapsed = min(_measure_startup_seconds() for _ in range(3))

    assert elapsed < STARTUP_BUDGET_SECONDS, (
        f"Server startup took {elapsed:.2f}s, exceeding the "
        f"{STARTUP_BUDGET_SECONDS:.1f}s budget (Claude Code limit ~5s). "
        "A heavy module may now be imported eagerly at startup."
    )
