import ipaddress
import logging
import pickle
import socket
from collections.abc import Iterable
from typing import Any
from unittest.mock import MagicMock

import anyio
import httpcore
import httpx
import ollama
import pytest
from celery.utils.serialization import get_pickleable_exception
from httpcore._backends.auto import AutoBackend
from pytest_mock import MockerFixture

from paperless.network import MAX_ADDRESSES_TRIED
from paperless.network import BlockReason
from paperless.network import GuardedAsyncHTTPTransport
from paperless.network import GuardedHTTPTransport
from paperless.network import HostResolutionError
from paperless.network import OutboundRequestBlockedError
from paperless.network import _GuardedAsyncBackend
from paperless.network import _GuardedSyncBackend
from paperless.network import aresolve_public_addresses
from paperless.network import blocked_message
from paperless.network import create_guarded_async_httpx_client
from paperless.network import create_guarded_httpx_client
from paperless.network import is_public_ip
from paperless.network import resolve_public_addresses
from paperless.network import validate_outbound_http_url


class TestIsPublicIp:
    @pytest.mark.parametrize(
        "address",
        [
            pytest.param("127.0.0.1", id="ipv4-loopback"),
            pytest.param("10.0.0.5", id="ipv4-private"),
            pytest.param("169.254.169.254", id="ipv4-link-local-metadata"),
            pytest.param("::1", id="ipv6-loopback"),
            pytest.param("fc00::1", id="ipv6-unique-local"),
            pytest.param("fe80::1", id="ipv6-link-local"),
            pytest.param("100.64.0.0", id="cgnat-first"),
            pytest.param("100.127.255.255", id="cgnat-last"),
            pytest.param("64:ff9b::", id="nat64-well-known-first"),
            pytest.param("64:ff9b::7f00:1", id="nat64-wrapping-loopback"),
            pytest.param("64:ff9b::ffff:ffff", id="nat64-well-known-last"),
            pytest.param("224.0.0.1", id="ipv4-multicast"),
            pytest.param("ff02::1", id="ipv6-multicast"),
            pytest.param("0.0.0.0", id="ipv4-unspecified"),
            pytest.param("::", id="ipv6-unspecified"),
            pytest.param("::ffff:127.0.0.1", id="ipv4-mapped-loopback"),
            pytest.param("::ffff:169.254.169.254", id="ipv4-mapped-metadata"),
            pytest.param("::ffff:10.0.0.1", id="ipv4-mapped-private"),
            pytest.param("::ffff:100.64.0.1", id="ipv4-mapped-cgnat"),
        ],
    )
    def test_rejects_non_public_addresses(self, address: str) -> None:
        """
        GIVEN:
            - An address that is internal, multicast, or reaches internal hosts
        WHEN:
            - It is classified
        THEN:
            - It is not public
        """
        assert not is_public_ip(ipaddress.ip_address(address))

    @pytest.mark.parametrize(
        "address",
        [
            pytest.param("8.8.8.8", id="ipv4-public"),
            pytest.param("2606:4700:4700::1111", id="ipv6-public"),
            pytest.param("100.63.255.255", id="below-cgnat"),
            pytest.param("100.128.0.0", id="above-cgnat"),
            pytest.param("64:ff9a:ffff:ffff:ffff:ffff:ffff:ffff", id="below-nat64"),
            pytest.param("64:ff9b::1:0:0", id="above-nat64-well-known"),
        ],
    )
    def test_accepts_public_addresses(self, address: str) -> None:
        """
        GIVEN:
            - A globally routable unicast address outside our extra ranges
        WHEN:
            - It is classified
        THEN:
            - It is public
        """
        assert is_public_ip(ipaddress.ip_address(address))


def _sample_errors() -> list[object]:
    return [
        pytest.param(
            OutboundRequestBlockedError(
                host="example.com",
                port=443,
                reason=BlockReason.NON_PUBLIC_ADDRESS,
                address=ipaddress.ip_address("10.0.0.1"),
            ),
            id="non-public-address",
        ),
        pytest.param(
            OutboundRequestBlockedError(
                host="/run/app.sock",
                port=None,
                reason=BlockReason.UNIX_SOCKET,
            ),
            id="unix-socket",
        ),
        pytest.param(
            HostResolutionError(
                host="missing.example",
                detail="Name or service not known",
            ),
            id="unresolvable",
        ),
    ]


