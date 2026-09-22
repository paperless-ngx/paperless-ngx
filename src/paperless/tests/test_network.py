import ipaddress
import pickle
import socket
from typing import Any
from unittest import mock
from unittest.mock import MagicMock

import httpx
import pytest
from celery.utils.serialization import get_pickleable_exception
from pytest_mock import MockerFixture

from paperless.network import BlockReason
from paperless.network import HostResolutionError
from paperless.network import OutboundRequestBlockedError
from paperless.network import PinnedHostHTTPTransport
from paperless.network import aresolve_public_addresses
from paperless.network import blocked_message
from paperless.network import is_public_ip
from paperless.network import resolve_public_addresses
from paperless.network import validate_outbound_http_url


def test_pinned_host_transport_blocks_internal_rebinding():
    transport = PinnedHostHTTPTransport(allow_internal=False)
    request = httpx.Request("GET", "http://example.com/test")

    with (
        mock.patch(
            "paperless.network.resolve_hostname_ips",
            return_value=["127.0.0.1"],
        ),
        pytest.raises(httpx.ConnectError, match="non-public address"),
    ):
        transport.handle_request(request)


def test_pinned_host_transport_rewrites_to_vetted_ip():
    transport = PinnedHostHTTPTransport(allow_internal=False)
    request = httpx.Request("GET", "https://example.com:8443/test")

    def assert_rewritten_request(
        self,
        rewritten_request,
    ):
        assert str(rewritten_request.url) == "https://93.184.216.34:8443/test"
        assert rewritten_request.headers["Host"] == "example.com:8443"
        assert rewritten_request.extensions["sni_hostname"] == "example.com"
        return httpx.Response(200, request=rewritten_request)

    with (
        mock.patch(
            "paperless.network.resolve_hostname_ips",
            return_value=["93.184.216.34"],
        ),
        mock.patch.object(
            httpx.HTTPTransport,
            "handle_request",
            autospec=True,
            side_effect=assert_rewritten_request,
        ),
    ):
        response = transport.handle_request(request)

    assert response.status_code == 200


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
    def test_ip_literal_skips_dns(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A public IP literal
        WHEN:
            - It is resolved
        THEN:
            - It is returned without a resolver call
        """
        resolver = _answer(mocker)

        assert resolve_public_addresses("93.184.216.34", 443) == (
            ipaddress.ip_address("93.184.216.34"),
        )
        resolver.assert_not_called()

    def test_private_ip_literal_is_blocked(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A private IP literal
        WHEN:
            - It is resolved
        THEN:
            - It is blocked as a non-public address
        """
        _answer(mocker)

        with pytest.raises(OutboundRequestBlockedError) as exc_info:
            resolve_public_addresses("10.0.0.1", 443)

        assert exc_info.value.reason is BlockReason.NON_PUBLIC_ADDRESS
        assert exc_info.value.address == ipaddress.ip_address("10.0.0.1")

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
