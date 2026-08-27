from unittest import mock

import httpx
import pytest

from paperless.network import PinnedHostHTTPTransport
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


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "169.254.169.254",
        "::1",
        "fc00::1",
        "fe80::1",
        # RFC 6598 shared address space, incl. both edges of the /10
        "100.64.0.0",
        "100.64.0.1",
        "100.127.255.255",
        # RFC 6052 NAT64 well-known prefix, embedding 127.0.0.1 and 10.0.0.5
        "64:ff9b::7f00:1",
        "64:ff9b::a00:5",
    ],
)
def test_is_public_ip_blocks_non_public_addresses(address):
    assert not is_public_ip(address)


@pytest.mark.parametrize(
    "address",
    [
        "8.8.8.8",
        "142.250.185.196",
        "2606:4700:4700::1111",
        # just outside the ranges above, must stay reachable
        "100.63.255.255",
        "100.128.0.0",
        "64:ff9a::1",
        "64:ff9c::1",
    ],
)
def test_is_public_ip_allows_public_addresses(address):
    assert is_public_ip(address)