class TestOutboundErrors:
    @pytest.mark.parametrize("error", _sample_errors())
    def test_round_trips_through_pickle(self, error: Exception) -> None:
        """
        GIVEN:
            - An outbound error with keyword-only fields
        WHEN:
            - It is pickled and unpickled
        THEN:
            - Type, fields and message are preserved
        """
        restored = pickle.loads(pickle.dumps(error))

        assert type(restored) is type(error)
        assert vars(restored) == vars(error)
        assert str(restored) == str(error)

    @pytest.mark.parametrize("error", _sample_errors())
    def test_celery_keeps_the_original_exception(self, error: Exception) -> None:
        """
        GIVEN:
            - An outbound error raised from a Celery task
        WHEN:
            - Celery prepares it for failure handling
        THEN:
            - The exception itself is kept, not an unpickleable wrapper
        """
        assert get_pickleable_exception(error) is error

    def test_message_names_the_destination_but_not_the_address(self) -> None:
        """
        GIVEN:
            - A block for a non-public address
        WHEN:
            - The error is rendered
        THEN:
            - Host, port and reason are in the message
            - The resolved internal address is not, so it never reaches logs or
              stored task results
        """
        error = OutboundRequestBlockedError(
            host="example.com",
            port=443,
            reason=BlockReason.NON_PUBLIC_ADDRESS,
            address=ipaddress.ip_address("10.0.0.1"),
        )

        message = str(error)

        assert "example.com:443" in message
        assert "non_public_address" in message
        assert "10.0.0.1" not in message

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            pytest.param(
                OutboundRequestBlockedError(
                    host="internal.example",
                    port=443,
                    reason=BlockReason.NON_PUBLIC_ADDRESS,
                    address=ipaddress.ip_address("10.0.0.1"),
                ),
                "Connection blocked: internal.example resolves to a non-public address",
                id="non-public-address",
            ),
            pytest.param(
                HostResolutionError(host="missing.example", detail="NXDOMAIN"),
                "Could not resolve hostname: missing.example",
                id="unresolvable",
            ),
            pytest.param(
                OutboundRequestBlockedError(
                    host="/run/app.sock",
                    port=None,
                    reason=BlockReason.UNIX_SOCKET,
                ),
                "Connection blocked: unix sockets are not permitted",
                id="unix-socket",
            ),
        ],
    )
    def test_blocked_message(
        self,
        error: OutboundRequestBlockedError | HostResolutionError,
        expected: str,
    ) -> None:
        """
        GIVEN:
            - An outbound error
        WHEN:
            - The user-facing message is requested
        THEN:
            - It matches the established wording
        """
        assert blocked_message(error) == expected


def _addrinfo(
    *addresses: str,
) -> list[tuple[socket.AddressFamily, socket.SocketKind, int, str, tuple[Any, ...]]]:
    return [
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, 443, 0, 0))
        if ":" in address
        else (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
        for address in addresses
    ]


def _answer(mocker: MockerFixture, *addresses: str) -> MagicMock:
    """Make both resolver hooks answer with ``addresses``; returns the sync mock."""
    infos = _addrinfo(*addresses)
    mocker.patch(
        "paperless.network._agetaddrinfo",
        new=mocker.AsyncMock(return_value=infos),
    )
    return mocker.patch("paperless.network._getaddrinfo", return_value=infos)


