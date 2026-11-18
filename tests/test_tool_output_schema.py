"""Guard tests: output shape of the dict-returning MCP tool.

FastMCP's `func_metadata` is annotation-sensitive: `dict[str, Any]` returns the
dict as structured output, while `typing.Dict[str, Any]` wraps it in
`{"result": ...}`. Respelling an annotation changes what clients receive, so the
unwrapped shape is pinned here.
"""

from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_tools_py.server import create_server


def _fastmcp(project_dir: Path) -> FastMCP:
    mcp = create_server(project_dir).mcp
    assert isinstance(mcp, FastMCP)
    return mcp


@pytest.mark.asyncio
async def test_output_schema_is_unwrapped(tmp_path: Path) -> None:
    tools = {tool.name: tool for tool in await _fastmcp(tmp_path).list_tools()}

    schema = tools["search_library_files"].outputSchema

    assert schema is not None
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is True
    assert "result" not in schema.get("properties", {})


@pytest.mark.asyncio
async def test_structured_content_is_unwrapped(tmp_path: Path) -> None:
    async with create_connected_server_and_client_session(
        _fastmcp(tmp_path)
    ) as session:
        result = await session.call_tool(
            "search_library_files", {"scope": "json", "glob": "__init__.py"}
        )

    assert not result.isError
    assert result.structuredContent is not None
    assert "result" not in result.structuredContent
    assert "scope_root" in result.structuredContent
