"""
Real-socket helpers for tests of the outbound connection guard in
paperless.network: a local HTTP server, a per-hostname resolver fake and
spies recording which addresses were actually dialled.

The fixtures wrapping these live in the root conftest.
"""

from __future__ import annotations

import http.server
import socket
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import anyio
import httpcore

from paperless.network import GuardedAsyncHTTPTransport
from paperless.network import GuardedHTTPTransport
from paperless.network import _GuardedAsyncBackend
from paperless.network import _GuardedSyncBackend

if TYPE_CHECKING:
    from collections.abc import Iterator
    from unittest.mock import MagicMock
    from unittest.mock import _Call

    import httpx
    from pytest_mock import MockerFixture

_REAL_GETADDRINFO = socket.getaddrinfo
_REAL_AGETADDRINFO = anyio.getaddrinfo


@dataclass
class ReceivedRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class LocalHTTPServer:
    """State of a threaded HTTP server bound to 127.0.0.1 on an ephemeral port."""

    port: int
    requests: list[ReceivedRequest] = field(default_factory=list)
    connections: int = 0
    redirect_to: str | None = None


class _Handler(http.server.BaseHTTPRequestHandler):
    # HTTP/1.1 keeps connections open, so tests can observe connection reuse.
    # Every response sets Content-Length, which keep-alive requires.
    protocol_version = "HTTP/1.1"

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        # BaseHTTPRequestHandler types server as the base socketserver.BaseServer;
        # narrowing the attribute's declared type is a variance error, so the
        # subclass is recovered here instead of on the class body.
        server = cast("_RecordingHTTPServer", self.server)
        state = server.state
        state.requests.append(
            ReceivedRequest(
                method=self.command,
                path=self.path,
                headers={key.lower(): value for key, value in self.headers.items()},
                body=body,
            ),
        )
        if state.redirect_to is not None:
            self.send_response(302)
            self.send_header("Location", state.redirect_to)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    do_GET = _handle
    do_POST = _handle

    def log_message(self, format: str, *args: Any) -> None:
        return None


class _RecordingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.state = LocalHTTPServer(port=self.socket.getsockname()[1])

    def verify_request(self, request: Any, client_address: Any) -> bool:
        self.state.connections += 1
        return True


@contextmanager
def running_http_server() -> Iterator[LocalHTTPServer]:
    """Serve on 127.0.0.1 in a background thread until the block exits."""
    server = _RecordingHTTPServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _addrinfo(address: str, port: int | None) -> tuple[Any, ...]:
    if ":" in address:
        return (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, port or 0, 0, 0))
    return (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port or 0))


class FakeDNS:
    """
    Answers the guard's resolver hooks for registered names and delegates
    every other name to the real resolver. The stock httpcore backends keep
    using the unpatched socket.getaddrinfo.
    """

    def __init__(self) -> None:
        self._answers: dict[str, list[str]] = {}
        self.lookups: list[str] = []

    def add(self, hostname: str, *addresses: str) -> None:
        self._answers[hostname] = list(addresses)

    def getaddrinfo(
        self,
        host: str,
        port: int | None,
        *args: Any,
        **kwargs: Any,
    ) -> list[tuple[Any, ...]]:
        self.lookups.append(host)
        if host in self._answers:
            return [_addrinfo(address, port) for address in self._answers[host]]
        return list(_REAL_GETADDRINFO(host, port, *args, **kwargs))

    async def agetaddrinfo(
        self,
        host: str,
        port: int | None,
        **kwargs: Any,
    ) -> list[tuple[Any, ...]]:
        self.lookups.append(host)
        if host in self._answers:
            return [_addrinfo(address, port) for address in self._answers[host]]
        return list(await _REAL_AGETADDRINFO(host, port, **kwargs))


def install_fake_dns(mocker: MockerFixture) -> FakeDNS:
    """Patch the guard's resolver hooks with a FakeDNS for the current test."""
    dns = FakeDNS()
    mocker.patch("paperless.network._getaddrinfo", new=dns.getaddrinfo)
    mocker.patch("paperless.network._agetaddrinfo", new=dns.agetaddrinfo)
    return dns


def _dialled_host(call: _Call) -> str:
    # The spy sits on the class, so args[0] is the backend instance.
    if "host" in call.kwargs:
        return str(call.kwargs["host"])
    return str(call.args[1])


@dataclass
class DialRecorder:
    sync_spy: MagicMock
    async_spy: MagicMock

    def hosts(self) -> list[str]:
        calls = [*self.sync_spy.call_args_list, *self.async_spy.call_args_list]
        return [_dialled_host(call) for call in calls]


def install_dial_recorder(mocker: MockerFixture) -> DialRecorder:
    """Spy on the stock backends' connect_tcp for the current test."""
    return DialRecorder(
        sync_spy=mocker.spy(httpcore.SyncBackend, "connect_tcp"),
        async_spy=mocker.spy(httpcore.AnyIOBackend, "connect_tcp"),
    )


def guard_of(
    client: httpx.Client | httpx.AsyncClient,
) -> _GuardedSyncBackend | _GuardedAsyncBackend:
    """Return the guard installed on a client's transport."""
    transport = client._transport
    assert isinstance(transport, GuardedHTTPTransport | GuardedAsyncHTTPTransport)
    backend = transport._pool._network_backend
    assert isinstance(backend, _GuardedSyncBackend | _GuardedAsyncBackend)
    return backend
