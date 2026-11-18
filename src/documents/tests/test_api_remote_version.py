from unittest import mock

from django.core.cache import cache
from pytest_httpx import HTTPXMock
from rest_framework import status
from rest_framework.test import APIClient

from paperless import version

RELEASES_URL = (
    "https://api.github.com/repos/paperless-ngx/paperless-ngx/releases?per_page=10"
)


def _release(tag: str, **kwargs) -> dict:
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/paperless-ngx/paperless-ngx/releases/tag/{tag}",
        **kwargs,
    }


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
            url=RELEASES_URL,
            json=[_release("ngx-1.6.0")],
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
            url=RELEASES_URL,
            json=[_release(version.__full_version_str__)],
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
            url=RELEASES_URL,
            json=[_release(new_version_str)],
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

    def test_remote_version_uses_highest_published_release(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        """
        GIVEN:
            - A backport release listed before a newer release, and a newer prerelease
        WHEN:
            - The remote version is requested
        THEN:
            - The highest non-prerelease version is reported
        """
        major, minor, patch = version.__version__
        newer = f"{major}.{minor}.{patch + 1}"
        httpx_mock.add_response(
            url=RELEASES_URL,
            json=[
                _release(f"v{major + 1}.0.0-beta.1", prerelease=True),
                _release(f"v{major - 1}.9.9"),
                _release(f"v{newer}"),
            ],
        )

        response = rest_api_client.get(self.ENDPOINT)

        assert response.data["version"] == newer
        assert response.data["update_available"]

    def test_remote_version_and_release_notes_share_request(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=RELEASES_URL,
            json=[_release(f"v{version.__full_version_str__}")],
        )

        rest_api_client.get(self.ENDPOINT)
        response = rest_api_client.get("/api/release_notes/")

        assert len(response.data["releases"]) == 1
        assert len(httpx_mock.get_requests()) == 1

    def test_new_running_version_refetches_releases(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        """
        GIVEN:
            - GitHub releases cached for the running version
        WHEN:
            - The running version changes (i.e. paperless was upgraded)
        THEN:
            - The cached releases are not reused and GitHub is queried again
        """
        major, minor, patch = version.__version__
        upgraded = f"{major}.{minor}.{patch + 1}"
        httpx_mock.add_response(
            url=RELEASES_URL,
            json=[_release(f"v{version.__full_version_str__}")],
        )
        httpx_mock.add_response(url=RELEASES_URL, json=[_release(f"v{upgraded}")])

        rest_api_client.get(self.ENDPOINT)
        with mock.patch.object(version, "__full_version_str__", upgraded):
            response = rest_api_client.get("/api/release_notes/")

        assert len(httpx_mock.get_requests()) == 2
        assert [r["version"] for r in response.data["releases"]] == [upgraded]
