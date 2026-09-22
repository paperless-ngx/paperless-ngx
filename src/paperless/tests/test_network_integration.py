import ipaddress
import os

import httpcore
import httpx
import pytest
from pytest_mock import MockerFixture

from paperless.network import GuardedAsyncHTTPTransport
from paperless.network import GuardedHTTPTransport
from paperless.network import OutboundRequestBlockedError
from paperless.network import create_guarded_httpx_client
from paperless_testing.outbound import DialRecorder
from paperless_testing.outbound import FakeDNS
from paperless_testing.outbound import LocalHTTPServer
from paperless_testing.outbound import running_http_server


class TestGuardedTransportSync:
    @pytest.mark.usefixtures("every_address_is_public")
    def test_pinned_connection_falls_back_to_next_address(
        self,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - A hostname resolving to ::1 then 127.0.0.1
            - A server listening on 127.0.0.1 only
            - Internal addresses disallowed, with loopback treated as public
        WHEN:
            - A request is made
        THEN:
            - ::1 fails, 127.0.0.1 is dialled next and the request succeeds
        """
        fake_dns.add("dual-stack.test", "::1", "127.0.0.1")

        with httpx.Client(
            transport=GuardedHTTPTransport(allow_internal=False),
            timeout=5.0,
        ) as client:
            response = client.get(f"http://dual-stack.test:{local_http_server.port}/")

        assert response.status_code == 200
        assert dial_recorder.hosts() == ["::1", "127.0.0.1"]

    def test_allow_internal_uses_stock_resolution(
        self,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
    ) -> None:
        """
        GIVEN:
            - Internal addresses allowed
        WHEN:
            - A request is made to localhost
        THEN:
            - It succeeds without the guard resolving anything
        """
        with httpx.Client(
            transport=GuardedHTTPTransport(allow_internal=True),
            timeout=5.0,
        ) as client:
            response = client.get(f"http://localhost:{local_http_server.port}/")

        assert response.status_code == 200
        assert fake_dns.lookups == []

    def test_blocks_internal_host_without_connecting(
        self,
        local_http_server: LocalHTTPServer,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - Internal addresses disallowed
        WHEN:
            - A request is made to localhost through the transport
        THEN:
            - It is blocked and the server never sees a connection
        """
        with (
            httpx.Client(
                transport=GuardedHTTPTransport(allow_internal=False),
                timeout=5.0,
            ) as client,
            pytest.raises(OutboundRequestBlockedError),
        ):
            client.get(f"http://localhost:{local_http_server.port}/")

        assert local_http_server.connections == 0
        assert dial_recorder.hosts() == []

    @pytest.mark.usefixtures("every_address_is_public")
    def test_host_header_is_the_hostname(
        self,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
    ) -> None:
        """
        GIVEN:
            - A pinned connection to a named host
        WHEN:
            - A request is made
        THEN:
            - The server receives the hostname in Host, not the dialled IP
        """
        fake_dns.add("pinned.test", "127.0.0.1")

        with httpx.Client(
            transport=GuardedHTTPTransport(allow_internal=False),
            timeout=5.0,
        ) as client:
            client.get(f"http://pinned.test:{local_http_server.port}/")

        assert local_http_server.requests[0].headers["host"] == (
            f"pinned.test:{local_http_server.port}"
        )

    def test_redirect_to_internal_host_is_blocked(
        self,
        mocker: MockerFixture,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - An allowed origin that redirects to a host resolving to a blocked
              address, and a client that follows redirects
        WHEN:
            - The origin is requested
        THEN:
            - The redirect hop is blocked without dialling the blocked address
        """
        allowed = ipaddress.ip_address("127.0.0.1")
        mocker.patch(
            "paperless.network.is_public_ip",
            side_effect=lambda address: address == allowed,
        )
        fake_dns.add("origin.test", "127.0.0.1")
        fake_dns.add("internal.test", "127.0.0.2")
        local_http_server.redirect_to = (
            f"http://internal.test:{local_http_server.port}/"
        )

        with (
            httpx.Client(
                transport=GuardedHTTPTransport(allow_internal=False),
                timeout=5.0,
                follow_redirects=True,
            ) as client,
            pytest.raises(OutboundRequestBlockedError) as exc_info,
        ):
            client.get(f"http://origin.test:{local_http_server.port}/")

        assert exc_info.value.address == ipaddress.ip_address("127.0.0.2")
        assert dial_recorder.hosts() == ["127.0.0.1"]
        assert len(local_http_server.requests) == 1

    @pytest.mark.usefixtures("every_address_is_public")
    def test_connections_are_not_shared_between_hosts_on_one_address(
        self,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - Two hostnames resolving to the same address
            - Internal addresses disallowed, with loopback treated as public
        WHEN:
            - One client requests the first host twice, then the second host
        THEN:
            - The first host's connection is reused for its second request
            - The second host gets its own connection, so its certificate would
              be checked rather than inheriting the first host's session
        """
        fake_dns.add("first.test", "127.0.0.1")
        fake_dns.add("second.test", "127.0.0.1")

        with httpx.Client(
            transport=GuardedHTTPTransport(allow_internal=False),
            timeout=5.0,
        ) as client:
            client.get(f"http://first.test:{local_http_server.port}/")
            client.get(f"http://first.test:{local_http_server.port}/")
            client.get(f"http://second.test:{local_http_server.port}/")

        assert dial_recorder.hosts() == ["127.0.0.1", "127.0.0.1"]
        assert local_http_server.connections == 2
        assert [request.headers["host"] for request in local_http_server.requests] == [
            f"first.test:{local_http_server.port}",
            f"first.test:{local_http_server.port}",
            f"second.test:{local_http_server.port}",
        ]

    @pytest.mark.usefixtures("every_address_is_public")
    def test_tls_uses_the_hostname_not_the_dialled_address(
        self,
        mocker: MockerFixture,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - A pinned HTTPS connection to a named host
            - A plain HTTP server, so the handshake itself fails
        WHEN:
            - A request is made
        THEN:
            - The validated address is dialled
            - TLS is started with the hostname for SNI and certificate checks
        """
        fake_dns.add("pinned.test", "127.0.0.1")
        start_tls = mocker.spy(httpcore._backends.sync.SyncStream, "start_tls")

        with (
            httpx.Client(
                transport=GuardedHTTPTransport(allow_internal=False),
                timeout=5.0,
            ) as client,
            pytest.raises(httpx.ConnectError),
        ):
            client.get(f"https://pinned.test:{local_http_server.port}/")

        assert dial_recorder.hosts() == ["127.0.0.1"]
        start_tls.assert_called_once()
        assert start_tls.call_args.kwargs["server_hostname"] == "pinned.test"

    @pytest.mark.parametrize(
        "host",
        [
            pytest.param("2130706433", id="decimal"),
            pytest.param("0x7f.1", id="hex-short"),
            pytest.param("127.1", id="short-dotted"),
        ],
    )
    def test_numeric_host_forms_are_blocked(
        self,
        local_http_server: LocalHTTPServer,
        dial_recorder: DialRecorder,
        host: str,
    ) -> None:
        """
        GIVEN:
            - Internal addresses disallowed
            - A URL whose host is a non-canonical spelling of 127.0.0.1
        WHEN:
            - A request is made through the transport
        THEN:
            - The resolved address is checked, the request is blocked and the
              server never sees a connection
        """
        with (
            httpx.Client(
                transport=GuardedHTTPTransport(allow_internal=False),
                timeout=5.0,
            ) as client,
            pytest.raises(OutboundRequestBlockedError),
        ):
            client.get(f"http://{host}:{local_http_server.port}/")

        assert local_http_server.connections == 0
        assert dial_recorder.hosts() == []

    @pytest.mark.usefixtures("every_address_is_public")
    def test_environment_proxy_is_not_used(
        self,
        mocker: MockerFixture,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - Proxy variables in the environment pointing at a second local server
            - Internal addresses disallowed
        WHEN:
            - A request is made through the production client factory to an
              allowed origin
        THEN:
            - The origin server receives the request directly and the proxy
              server never sees a connection
        """
        with running_http_server() as proxy_server:
            mocker.patch.dict(
                os.environ,
                {
                    "HTTP_PROXY": f"http://127.0.0.1:{proxy_server.port}",
                    "HTTPS_PROXY": f"http://127.0.0.1:{proxy_server.port}",
                    "ALL_PROXY": f"http://127.0.0.1:{proxy_server.port}",
                },
            )
            fake_dns.add("origin.test", "127.0.0.1")

            url = f"http://origin.test:{local_http_server.port}/"
            with create_guarded_httpx_client(
                url,
                allow_internal=False,
                timeout=5.0,
            ) as client:
                response = client.get(url)

            assert response.status_code == 200
            assert len(local_http_server.requests) == 1
            assert local_http_server.requests[0].headers["host"] == (
                f"origin.test:{local_http_server.port}"
            )
            assert proxy_server.connections == 0
            assert proxy_server.requests == []
            assert dial_recorder.hosts() == ["127.0.0.1"]


class TestGuardedTransportAsync:
    @pytest.fixture(autouse=True)
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.mark.anyio
    @pytest.mark.usefixtures("every_address_is_public")
    async def test_pinned_connection_falls_back_to_next_address(
        self,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - A hostname resolving to ::1 then 127.0.0.1
            - A server listening on 127.0.0.1 only
            - Internal addresses disallowed, with loopback treated as public
        WHEN:
            - An async request is made
        THEN:
            - ::1 fails, 127.0.0.1 is dialled next and the request succeeds
        """
        fake_dns.add("dual-stack.test", "::1", "127.0.0.1")

        async with httpx.AsyncClient(
            transport=GuardedAsyncHTTPTransport(allow_internal=False),
            timeout=5.0,
        ) as client:
            response = await client.get(
                f"http://dual-stack.test:{local_http_server.port}/",
            )

        assert response.status_code == 200
        assert dial_recorder.hosts() == ["::1", "127.0.0.1"]

    @pytest.mark.anyio
    async def test_allow_internal_uses_stock_resolution(
        self,
        local_http_server: LocalHTTPServer,
        fake_dns: FakeDNS,
    ) -> None:
        """
        GIVEN:
            - Internal addresses allowed
        WHEN:
            - An async request is made to localhost
        THEN:
            - It succeeds without the guard resolving anything
        """
        async with httpx.AsyncClient(
            transport=GuardedAsyncHTTPTransport(allow_internal=True),
            timeout=5.0,
        ) as client:
            response = await client.get(f"http://localhost:{local_http_server.port}/")

        assert response.status_code == 200
        assert fake_dns.lookups == []

    @pytest.mark.anyio
    async def test_blocks_internal_host_without_connecting(
        self,
        local_http_server: LocalHTTPServer,
        dial_recorder: DialRecorder,
    ) -> None:
        """
        GIVEN:
            - Internal addresses disallowed
        WHEN:
            - An async request is made to localhost through the transport
        THEN:
            - It is blocked and the server never sees a connection
        """
        async with httpx.AsyncClient(
            transport=GuardedAsyncHTTPTransport(allow_internal=False),
            timeout=5.0,
        ) as client:
            with pytest.raises(OutboundRequestBlockedError):
                await client.get(f"http://localhost:{local_http_server.port}/")

        assert local_http_server.connections == 0
        assert dial_recorder.hosts() == []
