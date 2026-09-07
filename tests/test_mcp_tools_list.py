"""Test tools/list through the MCP Gateway."""

import json
import requests
import pytest


def _parse_sse_json(text):
    """Parse a JSON-RPC result from an SSE response body."""
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(text)


def _mcp_request(url, method, params=None, session_id=None, host_header=None):
    """Send an MCP JSON-RPC request and return the response."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    if host_header:
        headers["Host"] = host_header
    resp = requests.post(
        f"{url}/mcp",
        json=payload,
        headers=headers,
        timeout=30,
        verify=False,
    )
    resp.raise_for_status()
    return resp


def _mcp_json(resp):
    """Extract JSON from a response that may be SSE or plain JSON."""
    ct = resp.headers.get("Content-Type", "")
    if "text/event-stream" in ct:
        return _parse_sse_json(resp.text)
    return resp.json()


def _init_session(url, host_header=None):
    """Initialize an MCP session and return (response_json, session_id)."""
    resp = _mcp_request(url, "initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0.1.0"},
    }, host_header=host_header)
    session_id = resp.headers.get("Mcp-Session-Id")
    data = _mcp_json(resp)
    return data, session_id


class TestToolsListDirect:
    """Test tools/list directly against kubernetes-mcp-server."""

    def test_tools_list_returns_tools(self, k8s_mcp_url):
        """Direct call returns tools without prefix."""
        _, session_id = _init_session(k8s_mcp_url)
        resp = _mcp_request(k8s_mcp_url, "tools/list", session_id=session_id)
        result = _mcp_json(resp)
        assert "result" in result, f"Expected result key: {result}"
        tools = result["result"].get("tools", [])
        assert len(tools) > 0, "Expected at least one tool"
        tool_names = [t["name"] for t in tools]
        assert any("pods" in name for name in tool_names), (
            f"Expected a pods-related tool, got: {tool_names}"
        )


class TestToolsListViaGateway:
    """Test tools/list through the MCP Gateway (tools should be prefixed)."""

    def test_tools_list_via_gateway(self, gateway_url, gateway_host_header):
        """Gateway aggregates tools with k8s_ prefix."""
        _, session_id = _init_session(gateway_url, host_header=gateway_host_header)
        assert session_id, "Expected Mcp-Session-Id header in initialize response"

        resp = _mcp_request(
            gateway_url, "tools/list",
            session_id=session_id,
            host_header=gateway_host_header,
        )
        result = _mcp_json(resp)
        assert "result" in result, f"Expected result key: {result}"
        tools = result["result"].get("tools", [])
        assert len(tools) > 0, "Expected at least one tool from gateway"
        tool_names = [t["name"] for t in tools]
        prefixed = [n for n in tool_names if n.startswith("k8s_")]
        assert len(prefixed) > 0, (
            f"Expected k8s_ prefixed tools, got: {tool_names}"
        )