class TestResolvePublicAddresses:
    def test_ip_literal_is_validated_from_resolver_answer(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A public IP literal, which the resolver answers with itself
        WHEN:
            - It is resolved
        THEN:
            - The literal is passed to the resolver and its answer returned
        """
        resolver = _answer(mocker, "93.184.216.34")

        assert resolve_public_addresses("93.184.216.34", 443) == (
            ipaddress.ip_address("93.184.216.34"),
        )
        resolver.assert_called_once_with("93.184.216.34", 443, type=socket.SOCK_STREAM)

    def test_private_ip_literal_is_blocked_from_resolver_answer(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A private IP literal, which the resolver answers with itself
        WHEN:
            - It is resolved
        THEN:
            - The literal is passed to the resolver and blocked as a
              non-public address
        """
        resolver = _answer(mocker, "10.0.0.1")

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            resolve_public_addresses("10.0.0.1", 443)

        assert exc_info.value.reason is BlockReason.NON_PUBLIC_ADDRESS
        assert exc_info.value.address == ipaddress.ip_address("10.0.0.1")
        resolver.assert_called_once_with("10.0.0.1", 443, type=socket.SOCK_STREAM)

    def test_asks_for_stream_sockets_on_the_port(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A hostname
        WHEN:
            - It is resolved
        THEN:
            - The resolver is asked for TCP stream results for that port
        """
        resolver = _answer(mocker, "93.184.216.34")

        resolve_public_addresses("example.com", 443)

        resolver.assert_called_once_with("example.com", 443, type=socket.SOCK_STREAM)

    def test_deduplicates_preserving_order(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - Resolver results containing a duplicate
        WHEN:
            - They are resolved
        THEN:
            - Each address appears once, in resolver order
        """
        _answer(mocker, "2606:4700::1", "93.184.216.34", "2606:4700::1")

        assert resolve_public_addresses("example.com", 443) == (
            ipaddress.ip_address("2606:4700::1"),
            ipaddress.ip_address("93.184.216.34"),
        )

    def test_strips_zone_ids(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A scoped link-local result
        WHEN:
            - It is resolved
        THEN:
            - The zone id is stripped and the address is blocked
        """
        _answer(mocker, "fe80::1%eth0")

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            resolve_public_addresses("example.com", 443)

        assert exc_info.value.address == ipaddress.ip_address("fe80::1")

    def test_any_non_public_answer_blocks_the_name(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - Resolver results mixing public and private addresses
        WHEN:
            - They are resolved
        THEN:
            - The whole name is blocked, naming the first offending address
        """
        _answer(mocker, "93.184.216.34", "127.0.0.1", "10.0.0.1")

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            resolve_public_addresses("example.com", 443)

        assert exc_info.value.reason is BlockReason.NON_PUBLIC_ADDRESS
        assert exc_info.value.host == "example.com"
        assert exc_info.value.port == 443
        assert exc_info.value.address == ipaddress.ip_address("127.0.0.1")

    @pytest.mark.parametrize(
        "failure",
        [
            pytest.param(
                socket.gaierror(-2, "Name or service not known"),
                id="gaierror",
            ),
            pytest.param(UnicodeError("label too long"), id="invalid-idna"),
        ],
    )
    def test_resolver_failure(self, mocker: MockerFixture, failure: Exception) -> None:
        """
        GIVEN:
            - A resolver that fails
        WHEN:
            - A hostname is resolved
        THEN:
            - HostResolutionError is raised
        """
        mocker.patch("paperless.network._getaddrinfo", side_effect=failure)

        with pytest.raises(HostResolutionError):
            resolve_public_addresses("example.com", 443)

    def test_empty_answer(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A resolver returning no results
        WHEN:
            - A hostname is resolved
        THEN:
            - HostResolutionError is raised
        """
        _answer(mocker)

        with pytest.raises(HostResolutionError):
            resolve_public_addresses("example.com", 443)

    def test_ipv4_with_percent_is_resolved_as_a_name(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A dotted quad followed by "%" and more text
            - A resolver answering with a public address
        WHEN:
            - It is resolved
        THEN:
            - The whole host is passed to the resolver and its answer returned
        """
        resolver = _answer(mocker, "93.184.216.34")

        assert resolve_public_addresses("8.8.8.8%2eexample.test", 443) == (
            ipaddress.ip_address("93.184.216.34"),
        )
        resolver.assert_called_once_with(
            "8.8.8.8%2eexample.test",
            443,
            type=socket.SOCK_STREAM,
        )

    def test_ipv4_with_percent_resolving_privately_is_blocked(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A dotted quad followed by "%" and more text
            - A resolver answering with a private address
        WHEN:
            - It is resolved
        THEN:
            - The name is blocked, not taken as the public address before "%"
        """
        resolver = _answer(mocker, "169.254.169.254")

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            resolve_public_addresses("8.8.8.8%2eexample.test", 443)

        assert exc_info.value.address == ipaddress.ip_address("169.254.169.254")
        resolver.assert_called_once()


class TestAsyncResolvePublicAddresses:
    @pytest.fixture(autouse=True)
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.mark.anyio
    async def test_returns_public_addresses(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - Public resolver results
        WHEN:
            - They are resolved asynchronously
        THEN:
            - The addresses are returned
        """
        _answer(mocker, "93.184.216.34")

        assert await aresolve_public_addresses("example.com", 443) == (
            ipaddress.ip_address("93.184.216.34"),
        )

    @pytest.mark.anyio
    async def test_blocks_non_public(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A private resolver result
        WHEN:
            - It is resolved asynchronously
        THEN:
            - It is blocked
        """
        _answer(mocker, "10.0.0.1")

        with pytest.raises(OutboundRequestBlockedError):
            await aresolve_public_addresses("example.com", 443)

    @pytest.mark.anyio
    async def test_ipv4_with_percent_is_resolved_as_a_name(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A dotted quad followed by "%" and more text
            - An async resolver answering with a public address
        WHEN:
            - It is resolved asynchronously
        THEN:
            - The whole host is passed to the resolver and its answer returned
        """
        resolver = mocker.patch(
            "paperless.network._agetaddrinfo",
            new=mocker.AsyncMock(return_value=_addrinfo("93.184.216.34")),
        )

        assert await aresolve_public_addresses("8.8.8.8%2eexample.test", 443) == (
            ipaddress.ip_address("93.184.216.34"),
        )
        resolver.assert_awaited_once_with(
            "8.8.8.8%2eexample.test",
            443,
            type=socket.SOCK_STREAM,
        )

    @pytest.mark.anyio
    async def test_ipv4_with_percent_resolving_privately_is_blocked(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A dotted quad followed by "%" and more text
            - An async resolver answering with a private address
        WHEN:
            - It is resolved asynchronously
        THEN:
            - The name is blocked, not taken as the public address before "%"
        """
        resolver = mocker.patch(
            "paperless.network._agetaddrinfo",
            new=mocker.AsyncMock(return_value=_addrinfo("169.254.169.254")),
        )

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            await aresolve_public_addresses("8.8.8.8%2eexample.test", 443)

        assert exc_info.value.address == ipaddress.ip_address("169.254.169.254")
        resolver.assert_awaited_once()

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "failure",
        [
            pytest.param(
                socket.gaierror(-2, "Name or service not known"),
                id="gaierror",
            ),
            pytest.param(UnicodeError("label too long"), id="invalid-idna"),
        ],
    )
    async def test_resolver_failure(
        self,
        mocker: MockerFixture,
        failure: Exception,
    ) -> None:
        """
        GIVEN:
            - An async resolver that fails
        WHEN:
            - A hostname is resolved
        THEN:
            - HostResolutionError is raised
        """
        mocker.patch(
            "paperless.network._agetaddrinfo",
            new=mocker.AsyncMock(side_effect=failure),
        )

        with pytest.raises(HostResolutionError):
            await aresolve_public_addresses("example.com", 443)


class TestValidateOutboundHttpUrl:
    @pytest.mark.parametrize(
        ("answers", "expected"),
        [
            pytest.param(
                ["10.0.0.1"],
                "Connection blocked: internal.example resolves to a non-public address",
                id="non-public",
            ),
            pytest.param(
                [],
                "Could not resolve hostname: internal.example",
                id="unresolvable",
            ),
        ],
    )
    def test_messages(
        self,
        mocker: MockerFixture,
        answers: list[str],
        expected: str,
    ) -> None:
        """
        GIVEN:
            - A hostname that resolves to a private address, or to nothing
        WHEN:
            - The URL is validated with internal addresses disallowed
        THEN:
            - ValueError carries the established message
        """
        _answer(mocker, *answers)

        with pytest.raises(ValueError, match=expected):
            validate_outbound_http_url(
                "https://internal.example/v1",
                allow_internal=False,
            )

    def test_allow_internal_skips_dns(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - Internal addresses allowed
        WHEN:
            - A URL is validated
        THEN:
            - No resolver call is made
        """
        resolver = _answer(mocker, "10.0.0.1")

        validate_outbound_http_url("https://internal.example/v1", allow_internal=True)

        resolver.assert_not_called()

    def test_resolves_the_name_http_clients_connect_to(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A hostname containing a character that IDNA 2003 and IDNA 2008
              encode differently ("fass" versus "xn--fa-hia")
            - The IDNA 2003 name resolves to a public address and the IDNA 2008
              name, which httpx and urllib3 connect to, to a private one
        WHEN:
            - The URL is validated with internal addresses disallowed
        THEN:
            - The IDNA 2008 name is the one checked, so the URL is blocked
        """
        answers = {
            "fass.example": _addrinfo("93.184.216.34"),
            "xn--fa-hia.example": _addrinfo("10.0.0.1"),
        }
        resolver = mocker.patch(
            "paperless.network._getaddrinfo",
            side_effect=lambda host, *args, **kwargs: answers[host],
        )

        with pytest.raises(ValueError, match="resolves to a non-public address"):
            validate_outbound_http_url(
                "https://fa\u00df.example/v1",
                allow_internal=False,
            )

        resolver.assert_called_once_with(
            "xn--fa-hia.example",
            443,
            type=socket.SOCK_STREAM,
        )

    def test_hostname_invalid_for_http_clients_is_rejected(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A hostname that has no valid IDNA 2008 encoding
        WHEN:
            - The URL is validated with internal addresses disallowed
        THEN:
            - It is rejected as invalid without a resolver call
        """
        resolver = _answer(mocker, "93.184.216.34")

        with pytest.raises(ValueError, match="Invalid URL scheme or hostname"):
            validate_outbound_http_url(
                "https://bad\u2764host.example/v1",
                allow_internal=False,
            )

        resolver.assert_not_called()

    @pytest.mark.parametrize(
        "url",
        [
            pytest.param(r"http://127.0.0.1\@evil.example/", id="backslash"),
            pytest.param(
                r"http://127.0.0.1:80\@evil.example/",
                id="backslash-with-port",
            ),
            pytest.param("http://evil\t.example/", id="tab-in-host"),
            pytest.param("http://evil .example/", id="space-in-host"),
        ],
    )
    def test_rejects_urls_http_clients_may_parse_differently(
        self,
        mocker: MockerFixture,
        url: str,
    ) -> None:
        """
        GIVEN:
            - A URL containing a backslash, control or whitespace character,
              which urllib3 may split into a different host than urlparse and
              httpx do
            - A resolver that would answer with a public address
        WHEN:
            - The URL is validated with internal addresses disallowed
        THEN:
            - It is rejected as invalid without a resolver call
        """
        resolver = _answer(mocker, "93.184.216.34")

        with pytest.raises(ValueError, match="Invalid URL scheme or hostname"):
            validate_outbound_http_url(url, allow_internal=False)

        resolver.assert_not_called()

    def test_allow_internal_does_not_reject_backslash(self) -> None:
        """
        GIVEN:
            - A URL containing a backslash
        WHEN:
            - The URL is validated with internal addresses allowed
        THEN:
            - It is not rejected, since no host check is made
        """
        validate_outbound_http_url(
            r"http://127.0.0.1\@evil.example/",
            allow_internal=True,
        )

    @pytest.mark.parametrize(
        "url",
        [
            pytest.param(
                "https://8.8.8.8%2e169-254-169-254.sslip.io/",
                id="dotted-quad-then-wildcard-dns",
            ),
            pytest.param(
                "https://8.8.8.8%2elocalhost/",
                id="dotted-quad-then-localhost",
            ),
        ],
    )
    def test_rejects_percent_in_host(self, mocker: MockerFixture, url: str) -> None:
        """
        GIVEN:
            - A host containing a percent-escape, which requests decodes before
              resolving while httpx does not
            - A resolver that would answer with a public address
        WHEN:
            - The URL is validated with internal addresses disallowed
        THEN:
            - It is rejected as invalid without a resolver call
        """
        resolver = _answer(mocker, "93.184.216.34")

        with pytest.raises(ValueError, match="Invalid URL scheme or hostname"):
            validate_outbound_http_url(url, allow_internal=False)

        resolver.assert_not_called()

    @pytest.mark.parametrize(
        "url",
        [
            pytest.param(
                "https://8.8.8.8%2e169-254-169-254.sslip.io/",
                id="dotted-quad-then-wildcard-dns",
            ),
            pytest.param(
                "https://8.8.8.8%2elocalhost/",
                id="dotted-quad-then-localhost",
            ),
        ],
    )
    def test_allow_internal_does_not_reject_percent_in_host(self, url: str) -> None:
        """
        GIVEN:
            - A host containing a percent-escape
        WHEN:
            - The URL is validated with internal addresses allowed
        THEN:
            - It is not rejected, since no host check is made
        """
        validate_outbound_http_url(url, allow_internal=True)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(mocker: MockerFixture) -> FakeClock:
    fake = FakeClock()
    mocker.patch("paperless.network._monotonic", new=fake)
    return fake


class ScriptedBackend(httpcore.NetworkBackend):
    """
    Inner backend double. Each host either connects (default), refuses
    immediately, or black-holes (uses its whole timeout, then times out).
    """

    def __init__(self, clock: FakeClock, outcomes: dict[str, str]) -> None:
        self.clock = clock
        self.outcomes = outcomes
        self.calls: list[tuple[str, float | None]] = []
        self.slept: list[float] = []

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.NetworkStream:
        self.calls.append((host, timeout))
        outcome = self.outcomes.get(host, "connect")
        if outcome == "refuse":
            raise httpcore.ConnectError(f"refused {host}")
        if outcome == "blackhole":
            self.clock.advance(timeout or 0.0)
            raise httpcore.ConnectTimeout(f"timed out {host}")
        return httpcore.MockStream([])

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


class AsyncScriptedBackend(httpcore.AsyncNetworkBackend):
    """Async twin of ScriptedBackend."""

    def __init__(self, clock: FakeClock, outcomes: dict[str, str]) -> None:
        self.clock = clock
        self.outcomes = outcomes
        self.calls: list[tuple[str, float | None]] = []
        self.slept: list[float] = []

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        self.calls.append((host, timeout))
        outcome = self.outcomes.get(host, "connect")
        if outcome == "refuse":
            raise httpcore.ConnectError(f"refused {host}")
        if outcome == "blackhole":
            self.clock.advance(timeout or 0.0)
            raise httpcore.ConnectTimeout(f"timed out {host}")
        return httpcore.AsyncMockStream([])

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


def _public_ipv4(count: int) -> list[str]:
    return [f"93.184.216.{index + 1}" for index in range(count)]


_ATTEMPT_BUDGETS = [
    pytest.param(5.0, 2, [2.5, 2.5], id="5s-2-addresses"),
    pytest.param(5.0, 3, [2.0, 3.0], id="5s-3-addresses"),
    pytest.param(5.0, 8, [2.0, 3.0], id="5s-8-addresses"),
    pytest.param(1.0, 2, [1.0], id="1s-2-addresses"),
    pytest.param(120.0, 8, [10.0] * 7 + [50.0], id="120s-8-addresses"),
    pytest.param(None, 3, [10.0, 10.0, None], id="no-timeout-3-addresses"),
]


class TestGuardedSyncBackend:
    def test_dials_validated_literals_in_order(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A hostname whose first address refuses and second accepts
        WHEN:
            - The guard connects
        THEN:
            - It dials the IP literals in turn, never the hostname
        """
        _answer(mocker, "93.184.216.1", "93.184.216.2")
        inner = ScriptedBackend(clock, {"93.184.216.1": "refuse"})
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        guard.connect_tcp("example.com", 443, timeout=5.0)

        assert [host for host, _ in inner.calls] == ["93.184.216.1", "93.184.216.2"]

    @pytest.mark.parametrize(
        ("answers", "expected"),
        [
            pytest.param(
                ["2606:4700::1", "2606:4700::2", "93.184.216.1", "93.184.216.2"],
                ["2606:4700::1", "93.184.216.1", "2606:4700::2", "93.184.216.2"],
                id="balanced",
            ),
            pytest.param(
                ["2606:4700::1", "2606:4700::2", "2606:4700::3", "93.184.216.1"],
                ["2606:4700::1", "93.184.216.1", "2606:4700::2", "2606:4700::3"],
                id="one-family-runs-out",
            ),
            pytest.param(
                ["93.184.216.1", "93.184.216.2"],
                ["93.184.216.1", "93.184.216.2"],
                id="single-family",
            ),
        ],
    )
    def test_interleaves_address_families(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
        answers: list[str],
        expected: list[str],
    ) -> None:
        """
        GIVEN:
            - Resolver results grouped by address family
        WHEN:
            - Every address refuses
        THEN:
            - Families are alternated, starting with the first result's family
        """
        _answer(mocker, *answers)
        inner = ScriptedBackend(clock, dict.fromkeys(answers, "refuse"))
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectError):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert [host for host, _ in inner.calls] == expected

    @pytest.mark.parametrize(("timeout", "count", "expected"), _ATTEMPT_BUDGETS)
    def test_attempt_budgets(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
        timeout: float | None,
        count: int,
        expected: list[float | None],
    ) -> None:
        """
        GIVEN:
            - Every resolved address black-holed
        WHEN:
            - The guard connects with a given timeout
        THEN:
            - Each attempt gets the budget the connect-time policy prescribes
        """
        addresses = _public_ipv4(count)
        _answer(mocker, *addresses)
        inner = ScriptedBackend(clock, dict.fromkeys(addresses, "blackhole"))
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectTimeout):
            guard.connect_tcp("example.com", 443, timeout=timeout)

        assert [budget for _, budget in inner.calls] == expected

    def test_quick_refusal_leaves_budget_for_next_address(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A 1 second budget, a refusing first address and a working second
        WHEN:
            - The guard connects
        THEN:
            - Both addresses are tried and the connection succeeds
        """
        _answer(mocker, "93.184.216.1", "93.184.216.2")
        inner = ScriptedBackend(clock, {"93.184.216.1": "refuse"})
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        guard.connect_tcp("example.com", 443, timeout=1.0)

        assert inner.calls == [("93.184.216.1", 1.0), ("93.184.216.2", 1.0)]

    def test_resolution_time_is_not_charged(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A resolver that takes 4 seconds against a 5 second timeout
        WHEN:
            - The guard connects to two black-holed addresses
        THEN:
            - The attempts share the full 5 seconds
        """
        infos = _addrinfo("93.184.216.1", "93.184.216.2")

        def slow_resolver(*_args: object, **_kwargs: object) -> list[tuple[Any, ...]]:
            clock.advance(4.0)
            return infos

        mocker.patch("paperless.network._getaddrinfo", side_effect=slow_resolver)
        inner = ScriptedBackend(
            clock,
            {"93.184.216.1": "blackhole", "93.184.216.2": "blackhole"},
        )
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectTimeout):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert [budget for _, budget in inner.calls] == [2.5, 2.5]

    @pytest.mark.parametrize(
        "timeout",
        [pytest.param(0.0, id="zero"), pytest.param(-1.0, id="negative")],
    )
    def test_non_positive_timeout(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
        timeout: float,
    ) -> None:
        """
        GIVEN:
            - A zero or negative connect timeout
        WHEN:
            - The guard connects
        THEN:
            - It times out without resolving or dialling
        """
        resolver = _answer(mocker, "93.184.216.1")
        inner = ScriptedBackend(clock, {})
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectTimeout):
            guard.connect_tcp("example.com", 443, timeout=timeout)

        resolver.assert_not_called()
        assert inner.calls == []

    def test_caps_attempts(self, mocker: MockerFixture, clock: FakeClock) -> None:
        """
        GIVEN:
            - More public addresses than the attempt cap, all refusing
        WHEN:
            - The guard connects
        THEN:
            - Only the capped number of addresses is dialled
        """
        addresses = _public_ipv4(MAX_ADDRESSES_TRIED + 2)
        _answer(mocker, *addresses)
        inner = ScriptedBackend(clock, dict.fromkeys(addresses, "refuse"))
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectError):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert len(inner.calls) == MAX_ADDRESSES_TRIED

    def test_private_address_beyond_cap_still_blocks(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A private address after more public addresses than the cap
        WHEN:
            - The guard connects
        THEN:
            - The name is blocked and nothing is dialled
        """
        _answer(mocker, *_public_ipv4(MAX_ADDRESSES_TRIED), "10.0.0.1")
        inner = ScriptedBackend(clock, {})
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        with pytest.raises(OutboundRequestBlockedError):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert inner.calls == []

    def test_block_is_logged(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A hostname resolving to a private address
        WHEN:
            - The guard connects
        THEN:
            - A warning names the destination and the reason
            - The resolved internal address is not logged
        """
        _answer(mocker, "10.0.0.1")
        guard = _GuardedSyncBackend(ScriptedBackend(clock, {}), allow_internal=False)

        with (
            caplog.at_level(logging.DEBUG, logger="paperless.network"),
            pytest.raises(OutboundRequestBlockedError),
        ):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert "example.com:443" in caplog.text
        assert "non_public_address" in caplog.text
        assert "10.0.0.1" not in caplog.text

    def test_resolves_again_for_every_connection(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A hostname that resolves to a public address, then to a private
              one (DNS rebinding)
        WHEN:
            - The guard opens two connections to it
        THEN:
            - The first connects to the public address
            - The second is blocked and nothing more is dialled
        """
        mocker.patch(
            "paperless.network._getaddrinfo",
            side_effect=[_addrinfo("93.184.216.34"), _addrinfo("10.0.0.1")],
        )
        inner = ScriptedBackend(clock, {})
        guard = _GuardedSyncBackend(inner, allow_internal=False)

        guard.connect_tcp("example.com", 443, timeout=5.0)
        with pytest.raises(OutboundRequestBlockedError):
            guard.connect_tcp("example.com", 443, timeout=5.0)

        assert [host for host, _ in inner.calls] == ["93.184.216.34"]

    def test_resolution_failure_is_a_connect_error(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A resolver that fails
        WHEN:
            - The guard connects
        THEN:
            - A connect error is raised, not a policy block
        """
        mocker.patch(
            "paperless.network._getaddrinfo",
            side_effect=socket.gaierror(-2, "Name or service not known"),
        )
        guard = _GuardedSyncBackend(ScriptedBackend(clock, {}), allow_internal=False)

        with pytest.raises(
            httpcore.ConnectError,
            match=r"Could not resolve example\.com",
        ):
            guard.connect_tcp("example.com", 443, timeout=5.0)

    def test_allow_internal_passes_hostname_through(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - Internal addresses allowed
        WHEN:
            - The guard connects
        THEN:
            - The inner backend gets the hostname and no resolution happens
        """
        resolver = _answer(mocker, "10.0.0.1")
        inner = ScriptedBackend(clock, {})
        guard = _GuardedSyncBackend(inner, allow_internal=True)

        guard.connect_tcp("localhost", 8080, timeout=5.0)

        assert inner.calls == [("localhost", 5.0)]
        resolver.assert_not_called()

    def test_unix_sockets_are_refused(self, clock: FakeClock) -> None:
        """
        GIVEN:
            - A guard
        WHEN:
            - A unix socket connection is requested
        THEN:
            - It is blocked with the unix socket reason
        """
        guard = _GuardedSyncBackend(ScriptedBackend(clock, {}), allow_internal=True)

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            guard.connect_unix_socket("/run/app.sock")

        assert exc_info.value.reason is BlockReason.UNIX_SOCKET
        assert exc_info.value.host == "/run/app.sock"

    def test_sleep_delegates(self, clock: FakeClock) -> None:
        """
        GIVEN:
            - A guard
        WHEN:
            - httpcore asks it to sleep between retries
        THEN:
            - The inner backend sleeps
        """
        inner = ScriptedBackend(clock, {})

        _GuardedSyncBackend(inner, allow_internal=False).sleep(0.5)

        assert inner.slept == [0.5]


class TestGuardedAsyncBackend:
    @pytest.fixture(autouse=True)
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.mark.anyio
    async def test_falls_back_to_next_address(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A refusing first address and a working second
        WHEN:
            - The async guard connects
        THEN:
            - Both literals are dialled in order
        """
        _answer(mocker, "2606:4700::1", "93.184.216.1")
        inner = AsyncScriptedBackend(clock, {"2606:4700::1": "refuse"})
        guard = _GuardedAsyncBackend(inner, allow_internal=False)

        await guard.connect_tcp("example.com", 443, timeout=5.0)

        assert [host for host, _ in inner.calls] == ["2606:4700::1", "93.184.216.1"]

    @pytest.mark.anyio
    @pytest.mark.parametrize(("timeout", "count", "expected"), _ATTEMPT_BUDGETS)
    async def test_attempt_budgets(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
        timeout: float | None,
        count: int,
        expected: list[float | None],
    ) -> None:
        """
        GIVEN:
            - Every resolved address black-holed
        WHEN:
            - The async guard connects with a given timeout
        THEN:
            - Each attempt gets the prescribed budget
        """
        addresses = _public_ipv4(count)
        _answer(mocker, *addresses)
        inner = AsyncScriptedBackend(clock, dict.fromkeys(addresses, "blackhole"))
        guard = _GuardedAsyncBackend(inner, allow_internal=False)

        with pytest.raises(httpcore.ConnectTimeout):
            await guard.connect_tcp("example.com", 443, timeout=timeout)

        assert [budget for _, budget in inner.calls] == expected

    @pytest.mark.anyio
    async def test_blocks_non_public(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - A hostname resolving to a private address
        WHEN:
            - The async guard connects
        THEN:
            - It is blocked and nothing is dialled
        """
        _answer(mocker, "10.0.0.1")
        inner = AsyncScriptedBackend(clock, {})
        guard = _GuardedAsyncBackend(inner, allow_internal=False)

        with pytest.raises(OutboundRequestBlockedError):
            await guard.connect_tcp("example.com", 443, timeout=5.0)

        assert inner.calls == []

    @pytest.mark.anyio
    async def test_slow_resolution_times_out(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A resolver slower than the connect timeout
        WHEN:
            - The async guard connects
        THEN:
            - It raises a connect timeout (real time: fail_after follows the
              event loop clock)
        """

        async def slow_resolver(
            *_args: object,
            **_kwargs: object,
        ) -> list[tuple[Any, ...]]:
            await anyio.sleep(0.2)
            return _addrinfo("93.184.216.1")

        mocker.patch("paperless.network._agetaddrinfo", new=slow_resolver)
        guard = _GuardedAsyncBackend(
            AsyncScriptedBackend(FakeClock(), {}),
            allow_internal=False,
        )

        with pytest.raises(httpcore.ConnectTimeout, match="Timed out resolving"):
            await guard.connect_tcp("example.com", 443, timeout=0.05)

    @pytest.mark.anyio
    async def test_resolution_failure_is_a_connect_error(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - An async resolver that fails
        WHEN:
            - The async guard connects
        THEN:
            - A connect error is raised, not a policy block
        """
        mocker.patch(
            "paperless.network._agetaddrinfo",
            new=mocker.AsyncMock(
                side_effect=socket.gaierror(-2, "Name or service not known"),
            ),
        )
        guard = _GuardedAsyncBackend(
            AsyncScriptedBackend(clock, {}),
            allow_internal=False,
        )

        with pytest.raises(
            httpcore.ConnectError,
            match=r"Could not resolve example\.com",
        ):
            await guard.connect_tcp("example.com", 443, timeout=5.0)

    @pytest.mark.anyio
    async def test_allow_internal_passes_hostname_through(
        self,
        mocker: MockerFixture,
        clock: FakeClock,
    ) -> None:
        """
        GIVEN:
            - Internal addresses allowed
        WHEN:
            - The async guard connects
        THEN:
            - The inner backend gets the hostname and no resolution happens
        """
        _answer(mocker, "10.0.0.1")
        inner = AsyncScriptedBackend(clock, {})
        guard = _GuardedAsyncBackend(inner, allow_internal=True)

        await guard.connect_tcp("localhost", 8080, timeout=5.0)

        assert inner.calls == [("localhost", 5.0)]

    @pytest.mark.anyio
    async def test_unix_sockets_are_refused(self, clock: FakeClock) -> None:
        """
        GIVEN:
            - An async guard
        WHEN:
            - A unix socket connection is requested
        THEN:
            - It is blocked with the unix socket reason
        """
        guard = _GuardedAsyncBackend(
            AsyncScriptedBackend(clock, {}),
            allow_internal=True,
        )

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            await guard.connect_unix_socket("/run/app.sock")

        assert exc_info.value.reason is BlockReason.UNIX_SOCKET

    @pytest.mark.anyio
    async def test_sleep_delegates(self, clock: FakeClock) -> None:
        """
        GIVEN:
            - An async guard
        WHEN:
            - httpcore asks it to sleep between retries
        THEN:
            - The inner backend sleeps
        """
        inner = AsyncScriptedBackend(clock, {})

        await _GuardedAsyncBackend(inner, allow_internal=False).sleep(0.5)

        assert inner.slept == [0.5]


class TestGuardedTransports:
    def test_sync_transport_installs_guard(self) -> None:
        """
        GIVEN:
            - A guarded sync transport
        WHEN:
            - It is constructed
        THEN:
            - The httpcore pool dials through the guard wrapping the stock backend
        """
        transport = GuardedHTTPTransport(allow_internal=False)

        assert type(transport._pool) is httpcore.ConnectionPool
        backend = transport._pool._network_backend
        assert isinstance(backend, _GuardedSyncBackend)
        assert type(backend._inner) is httpcore.SyncBackend
        assert backend._allow_internal is False

    def test_async_transport_installs_guard(self) -> None:
        """
        GIVEN:
            - A guarded async transport
        WHEN:
            - It is constructed
        THEN:
            - The httpcore pool dials through the guard wrapping the stock backend
        """
        transport = GuardedAsyncHTTPTransport(allow_internal=True)

        assert type(transport._pool) is httpcore.AsyncConnectionPool
        backend = transport._pool._network_backend
        assert isinstance(backend, _GuardedAsyncBackend)
        assert type(backend._inner) is AutoBackend
        assert backend._allow_internal is True

    def test_sync_transport_refuses_unexpected_layout(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An httpcore whose default sync backend is not the expected type
        WHEN:
            - A guarded transport is constructed
        THEN:
            - Construction fails instead of producing an unguarded transport
        """
        mocker.patch.object(httpcore, "SyncBackend", type("OtherBackend", (), {}))

        with pytest.raises(RuntimeError, match="transport layout"):
            GuardedHTTPTransport(allow_internal=False)

    def test_async_transport_refuses_unexpected_layout(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An httpcore whose default async backend is not the expected type
        WHEN:
            - A guarded async transport is constructed
        THEN:
            - Construction fails instead of producing an unguarded transport
        """
        mocker.patch("paperless.network.AutoBackend", type("OtherBackend", (), {}))

        with pytest.raises(RuntimeError, match="transport layout"):
            GuardedAsyncHTTPTransport(allow_internal=False)

    def test_factory_validates_url_first(self) -> None:
        """
        GIVEN:
            - An internal endpoint with internal addresses disallowed
        WHEN:
            - A guarded client is requested
        THEN:
            - The up-front check raises ValueError
        """
        with pytest.raises(ValueError, match="non-public address"):
            create_guarded_httpx_client(
                "http://127.0.0.1:8080",
                allow_internal=False,
                timeout=5.0,
            )

    def test_factory_builds_guarded_clients(self) -> None:
        """
        GIVEN:
            - A public endpoint
        WHEN:
            - Sync and async guarded clients are requested
        THEN:
            - Both use guarded transports and the requested timeout
        """
        with create_guarded_httpx_client(
            "http://93.184.216.34",
            allow_internal=False,
            timeout=5.0,
        ) as client:
            assert isinstance(client._transport, GuardedHTTPTransport)
            assert client.timeout == httpx.Timeout(5.0)

        async_client = create_guarded_async_httpx_client(
            "http://93.184.216.34",
            allow_internal=False,
            timeout=5.0,
        )
        assert isinstance(async_client._transport, GuardedAsyncHTTPTransport)
        assert async_client.timeout == httpx.Timeout(5.0)

    def test_environment_proxies_are_ignored(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        GIVEN:
            - HTTP_PROXY and HTTPS_PROXY set in the environment
        WHEN:
            - A guarded client is built, directly or inside ollama.Client
        THEN:
            - No proxy transport is mounted, so requests go through the guard
        """
        monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:3128")
        monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")

        with create_guarded_httpx_client(
            "http://93.184.216.34",
            allow_internal=False,
            timeout=5.0,
        ) as client:
            assert client._mounts == {}

        ollama_client = ollama.Client(
            host="http://93.184.216.34:11434",
            transport=GuardedHTTPTransport(allow_internal=False),
        )
        assert ollama_client._client._mounts == {}
