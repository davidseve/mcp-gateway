import os
import socket
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
def gateway_host_header(cluster_domain, gateway_url):
    """Host header to send when accessing gateway via ELB hostname (HTTP only).

    For HTTPS, SNI uses the URL hostname; Host header override is not needed
    when gateway_url already uses the mcp listener hostname.
    """
    if os.environ.get("GATEWAY_HOST_HEADER"):
        return os.environ.get("GATEWAY_HOST_HEADER")
    if "amazonaws.com" in gateway_url and gateway_url.startswith("http://"):
        return f"mcp-gateway.{cluster_domain}"
    return None


@pytest.fixture(scope="session", autouse=True)
def _gateway_dns_resolve(cluster_domain):
    """Resolve mcp hostname to Gateway ELB IP when public DNS is not updated yet."""
    resolve_ip = os.environ.get("GATEWAY_RESOLVE_IP", "").strip()
    if not resolve_ip:
        yield
        return

    hostname = os.environ.get(
        "GATEWAY_HOST_HEADER",
        f"mcp-gateway.{cluster_domain}",
    )
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(host, *args, **kwargs):
        if host == hostname:
            host = resolve_ip
        return original_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = patched_getaddrinfo
    yield
    socket.getaddrinfo = original_getaddrinfo


@pytest.fixture(scope="session")
def k8s_mcp_url(cluster_domain, k8s_mcp_namespace):
    """Direct kubernetes-mcp-server endpoint URL."""
    host = os.environ.get(
        "K8S_MCP_HOST",
        f"kubernetes-mcp-server.{cluster_domain}",
    )
    return f"https://{host}"
