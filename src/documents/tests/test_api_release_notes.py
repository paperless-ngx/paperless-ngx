from unittest import mock

import pytest
from django.core.cache import cache
from pytest_httpx import HTTPXMock
from rest_framework import status
from rest_framework.test import APIClient

from paperless import version

REPO_URL = "https://api.github.com/repos/paperless-ngx/paperless-ngx"
RELEASES_URL = f"{REPO_URL}/releases?per_page=10&page=1"


def _page_url(page: int) -> str:
    return f"{REPO_URL}/releases?per_page=10&page={page}"


def _tag_url(version_str: str) -> str:
    return f"{REPO_URL}/releases/tags/v{version_str}"


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
    def current_release(self, httpx_mock: HTTPXMock) -> HTTPXMock:
        httpx_mock.add_response(
            url=_tag_url(CURRENT),
            match_headers={"Accept": "application/vnd.github.html+json"},
            json=_release(f"v{CURRENT}"),
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
    def test_without_since_fetches_current_only(
        self,
        rest_api_client: APIClient,
        current_release: HTTPXMock,
    ) -> None:
        """
        GIVEN:
            - A GitHub release for the running version
        WHEN:
            - Release notes are requested without `since`
        THEN:
            - Only that release is fetched, by tag, and returned
        """
        response = rest_api_client.get(self.ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert [r["version"] for r in response.data["releases"]] == [CURRENT]
        assert len(current_release.get_requests(url=_tag_url(CURRENT))) == 1

    @pytest.mark.usefixtures("stars")
    def test_since_pages_back_to_since(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        """
        GIVEN:
            - More releases since `since` than fit on one page
        WHEN:
            - Release notes are requested since that version
        THEN:
            - GitHub is paged until `since` is reached and all releases are returned
        """
        major, minor, _ = version.__version__
        page_one = [f"{major}.{minor - 1}.{patch}" for patch in range(10, 0, -1)]
        httpx_mock.add_response(
            url=_page_url(1),
            json=[_release(f"v{v}") for v in page_one],
        )
        httpx_mock.add_response(
            url=_page_url(2),
            json=[_release(f"v{PREVIOUS}"), _release(f"v{OLDER}")],
        )

        response = rest_api_client.get(self.ENDPOINT, {"since": OLDER})

        assert [r["version"] for r in response.data["releases"]] == [
            *page_one,
            PREVIOUS,
        ]

    @pytest.mark.usefixtures("stars")
    def test_since_paging_is_capped(
        self,
        rest_api_client: APIClient,
        httpx_mock: HTTPXMock,
    ) -> None:
        """
        GIVEN:
            - Full pages of releases that never reach `since`
        WHEN:
            - Release notes are requested since a very old version
        THEN:
            - Paging stops after the page cap
        """
        major, minor, _ = version.__version__
        for page in range(1, 4):
            httpx_mock.add_response(
                url=_page_url(page),
                json=[
                    _release(f"v{major}.{minor}.{page * 100 + patch}")
                    for patch in range(10)
                ],
            )

        rest_api_client.get(self.ENDPOINT, {"since": "0.1.0"})

        assert len(httpx_mock.get_requests()) == 4  # 3 pages + stars

    @pytest.mark.usefixtures("stars")
    @pytest.mark.usefixtures("current_release")
    def test_releases_are_cached(
        self,
        rest_api_client: APIClient,
        releases: HTTPXMock,
    ) -> None:
        for _ in range(2):
            rest_api_client.get(self.ENDPOINT, {"since": OLDER})
            rest_api_client.get(self.ENDPOINT)

        assert len(releases.get_requests(url=RELEASES_URL)) == 1
        assert len(releases.get_requests(url=_tag_url(CURRENT))) == 1
        assert len(releases.get_requests(url=REPO_URL)) == 1

    @pytest.mark.usefixtures("stars")
    def test_new_running_version_refetches_releases(
        self,
        rest_api_client: APIClient,
        releases: HTTPXMock,
    ) -> None:
        """
        GIVEN:
            - GitHub releases cached for the running version
        WHEN:
            - The running version changes (i.e. paperless was upgraded)
        THEN:
            - The cached releases are not reused and GitHub is queried again
        """
        upgraded = _bump(patch=1)
        releases.add_response(url=RELEASES_URL, json=[_release(f"v{upgraded}")])

        rest_api_client.get(self.ENDPOINT, {"since": OLDER})
        with mock.patch.object(version, "__full_version_str__", upgraded):
            response = rest_api_client.get(self.ENDPOINT, {"since": CURRENT})

        assert len(releases.get_requests(url=RELEASES_URL)) == 2
        assert [r["version"] for r in response.data["releases"]] == [upgraded]

    @pytest.mark.usefixtures("stars")
    def test_until_returns_newer_releases(
        self,
        rest_api_client: APIClient,
        releases: HTTPXMock,
    ) -> None:
        """
        GIVEN:
            - A GitHub release newer than the running version
        WHEN:
            - Release notes are requested from the running version until the newer one
        THEN:
            - Only the newer release is returned, excluding prereleases
        """
        response = rest_api_client.get(
            self.ENDPOINT,
            {"since": CURRENT, "until": _bump(minor=1)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert [r["version"] for r in response.data["releases"]] == [
            _bump(patch=1),
        ]

    @pytest.mark.parametrize("param", ["since", "until"])
    def test_invalid_version(
        self,
        rest_api_client: APIClient,
        param: str,
    ) -> None:
        response = rest_api_client.get(self.ENDPOINT, {param: "not-a-version"})

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
        httpx_mock.add_response(url=_tag_url(CURRENT), **mock_kwargs)
        httpx_mock.add_response(url=_tag_url(CURRENT), json=_release(f"v{CURRENT}"))
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

    @pytest.mark.usefixtures("current_release", "stars")
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

    @pytest.mark.usefixtures("current_release")
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
