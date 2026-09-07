"""Health checks for MCP Gateway and kubernetes-mcp-server."""

import requests
import pytest


class TestKubernetesMcpServerDirect:
    """Test kubernetes-mcp-server directly (bypass gateway)."""

    def test_k8s_mcp_endpoint_reachable(self, k8s_mcp_url):
        """The kubernetes-mcp-server endpoint responds."""
        resp = requests.post(
            f"{k8s_mcp_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0.1.0"},
                },
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
            verify=False,
        )
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )


class TestGatewayHealth:
    """Test MCP Gateway is running and reachable."""

    def test_gateway_endpoint_reachable(self, gateway_url, gateway_host_header):
        """The gateway endpoint responds (may return 4xx without auth, that's OK)."""
        headers = {"Content-Type": "application/json"}
        if gateway_host_header:
            headers["Host"] = gateway_host_header
        try:
            resp = requests.post(
                f"{gateway_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0.1.0"},
                    },
                },
                headers=headers,
                timeout=30,
                verify=False,
            )
            assert resp.status_code in (200, 401, 403), (
                f"Unexpected status {resp.status_code}: {resp.text}"
            )
        except requests.ConnectionError:
            pytest.fail("Cannot connect to MCP Gateway endpoint")
