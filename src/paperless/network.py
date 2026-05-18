import ipaddress
import socket
from collections.abc import Collection
from urllib.parse import ParseResult
from urllib.parse import urlparse


def is_public_ip(ip: str | int) -> bool:
    try:
        obj = ipaddress.ip_address(ip)
        return not (
            obj.is_private
            or obj.is_loopback
            or obj.is_link_local
            or obj.is_multicast
            or obj.is_unspecified
        )
    except ValueError:  # pragma: no cover
        return False


def resolve_hostname_ips(hostname: str) -> list[str]:
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve hostname: {hostname}") from e

    ips = [info[4][0] for info in addr_info if info and info[4]]
    if not ips:
        raise ValueError(f"Could not resolve hostname: {hostname}")
    return ips


def format_host_for_url(host: str) -> str:
    """
    Format IP address for URL use (wrap IPv6 in brackets).
    """
    try:
        ip_obj = ipaddress.ip_address(host)
        if ip_obj.version == 6:
            return f"[{host}]"
        return host
    except ValueError:
        return host


def validate_outbound_http_url(
    url: str,
    *,
    allowed_schemes: Collection[str] = ("http", "https"),
    allowed_ports: Collection[int] | None = None,
    allow_internal: bool = False,
) -> ParseResult:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    if scheme not in allowed_schemes or not parsed.hostname:
        raise ValueError("Invalid URL scheme or hostname.")

    default_port = 443 if scheme == "https" else 80
    try:
        port = parsed.port or default_port
    except ValueError as e:
        raise ValueError("Invalid URL scheme or hostname.") from e

    if allowed_ports and port not in allowed_ports:
        raise ValueError("Destination port not permitted.")

    if not allow_internal:
        for ip_str in resolve_hostname_ips(parsed.hostname):
            if not is_public_ip(ip_str):
                raise ValueError(
                    f"Connection blocked: {parsed.hostname} resolves to a non-public address",
                )

    return parsed
