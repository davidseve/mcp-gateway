"""Test tools/list through the MCP Gateway."""

import requests
import pytest


def _mcp_request(url, method, params=None):
    """Send an MCP JSON-RPC request and return the parsed response."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }
    resp = requests.post(
        f"{url}/mcp",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
        verify=False,
    )
    resp.raise_for_status()
    return resp.json()


class TestToolsListDirect:
    """Test tools/list directly against kubernetes-mcp-server."""

    def test_tools_list_returns_tools(self, k8s_mcp_url):
        """Direct call returns tools without prefix."""
        _mcp_request(k8s_mcp_url, "initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.1.0"},
        })
        result = _mcp_request(k8s_mcp_url, "tools/list")
        assert "result" in result, f"Expected result key: {result}"
        tools = result["result"].get("tools", [])
        assert len(tools) > 0, "Expected at least one tool"
        tool_names = [t["name"] for t in tools]
        assert any("pods" in name for name in tool_names), (
            f"Expected a pods-related tool, got: {tool_names}"
        )


class TestToolsListViaGateway:
    """Test tools/list through the MCP Gateway (tools should be prefixed)."""

    def test_tools_list_via_gateway(self, gateway_url):
        """Gateway aggregates tools with k8s_ prefix."""
        _mcp_request(gateway_url, "initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.1.0"},
        })
        result = _mcp_request(gateway_url, "tools/list")
        assert "result" in result, f"Expected result key: {result}"
        tools = result["result"].get("tools", [])
        assert len(tools) > 0, "Expected at least one tool from gateway"
        tool_names = [t["name"] for t in tools]
        prefixed = [n for n in tool_names if n.startswith("k8s_")]
        assert len(prefixed) > 0, (
            f"Expected k8s_ prefixed tools, got: {tool_names}"
        )
