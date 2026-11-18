import pytest
from django.core.cache import cache
from pytest_httpx import HTTPXMock
from rest_framework import status
from rest_framework.test import APIClient

from paperless import version

REPO_URL = "https://api.github.com/repos/paperless-ngx/paperless-ngx"
RELEASES_URL = f"{REPO_URL}/releases?per_page=10"


def _release(tag: str, **kwargs) -> dict:
    return {
        "tag_name": tag,
        "name": f"Paperless-ngx {tag}",
        "body_html": f"<h2>paperless-ngx {tag}</h2>",
        "html_url": f"https://github.com/paperless-ngx/paperless-ngx/releases/tag/{tag}",
        "published_at": "2026-11-17T03:36:20Z",
        "draft": False,
        "prerelease": False,
        **kwargs,
    }


def _bump(minor: int = 0, patch: int = 0) -> str:
    major, cur_minor, cur_patch = version.__version__
    return f"{major}.{cur_minor + minor}.{cur_patch + patch}"


CURRENT = version.__full_version_str__
PREVIOUS = f"{version.__version__[0]}.{version.__version__[1] - 1}.0"
OLDER = f"{version.__version__[0]}.{version.__version__[1] - 2}.0"


class TestApiReleaseNotes:
    ENDPOINT = "/api/release_notes/"

    def setup_method(self) -> None:
        cache.clear()

    @pytest.fixture
    def releases(self, httpx_mock: HTTPXMock) -> HTTPXMock:
        httpx_mock.add_response(
            url=RELEASES_URL,
            match_headers={"Accept": "application/vnd.github.html+json"},
            json=[
                _release(f"v{_bump(patch=1)}"),
                _release(f"v{_bump(minor=1)}-beta.1", prerelease=True),
                _release(f"v{CURRENT}"),
                _release(f"v{PREVIOUS}"),
                _release(f"ngx-{OLDER}"),
            ],
        )
        return httpx_mock

    @pytest.fixture
    def stars(self, httpx_mock: HTTPXMock) -> HTTPXMock:
        httpx_mock.add_response(url=REPO_URL, json={"stargazers_count": 1234})
        return httpx_mock

    @pytest.mark.usefixtures("stars")
    def test_since_returns_newer_up_to_current(
        self,
        rest_api_client: APIClient,
        releases: HTTPXMock,
    ) -> None:
        """
        GIVEN:
            - GitHub releases older, equal to, and newer than the running version
        WHEN:
            - Release notes are requested since an older version
        THEN:
            - Only releases after `since` up to the running version are returned,
              newest first, excluding prereleases and the `since` release itself
        """
        response = rest_api_client.get(self.ENDPOINT, {"since": OLDER})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["version"] == CURRENT
        assert [r["version"] for r in response.data["releases"]] == [
            CURRENT,
            PREVIOUS,
        ]
        assert response.data["releases"][0]["html_url"].endswith(f"v{CURRENT}")
        assert (
            response.data["releases"][0]["body_html"]
            == f"<h2>paperless-ngx v{CURRENT}</h2>"
        )

    @pytest.mark.usefixtures("stars")
    def test_without_since_returns_current_only(
        self,
        rest_api_client: APIClient,
        releases: HTTPXMock,
    ) -> None:
        response = rest_api_client.get(self.ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert [r["version"] for r in response.data["releases"]] == [CURRENT]

    @pytest.mark.usefixtures("stars")
    def test_releases_are_cached(
        self,
        rest_api_client: APIClient,
        releases: HTTPXMock,
    ) -> None:
        rest_api_client.get(self.ENDPOINT, {"since": OLDER})
        rest_api_client.get(self.ENDPOINT)

        assert len(releases.get_requests(url=RELEASES_URL)) == 1
        assert len(releases.get_requests(url=REPO_URL)) == 1

    def test_invalid_since(
        self,
        rest_api_client: APIClient,
    ) -> None:
        response = rest_api_client.get(self.ENDPOINT, {"since": "not-a-version"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        "mock_kwargs",
        [
            pytest.param({"status_code": 503}, id="http-error"),
            pytest.param(
                {
                    "content": b'{ "blah":',
                    "headers": {"Content-Type": "application/json"},
                },
                id="bad-json",
            ),
        ],
    )
    def test_github_failure_returns_empty_and_is_not_cached(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
        mock_kwargs: dict,
    ) -> None:
        httpx_mock.add_response(url=RELEASES_URL, **mock_kwargs)
        httpx_mock.add_response(url=RELEASES_URL, json=[_release(f"v{CURRENT}")])
        httpx_mock.add_response(
            url=REPO_URL,
            json={"stargazers_count": 1234},
            is_reusable=True,
        )

        response = rest_api_client.get(self.ENDPOINT)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["releases"] == []

        response = rest_api_client.get(self.ENDPOINT)
        assert [r["version"] for r in response.data["releases"]] == [CURRENT]

    @pytest.mark.usefixtures("releases", "stars")
    def test_stars_are_returned_and_cached(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        """
        GIVEN:
            - The GitHub repository reports a star count
        WHEN:
            - Release notes are requested twice
        THEN:
            - The star count is included and GitHub is only asked once
        """
        response = rest_api_client.get(self.ENDPOINT)
        assert response.data["stars"] == 1234

        response = rest_api_client.get(self.ENDPOINT)
        assert response.data["stars"] == 1234
        assert len(httpx_mock.get_requests(url=REPO_URL)) == 1

    @pytest.mark.usefixtures("releases")
    def test_stars_failure_returns_none_and_is_not_cached(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        """
        GIVEN:
            - The GitHub repository request fails, then succeeds
        WHEN:
            - Release notes are requested twice
        THEN:
            - Stars are null at first, then fetched again rather than cached
        """
        httpx_mock.add_response(url=REPO_URL, status_code=503)
        httpx_mock.add_response(url=REPO_URL, json={"stargazers_count": 1234})

        response = rest_api_client.get(self.ENDPOINT)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["stars"] is None
        assert len(response.data["releases"]) == 1

        response = rest_api_client.get(self.ENDPOINT)
        assert response.data["stars"] == 1234
