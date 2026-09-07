import os
import subprocess
import pytest


def _run_oc(*args):
    """Run an oc command and return stdout."""
    result = subprocess.run(
        ["oc", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result


@pytest.fixture(scope="session")
def cluster_domain():
    """Get the cluster apps domain."""
    r = _run_oc(
        "get", "ingress.config", "cluster",
        "-o", "jsonpath={.spec.domain}",
    )
    if r.returncode != 0:
        pytest.skip("Cannot determine cluster domain; not logged in?")
    return r.stdout.strip()


@pytest.fixture(scope="session")
def gateway_namespace():
    return os.environ.get("GATEWAY_NS", "gateway-system")


@pytest.fixture(scope="session")
def k8s_mcp_namespace():
    return os.environ.get("K8S_MCP_NS", "kubernetes-mcp-server")


@pytest.fixture(scope="session")
def gateway_url(cluster_domain, gateway_namespace):
    """MCP Gateway endpoint URL.
    
    Supports GATEWAY_URL for full URL override (e.g. http://elb:8080),
    or GATEWAY_HOST for hostname-only override.
    """
    full_url = os.environ.get("GATEWAY_URL")
    if full_url:
        return full_url.rstrip("/")
    host = os.environ.get(
        "GATEWAY_HOST",
        f"mcp-gateway.{cluster_domain}",
    )
    # Detect ELB addresses (no TLS) vs cluster hostnames (TLS)
    scheme = os.environ.get("GATEWAY_SCHEME", "https")
    port = os.environ.get("GATEWAY_PORT", "")
    url = f"{scheme}://{host}"
    if port:
        url = f"{url}:{port}"
    return url


@pytest.fixture(scope="session")
def gateway_host_header(cluster_domain):
    """Host header to send when accessing gateway via ELB.
    
    Returns the expected hostname for the mcp listener, or None if
    not needed (direct hostname access).
    """
    if os.environ.get("GATEWAY_URL"):
        return os.environ.get(
            "GATEWAY_HOST_HEADER",
            f"mcp-gateway.{cluster_domain}",
        )
    return None


@pytest.fixture(scope="session")
def k8s_mcp_url(cluster_domain, k8s_mcp_namespace):
    """Direct kubernetes-mcp-server endpoint URL."""
    host = os.environ.get(
        "K8S_MCP_HOST",
        f"kubernetes-mcp-server.{cluster_domain}",
    )
    return f"https://{host}"
