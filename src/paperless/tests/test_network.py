import ipaddress
import pickle
from unittest import mock

import httpx
import pytest
from celery.utils.serialization import get_pickleable_exception

from paperless.network import BlockReason
from paperless.network import HostResolutionError
from paperless.network import OutboundRequestBlockedError
from paperless.network import PinnedHostHTTPTransport
from paperless.network import blocked_message
from paperless.network import is_public_ip


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
