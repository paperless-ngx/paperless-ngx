"""Fixtures available to every Paperless-ngx app.

Loaded automatically for every test path. Keep module-scope imports minimal:
this file is imported for every session,  so anything heavy belongs inside
the fixture body that needs it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from django.contrib.auth.models import User
    from pytest_django.fixtures import Settings
    from rest_framework.test import APIClient

    from paperless_testing.dirs import PaperlessDirs


@pytest.fixture(scope="session", autouse=True)
def faker_session_locale() -> str:
    """Pin Faker's locale so generated data does not follow the host locale.

    The seed itself is left to pytest-randomly, which derives one per run.
    """
    return "en_US"


@pytest.fixture(autouse=True)
def _clear_content_type_caches() -> None:
    """Clear Django's ContentType cache and guardian's lru_cache before each test.

    Tests that delete and reinsert ContentType/Permission rows (e.g. the
    importer) corrupt both caches. Without this fixture a subsequent test on
    the same xdist worker sees stale ContentType objects and guardian raises
    MixedContentTypeError.
    """
    from django.contrib.contenttypes.models import ContentType
    from guardian.shortcuts import clear_ct_cache

    ContentType.objects.clear_cache()
    clear_ct_cache()


@pytest.fixture(autouse=True)
def _clear_django_caches() -> None:
    """Clear every configured cache before each test.

    Cached values outlive the test that wrote them: the classifier keys its
    vectorized content on a hash of the content itself, so a second test
    generating the same fixture data takes the cache-hit path and never calls
    the code it is asserting against.
    """
    from django.core.cache import caches

    for cache in caches.all(initialized_only=False):
        cache.clear()


@pytest.fixture
def paperless_dirs(
    tmp_path: Path,
    settings: Settings,
) -> Generator[PaperlessDirs, None, None]:
    """The standard temp directory layout, applied to Django settings."""
    from documents.search import reset_backend
    from paperless_testing.dirs import build_paperless_dirs
    from paperless_testing.dirs import dirs_settings

    dirs = build_paperless_dirs(tmp_path)
    for name, value in dirs_settings(dirs).items():
        setattr(settings, name, value)

    # Not directory settings, but they are needed alongside the layout by the
    # sanity checker tests.
    settings.IGNORABLE_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
    settings.APP_LOGO = ""

    reset_backend()
    yield dirs
    reset_backend()


@pytest.fixture
def rest_api_client() -> APIClient:
    """The basic DRF APIClient, unauthenticated."""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def regular_user(db: None) -> User:
    """Unprivileged user for permission boundary tests."""
    from paperless_testing.factories import UserFactory

    return UserFactory(username="regular")


@pytest.fixture
def admin_client(rest_api_client: APIClient, admin_user: User) -> APIClient:
    """Admin client pre-authenticated and sending the v10 Accept header."""
    rest_api_client.force_authenticate(user=admin_user)
    rest_api_client.credentials(HTTP_ACCEPT="application/json; version=10")
    return rest_api_client


@pytest.fixture
def v9_client(rest_api_client: APIClient, admin_user: User) -> APIClient:
    """Admin client pre-authenticated and sending the v9 Accept header."""
    rest_api_client.force_authenticate(user=admin_user)
    rest_api_client.credentials(HTTP_ACCEPT="application/json; version=9")
    return rest_api_client


@pytest.fixture
def user_client(rest_api_client: APIClient, regular_user: User) -> APIClient:
    """Regular-user client pre-authenticated and sending the v10 Accept header."""
    rest_api_client.force_authenticate(user=regular_user)
    rest_api_client.credentials(HTTP_ACCEPT="application/json; version=10")
    return rest_api_client
