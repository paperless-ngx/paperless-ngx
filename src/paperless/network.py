import functools
import ipaddress
import logging
import math
import re
import socket
import time
from collections.abc import Callable
from collections.abc import Collection
from collections.abc import Iterable
from enum import StrEnum
from typing import Any
from typing import Final
from typing import Self
from typing import TypeAlias
from urllib.parse import ParseResult
from urllib.parse import urlparse

import anyio
import httpcore
import httpx

# Not exported by httpcore; the guard asserts it is still the async default.
from httpcore._backends.auto import AutoBackend

logger = logging.getLogger("paperless.network")

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


# Resolver and clock indirection so tests can fake DNS and time for this module
# without changing how the stock httpcore backends resolve the literals the
# guard dials.
_getaddrinfo = socket.getaddrinfo
_agetaddrinfo = anyio.getaddrinfo
_monotonic = time.monotonic


def _parse_ip_literal(host: str) -> IPAddress | None:
    address, zone_sep, _zone = host.partition("%")
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return None
    # Zone ids exist only on IPv6; anything else after "%" is not a literal.
    if zone_sep and parsed.version != 6:
        return None
    return parsed


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


MAX_ADDRESSES_TRIED: Final = 8
MIN_ATTEMPT_TIMEOUT: Final = 2.0
MAX_ATTEMPT_TIMEOUT: Final = 10.0


def _require_positive_timeout(host: str, timeout: float | None) -> None:
    # A zero timeout makes the socket non-blocking and a negative one is
    # rejected by settimeout; neither can produce a useful connection attempt.
    if timeout is not None and timeout <= 0:
        raise httpcore.ConnectTimeout(
            f"Connect timeout for {host} must be positive, got {timeout}",
        )


def _deadline(timeout: float | None) -> float:
    return math.inf if timeout is None else _monotonic() + timeout


def _attempt_order(addresses: tuple[IPAddress, ...]) -> list[IPAddress]:
    # Alternate address families, starting with the resolver's first family
    # (RFC 8305 section 4), so one unreachable family cannot delay the other.
    first_version = addresses[0].version
    primary = [a for a in addresses if a.version == first_version]
    secondary = [a for a in addresses if a.version != first_version]
    ordered: list[IPAddress] = []
    for index in range(max(len(primary), len(secondary))):
        ordered.extend(primary[index : index + 1])
        ordered.extend(secondary[index : index + 1])
    return ordered[:MAX_ADDRESSES_TRIED]


def _attempt_timeout(remaining: float, attempts_left: int) -> float:
    """
    Budget for the next attempt. Once the budget is too small to split, or on
    the last address, the attempt gets everything left. Otherwise it gets an
    equal share clamped to [MIN, MAX], always leaving MIN for a later attempt.
    The floor survives one lost SYN; the ceiling bounds how long a black-holed
    address delays the next one.
    """
    if attempts_left == 1 or remaining < 2 * MIN_ATTEMPT_TIMEOUT:
        return remaining
    share = remaining / attempts_left
    return min(
        MAX_ATTEMPT_TIMEOUT,
        max(MIN_ATTEMPT_TIMEOUT, share),
        remaining - MIN_ATTEMPT_TIMEOUT,
    )


def _as_httpcore_timeout(seconds: float) -> float | None:
    return None if math.isinf(seconds) else seconds


def _log_block(error: OutboundRequestBlockedError) -> None:
    logger.warning("Blocked outbound connection: %s", error)


def _budget_exhausted(host: str, tried: int, total: int) -> httpcore.ConnectTimeout:
    return httpcore.ConnectTimeout(
        f"Timed out connecting to {host} after trying {tried} of {total} addresses",
    )


def _resolve_for_connect(host: str, port: int) -> tuple[IPAddress, ...]:
    try:
        return resolve_public_addresses(host, port)
    except OutboundRequestBlockedError as e:
        _log_block(e)
        raise
    except HostResolutionError as e:
        raise httpcore.ConnectError(str(e)) from e


