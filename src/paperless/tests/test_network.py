import socket
from unittest.mock import Mock

import pytest

import paperless.network as network


class TestIsPublicIp:
    @pytest.mark.parametrize(
        "ip",
        [
            pytest.param("8.8.8.8", id="public-ipv4"),
            pytest.param(134744072, id="public-ipv4-int"),
            pytest.param("2001:4860:4860::8888", id="public-ipv6"),
        ],
    )
    def test_identifies_publicly_routable_addresses(self, ip: str | int) -> None:
        assert network.is_public_ip(ip) is True

    @pytest.mark.parametrize(
        "ip",
        [
            pytest.param("10.0.0.1", id="private-ipv4"),
            pytest.param("127.0.0.1", id="loopback-ipv4"),
            pytest.param(2130706433, id="loopback-ipv4-int"),
            pytest.param("169.254.1.1", id="link-local-ipv4"),
            pytest.param("224.0.0.1", id="multicast-ipv4"),
            pytest.param("0.0.0.0", id="unspecified-ipv4"),
            pytest.param("not-an-ip", id="malformed"),
        ],
    )
    def test_rejects_non_public_addresses(self, ip: str | int) -> None:
        assert network.is_public_ip(ip) is False


class TestResolveHostnameIps:
    def test_returns_all_resolved_socket_addresses(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            network.socket,
            "getaddrinfo",
            Mock(
                return_value=[
                    (
                        socket.AF_INET,
                        socket.SOCK_STREAM,
                        6,
                        "",
                        ("93.184.216.34", 0),
                    ),
                    (
                        socket.AF_INET6,
                        socket.SOCK_STREAM,
                        6,
                        "",
                        ("2606:2800:220:1:248:1893:25c8:1946", 0, 0, 0),
                    ),
                ],
            ),
        )

        assert network.resolve_hostname_ips("example.com") == [
            "93.184.216.34",
            "2606:2800:220:1:248:1893:25c8:1946",
        ]

    def test_raises_value_error_when_dns_lookup_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            network.socket,
            "getaddrinfo",
            Mock(side_effect=socket.gaierror),
        )

        with pytest.raises(
            ValueError,
            match="Could not resolve hostname: missing.example",
        ) as exc_info:
            network.resolve_hostname_ips("missing.example")

        assert isinstance(exc_info.value.__cause__, socket.gaierror)

    def test_raises_value_error_when_lookup_returns_no_addresses(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            network.socket,
            "getaddrinfo",
            Mock(return_value=[()]),
        )

        with pytest.raises(
            ValueError,
            match="Could not resolve hostname: empty.example",
        ):
            network.resolve_hostname_ips("empty.example")


class TestFormatHostForUrl:
    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            pytest.param("8.8.8.8", "8.8.8.8", id="ipv4"),
            pytest.param("2001:db8::1", "[2001:db8::1]", id="ipv6"),
            pytest.param("example.com", "example.com", id="hostname"),
        ],
    )
    def test_wraps_only_ipv6_hosts(self, host: str, expected: str) -> None:
        assert network.format_host_for_url(host) == expected


class TestValidateOutboundHttpUrl:
    def test_returns_parsed_url_after_public_dns_validation(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_resolve = Mock(return_value=["8.8.8.8"])
        monkeypatch.setattr(network, "resolve_hostname_ips", mock_resolve)

        parsed = network.validate_outbound_http_url(
            "https://example.com/documents?tag=paid",
        )

        assert parsed.scheme == "https"
        assert parsed.hostname == "example.com"
        assert parsed.path == "/documents"
        assert parsed.query == "tag=paid"
        mock_resolve.assert_called_once_with("example.com")

    def test_allow_internal_skips_dns_public_ip_validation(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_resolve = Mock()
        monkeypatch.setattr(network, "resolve_hostname_ips", mock_resolve)

        parsed = network.validate_outbound_http_url(
            "http://localhost:11434",
            allow_internal=True,
        )

        assert parsed.hostname == "localhost"
        mock_resolve.assert_not_called()

    @pytest.mark.parametrize(
        "url",
        [
            pytest.param("ftp://example.com/resource", id="unsupported-scheme"),
            pytest.param("https:///missing-host", id="missing-hostname"),
            pytest.param("http://example.com:notaport", id="invalid-port"),
        ],
    )
    def test_rejects_invalid_scheme_hostname_or_port(self, url: str) -> None:
        with pytest.raises(ValueError, match="Invalid URL scheme or hostname."):
            network.validate_outbound_http_url(url)

    def test_rejects_disallowed_destination_port(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_resolve = Mock()
        monkeypatch.setattr(network, "resolve_hostname_ips", mock_resolve)

        with pytest.raises(ValueError, match="Destination port not permitted."):
            network.validate_outbound_http_url(
                "https://example.com:8443",
                allowed_ports={443},
            )

        mock_resolve.assert_not_called()

    def test_uses_default_scheme_port_for_allowed_port_check(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_resolve = Mock(return_value=["8.8.8.8"])
        monkeypatch.setattr(network, "resolve_hostname_ips", mock_resolve)

        parsed = network.validate_outbound_http_url(
            "https://example.com/resource",
            allowed_ports={443},
        )

        assert parsed.hostname == "example.com"
        mock_resolve.assert_called_once_with("example.com")

    def test_blocks_hostname_if_any_resolved_address_is_non_public(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            network,
            "resolve_hostname_ips",
            Mock(return_value=["8.8.8.8", "127.0.0.1"]),
        )

        with pytest.raises(ValueError, match="resolves to a non-public address"):
            network.validate_outbound_http_url("https://example.com/webhook")

    def test_surfaces_hostname_resolution_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            network,
            "resolve_hostname_ips",
            Mock(side_effect=ValueError("Could not resolve hostname: missing.example")),
        )

        with pytest.raises(
            ValueError,
            match="Could not resolve hostname: missing.example",
        ):
            network.validate_outbound_http_url("https://missing.example/webhook")

    def test_custom_allowed_schemes_are_enforced(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_resolve = Mock(return_value=["8.8.8.8"])
        monkeypatch.setattr(network, "resolve_hostname_ips", mock_resolve)

        network.validate_outbound_http_url(
            "http://example.com/status",
            allowed_schemes={"http"},
        )

        with pytest.raises(ValueError, match="Invalid URL scheme or hostname."):
            network.validate_outbound_http_url(
                "https://example.com/status",
                allowed_schemes={"http"},
            )

        mock_resolve.assert_called_once_with("example.com")
