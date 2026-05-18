from django.core.cache import cache
from pytest_httpx import HTTPXMock
from rest_framework import status
from rest_framework.test import APIClient

from paperless import version


class TestApiRemoteVersion:
    ENDPOINT = "/api/remote_version/"

    def setup_method(self) -> None:
        cache.clear()

    def test_remote_version_enabled_no_update_prefix(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://api.github.com/repos/paperless-ngx/paperless-ngx/releases/latest",
            json={"tag_name": "ngx-1.6.0"},
        )

        response = rest_api_client.get(self.ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert "version" in response.data
        assert response.data["version"] == "1.6.0"

        assert "update_available" in response.data
        assert not response.data["update_available"]

    def test_remote_version_enabled_no_update_no_prefix(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://api.github.com/repos/paperless-ngx/paperless-ngx/releases/latest",
            json={"tag_name": version.__full_version_str__},
        )

        response = rest_api_client.get(self.ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert "version" in response.data
        assert response.data["version"] == version.__full_version_str__

        assert "update_available" in response.data
        assert not response.data["update_available"]

    def test_remote_version_enabled_update(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        new_version = (
            version.__version__[0],
            version.__version__[1],
            version.__version__[2] + 1,
        )
        new_version_str = ".".join(map(str, new_version))

        httpx_mock.add_response(
            url="https://api.github.com/repos/paperless-ngx/paperless-ngx/releases/latest",
            json={"tag_name": new_version_str},
        )

        response = rest_api_client.get(self.ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert "version" in response.data
        assert response.data["version"] == new_version_str

        assert "update_available" in response.data
        assert response.data["update_available"]

    def test_remote_version_bad_json(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            content=b'{ "blah":',
            headers={"Content-Type": "application/json"},
        )

        response = rest_api_client.get(self.ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert "version" in response.data
        assert response.data["version"] == "0.0.0"

        assert "update_available" in response.data
        assert not response.data["update_available"]

    def test_remote_version_exception(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(status_code=503)

        response = rest_api_client.get(self.ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert "version" in response.data
        assert response.data["version"] == "0.0.0"

        assert "update_available" in response.data
        assert not response.data["update_available"]