class _GuardedSyncBackend(httpcore.NetworkBackend):
    """
    Wraps httpcore's sync backend. With internal addresses disallowed, it
    resolves the origin host itself, rejects the name if any address is
    non-public, and dials the validated literals so the checked address is
    the connected one. TLS still verifies against the origin hostname.
    """

    def __init__(self, inner: httpcore.NetworkBackend, *, allow_internal: bool) -> None:
        self._inner = inner
        self._allow_internal = allow_internal

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.NetworkStream:
        if self._allow_internal:
            return self._inner.connect_tcp(
                host,
                port,
                timeout=timeout,
                local_address=local_address,
                socket_options=socket_options,
            )
        _require_positive_timeout(host, timeout)
        # Resolution is not charged to the budget, matching the stock backend.
        candidates = _attempt_order(_resolve_for_connect(host, port))
        deadline = _deadline(timeout)
        last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None = None
        for index, address in enumerate(candidates):
            remaining = deadline - _monotonic()
            if remaining <= 0:
                raise _budget_exhausted(host, index, len(candidates))
            budget = _attempt_timeout(remaining, len(candidates) - index)
            try:
                return self._inner.connect_tcp(
                    str(address),
                    port,
                    timeout=_as_httpcore_timeout(budget),
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as e:
                logger.debug("Connecting to %s via %s failed: %s", host, address, e)
                last_error = e
        # candidates is never empty, so every address was tried and failed
        raise last_error or _budget_exhausted(host, len(candidates), len(candidates))

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.NetworkStream:
        error = OutboundRequestBlockedError(
            host=path,
            port=None,
            reason=BlockReason.UNIX_SOCKET,
        )
        _log_block(error)
        raise error

    def sleep(self, seconds: float) -> None:
        self._inner.sleep(seconds)


class _GuardedAsyncBackend(httpcore.AsyncNetworkBackend):
    """Async twin of _GuardedSyncBackend."""

    def __init__(
        self,
        inner: httpcore.AsyncNetworkBackend,
        *,
        allow_internal: bool,
    ) -> None:
        self._inner = inner
        self._allow_internal = allow_internal

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if self._allow_internal:
            return await self._inner.connect_tcp(
                host,
                port,
                timeout=timeout,
                local_address=local_address,
                socket_options=socket_options,
            )
        _require_positive_timeout(host, timeout)
        # Resolution counts against the budget, matching the stock backend.
        # This scope closes before dialling; attempts are not nested inside it.
        deadline = _deadline(timeout)
        try:
            with anyio.fail_after(timeout):
                addresses = await aresolve_public_addresses(host, port)
        except TimeoutError as e:
            raise httpcore.ConnectTimeout(f"Timed out resolving {host}") from e
        except OutboundRequestBlockedError as e:
            _log_block(e)
            raise
        except HostResolutionError as e:
            raise httpcore.ConnectError(str(e)) from e
        candidates = _attempt_order(addresses)
        last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None = None
        for index, address in enumerate(candidates):
            remaining = deadline - _monotonic()
            if remaining <= 0:
                raise _budget_exhausted(host, index, len(candidates))
            budget = _attempt_timeout(remaining, len(candidates) - index)
            try:
                return await self._inner.connect_tcp(
                    str(address),
                    port,
                    timeout=_as_httpcore_timeout(budget),
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as e:
                logger.debug("Connecting to %s via %s failed: %s", host, address, e)
                last_error = e
        raise last_error or _budget_exhausted(host, len(candidates), len(candidates))

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        error = OutboundRequestBlockedError(
            host=path,
            port=None,
            reason=BlockReason.UNIX_SOCKET,
        )
        _log_block(error)
        raise error

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


_LAYOUT_ERROR = (
    "Unexpected httpx transport layout; refusing to create a transport "
    "without the outbound connection guard"
)


class GuardedHTTPTransport(httpx.HTTPTransport):
    """
    httpx transport whose connections pass through the outbound guard.

    Deliberately accepts no proxy, uds or retries options: a proxy would be
    dialled instead of the destination, and a unix socket bypasses TCP
    entirely. Adding an option here is a reviewed change, not a pass-through.
    """

    def __init__(self, *, allow_internal: bool) -> None:
        super().__init__()
        # httpx has no public hook for the network backend. Check the exact
        # layout before swapping so an httpx or httpcore change fails loudly.
        pool = self._pool
        if (
            type(pool) is not httpcore.ConnectionPool
            or type(pool._network_backend) is not httpcore.SyncBackend
        ):
            raise RuntimeError(_LAYOUT_ERROR)
        pool._network_backend = _GuardedSyncBackend(
            pool._network_backend,
            allow_internal=allow_internal,
        )


class GuardedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """Async twin of GuardedHTTPTransport."""

    def __init__(self, *, allow_internal: bool) -> None:
        super().__init__()
        pool = self._pool
        if (
            type(pool) is not httpcore.AsyncConnectionPool
            or type(pool._network_backend) is not AutoBackend
        ):
            raise RuntimeError(_LAYOUT_ERROR)
        pool._network_backend = _GuardedAsyncBackend(
            pool._network_backend,
            allow_internal=allow_internal,
        )


def create_guarded_httpx_client(
    url: str,
    *,
    allow_internal: bool,
    timeout: float,
) -> httpx.Client:
    """
    Validate ``url`` up front, then build a client that re-checks at connect
    time. The up-front check turns static misconfiguration into a ValueError
    before any retry layer sees it.
    """
    validate_outbound_http_url(url, allow_internal=allow_internal)
    return httpx.Client(
        transport=GuardedHTTPTransport(allow_internal=allow_internal),
        timeout=timeout,
    )


def create_guarded_async_httpx_client(
    url: str,
    *,
    allow_internal: bool,
    timeout: float,
) -> httpx.AsyncClient:
    """Async twin of create_guarded_httpx_client."""
    validate_outbound_http_url(url, allow_internal=allow_internal)
    return httpx.AsyncClient(
        transport=GuardedAsyncHTTPTransport(allow_internal=allow_internal),
        timeout=timeout,
    )


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
        host = _dns_name(url)
        # HTTP clients may percent-decode the host before resolving it, so the
        # checked name could differ from the dialled one. An IPv6 zone id is the
        # only legitimate use, and link-local addresses are non-public anyway.
        if "%" in host:
            raise ValueError("Invalid URL scheme or hostname.")
        try:
            resolve_public_addresses(host, port)
        except (OutboundRequestBlockedError, HostResolutionError) as e:
            raise ValueError(blocked_message(e)) from e

    return parsed
