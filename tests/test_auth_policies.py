"""Test auth policies on the MCP Gateway."""

import os
import requests
import pytest


@pytest.fixture
def api_key():
    """API key for authenticated requests. Set MCP_API_KEY env var."""
    key = os.environ.get("MCP_API_KEY")
    if not key:
        pytest.skip("MCP_API_KEY not set; skipping auth tests")
    return key


@pytest.fixture
def auth_enabled():
    """Check if AuthPolicy is deployed. Skip if not."""
    import subprocess
    r = subprocess.run(
        ["oc", "get", "authpolicy", "-n", "gateway-system", "--no-headers"],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        pytest.skip("No AuthPolicy deployed; skipping auth tests")
    return True


def _mcp_initialize(url, headers=None, host_header=None):
    """Send MCP initialize request."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.1.0"},
        },
    }
    h = {"Content-Type": "application/json", **(headers or {})}
    if host_header:
        h["Host"] = host_header
    return requests.post(
        f"{url}/mcp",
        json=payload,
        headers=h,
        timeout=30,
        verify=False,
    )


class TestNoAuth:
    """Requests without credentials should be rejected when AuthPolicy is active."""

    def test_no_auth_returns_401(self, gateway_url, gateway_host_header, auth_enabled):
        resp = _mcp_initialize(gateway_url, host_header=gateway_host_header)
        assert resp.status_code == 401, (
            f"Expected 401 without auth, got {resp.status_code}. "
            "Is AuthPolicy enabled?"
        )


class TestValidAuth:
    """Requests with valid API key should succeed."""

    def test_valid_key_returns_200(self, gateway_url, gateway_host_header, api_key, auth_enabled):
        resp = _mcp_initialize(
            gateway_url,
            headers={"Authorization": f"Bearer {api_key}"},
            host_header=gateway_host_header,
        )
        assert resp.status_code == 200, (
            f"Expected 200 with valid key, got {resp.status_code}: {resp.text}"
        )


class TestInvalidAuth:
    """Requests with invalid credentials should be rejected."""

    def test_invalid_key_returns_401(self, gateway_url, gateway_host_header, auth_enabled):
        resp = _mcp_initialize(
            gateway_url,
            headers={"Authorization": "Bearer invalid-key-12345"},
            host_header=gateway_host_header,
        )
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 with invalid key, got {resp.status_code}"
        )
