"""Fixtures available to every Paperless-ngx app.

Loaded automatically for every test path. Keep module-scope imports minimal:
this file is imported for every session,  so anything heavy belongs inside
the fixture body that needs it.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def faker_session_locale() -> str:
    """Set Faker locale for reproducibility."""
    return "en_US"


@pytest.fixture(scope="session", autouse=True)
def faker_seed() -> int:
    return 12345


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
