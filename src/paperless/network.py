import functools
import ipaddress
import re
import socket
from collections.abc import Callable
from collections.abc import Collection
from collections.abc import Iterable
from enum import StrEnum
from typing import Any
from typing import Self
from typing import TypeAlias
from urllib.parse import ParseResult
from urllib.parse import urlparse

import anyio
import httpx

# requires-python is >=3.11, so no PEP 695 `type` statement.
IPAddress: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address

# Ranges that ipaddress reports as global but which still reach internal hosts.
_NON_PUBLIC_NETWORKS = (
    # RFC 6052 NAT64 well-known prefix: 64:ff9b::7f00:1 is 127.0.0.1 wherever
    # a NAT64 gateway exists, yet ipaddress classifies the prefix as global.
    ipaddress.ip_network("64:ff9b::/96"),
)


class BlockReason(StrEnum):
    NON_PUBLIC_ADDRESS = "non_public_address"
    UNIX_SOCKET = "unix_socket"


class OutboundRequestBlockedError(Exception):
    """
    An outbound connection was refused by policy before any socket was opened.

    For NON_PUBLIC_ADDRESS, ``host`` is the name or literal being connected to
    and ``address`` the first offending address. For UNIX_SOCKET, ``host`` is
    the socket path and ``port`` and ``address`` are None.

    ``address`` is deliberately left out of the message: the message is logged
    and stored on failed tasks, and must not disclose internal addresses.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int | None,
        reason: BlockReason,
        address: IPAddress | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.reason = reason
        self.address = address
        target = host if port is None else f"{host}:{port}"
        super().__init__(f"Outbound connection to {target} blocked ({reason})")

    def __reduce__(self) -> tuple[Callable[..., Self], tuple[object, ...]]:
        # Celery rebuilds failed-task exceptions by pickling; keyword-only
        # fields cannot be recovered from ``args`` alone.
        return (
            functools.partial(
                type(self),
                host=self.host,
                port=self.port,
                reason=self.reason,
                address=self.address,
            ),
            (),
        )


class HostResolutionError(Exception):
    """The resolver returned no usable addresses for a host."""

    def __init__(self, *, host: str, detail: str) -> None:
        self.host = host
        self.detail = detail
        super().__init__(f"Could not resolve {host}: {detail}")

    def __reduce__(self) -> tuple[Callable[..., Self], tuple[object, ...]]:
        return (
            functools.partial(type(self), host=self.host, detail=self.detail),
            (),
        )


def blocked_message(exc: OutboundRequestBlockedError | HostResolutionError) -> str:
    """User-facing text for validation errors, kept stable for existing callers."""
    if isinstance(exc, HostResolutionError):
        return f"Could not resolve hostname: {exc.host}"
    if exc.reason is BlockReason.UNIX_SOCKET:
        return "Connection blocked: unix sockets are not permitted"
    return f"Connection blocked: {exc.host} resolves to a non-public address"


def is_public_ip(ip: IPAddress) -> bool:
    """
    True when ``ip`` is globally routable unicast and not in a range that
    ipaddress reports as global but which still reaches internal hosts.
    """
    return (
        ip.is_global
        and not ip.is_multicast
        and not any(ip in network for network in _NON_PUBLIC_NETWORKS)
    )


# Resolver indirection so tests can fake DNS for this module without changing
# how the stock httpcore backends resolve the literals the guard dials.
_getaddrinfo = socket.getaddrinfo
_agetaddrinfo = anyio.getaddrinfo


def _parse_ip_literal(host: str) -> IPAddress | None:
    try:
        return ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return None


def _collect_addresses(
    host: str,
    infos: Iterable[tuple[Any, ...]],
) -> tuple[IPAddress, ...]:
    # dict keys keep the first occurrence and resolver order
    addresses: dict[IPAddress, None] = {}
    for info in infos:
        address = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        addresses.setdefault(address, None)
    if not addresses:
        raise HostResolutionError(host=host, detail="no addresses returned")
    return tuple(addresses)


def _require_public(
    host: str,
    port: int | None,
    addresses: tuple[IPAddress, ...],
) -> tuple[IPAddress, ...]:
    for address in addresses:
        if not is_public_ip(address):
            raise OutboundRequestBlockedError(
                host=host,
                port=port,
                reason=BlockReason.NON_PUBLIC_ADDRESS,
                address=address,
            )
    return addresses


def resolve_public_addresses(host: str, port: int | None) -> tuple[IPAddress, ...]:
    """
    Resolve ``host`` and return its addresses in resolver order, or raise if
    any of them is non-public. A name is rejected as a whole; offending
    addresses are never filtered out.
    """
    literal = _parse_ip_literal(host)
    if literal is not None:
        return _require_public(host, port, (literal,))
    try:
        infos = _getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as e:
        raise HostResolutionError(host=host, detail=str(e)) from e
    return _require_public(host, port, _collect_addresses(host, infos))


async def aresolve_public_addresses(
    host: str,
    port: int | None,
) -> tuple[IPAddress, ...]:
    """Async variant of resolve_public_addresses."""
    literal = _parse_ip_literal(host)
    if literal is not None:
        return _require_public(host, port, (literal,))
    try:
        infos = await _agetaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as e:
        raise HostResolutionError(host=host, detail=str(e)) from e
    return _require_public(host, port, _collect_addresses(host, infos))


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


# urllib3 treats a backslash as ending the authority while urlparse and httpx do
# not, so the host checked here could differ from the one that is dialled.
# Control and whitespace characters are refused for the same reason.
_UNSAFE_URL_CHARS = re.compile(r"[\\\x00-\x1f\x7f\s]")


def _dns_name(url: str) -> str:
    """
    The ASCII hostname that httpx and urllib3 look up for ``url``.

    urlparse keeps a non-ASCII hostname as typed, and getaddrinfo would then
    encode it with the stdlib IDNA 2003 codec. That maps some characters
    differently from the IDNA 2008 encoding the HTTP clients use ("faß"
    becomes "fass" instead of "xn--fa-hia"), so the check would resolve a
    different name from the one that is connected to.
    """
    try:
        return httpx.URL(url).raw_host.decode("ascii")
    except (httpx.InvalidURL, UnicodeError) as e:
        raise ValueError("Invalid URL scheme or hostname.") from e


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
        if _UNSAFE_URL_CHARS.search(url):
            raise ValueError("Invalid URL scheme or hostname.")
        try:
            resolve_public_addresses(_dns_name(url), port)
        except (OutboundRequestBlockedError, HostResolutionError) as e:
            raise ValueError(blocked_message(e)) from e

    return parsed


def _rewrite_request_to_pinned_ip(
    request: httpx.Request,
    *,
    allow_internal: bool,
) -> httpx.Request:
    hostname = request.url.host

    if not hostname:
        raise httpx.ConnectError("No hostname in request URL")

    try:
        ips = resolve_hostname_ips(hostname)
    except ValueError as e:
        raise httpx.ConnectError(str(e)) from e

    if not allow_internal:
        for ip_str in ips:
            if not is_public_ip(ipaddress.ip_address(ip_str)):
                raise httpx.ConnectError(
                    f"Connection blocked: {hostname} resolves to a non-public address",
                )

    ip_str = ips[0]
    formatted_ip = format_host_for_url(ip_str)

    new_headers = httpx.Headers(request.headers)
    if "host" in new_headers:
        del new_headers["host"]
    host_header = format_host_for_url(hostname)
    default_port = 443 if request.url.scheme == "https" else 80
    if request.url.port and request.url.port != default_port:
        host_header = f"{host_header}:{request.url.port}"
    new_headers["Host"] = host_header
    new_url = request.url.copy_with(host=formatted_ip)

    rewritten_request = httpx.Request(
        method=request.method,
        url=new_url,
        headers=new_headers,
        stream=request.stream,
        extensions=request.extensions,
    )
    rewritten_request.extensions["sni_hostname"] = hostname

    return rewritten_request


class PinnedHostHTTPTransport(httpx.HTTPTransport):
    """
    HTTP transport that resolves/validates hostnames per request and connects to
    a vetted IP while preserving the original Host header and TLS SNI hostname.
    """

    def __init__(
        self,
        *args,
        allow_internal: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.allow_internal = allow_internal

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request = _rewrite_request_to_pinned_ip(
            request,
            allow_internal=self.allow_internal,
        )
        return super().handle_request(request)


class PinnedHostAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """
    Async variant of PinnedHostHTTPTransport.
    """

    def __init__(
        self,
        *args,
        allow_internal: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.allow_internal = allow_internal

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request = _rewrite_request_to_pinned_ip(
            request,
            allow_internal=self.allow_internal,
        )
        return await super().handle_async_request(request)


def create_pinned_httpx_client(
    url: str,
    *,
    allow_internal: bool = False,
    **kwargs,
) -> httpx.Client:
    validate_outbound_http_url(url, allow_internal=allow_internal)
    return httpx.Client(
        transport=PinnedHostHTTPTransport(allow_internal=allow_internal),
        **kwargs,
    )


def create_pinned_async_httpx_client(
    url: str,
    *,
    allow_internal: bool = False,
    **kwargs,
) -> httpx.AsyncClient:
    validate_outbound_http_url(url, allow_internal=allow_internal)
    return httpx.AsyncClient(
        transport=PinnedHostAsyncHTTPTransport(allow_internal=allow_internal),
        **kwargs,
    )
