"""Test rate limiting policies on the MCP Gateway."""

import os
import subprocess
import time
import requests
import pytest


@pytest.fixture
def ratelimit_enabled():
    """Check if RateLimitPolicy is deployed. Skip if not."""
    r = subprocess.run(
        ["oc", "get", "ratelimitpolicy", "-n", "gateway-system", "--no-headers"],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        pytest.skip("No RateLimitPolicy deployed; skipping rate limit tests")
    return True


@pytest.fixture
def api_key():
    """API key for authenticated requests (rate limit tests need to pass auth first)."""
    key = os.environ.get("MCP_API_KEY")
    if not key:
        pytest.skip("MCP_API_KEY not set; skipping rate limit tests (auth required)")
    return key


def _mcp_initialize(url, headers=None, host_header=None):
    """Send MCP initialize request."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-ratelimit", "version": "0.1.0"},
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


class TestBurstThrottling:
    """Burst rate limit: sending more than burst limit in <1s should trigger 429."""

    def test_burst_triggers_429(self, gateway_url, gateway_host_header, api_key, ratelimit_enabled):
        """Send concurrent requests exceeding the burst limit (default: 10/s)."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        auth_headers = {"Authorization": f"Bearer {api_key}"}

        def fire():
            return _mcp_initialize(gateway_url, headers=auth_headers, host_header=gateway_host_header).status_code

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(fire) for _ in range(25)]
            statuses = [f.result() for f in as_completed(futures)]

        has_429 = 429 in statuses
        assert has_429, (
            f"Expected at least one 429 after burst, got statuses: {statuses}"
        )


class TestSustainedRate:
    """Requests within the sustained rate limit should all succeed."""

    def test_within_limit_all_200(self, gateway_url, gateway_host_header, api_key, ratelimit_enabled):
        """Send a few spaced requests — all should pass."""
        auth_headers = {"Authorization": f"Bearer {api_key}"}
        time.sleep(2)
        statuses = []
        for i in range(3):
            resp = _mcp_initialize(gateway_url, headers=auth_headers, host_header=gateway_host_header)
            statuses.append(resp.status_code)
            time.sleep(1)

        assert all(s == 200 for s in statuses), (
            f"Expected all 200, got: {statuses}"
        )
