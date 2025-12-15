# noqa: INP001

"""
Ad-hoc script to gauge Tag + treenode performance locally.

It bootstraps a fresh SQLite DB in a temp folder (or PAPERLESS_DATA_DIR),
uses locmem cache/redis to avoid external services, creates synthetic tags,
and measures:
 - creation time
 - query count and wall time for the Tag list view

Usage:
    PAPERLESS_DEBUG=1 PAPERLESS_REDIS=locmem:// PYTHONPATH=src \
    PAPERLESS_DATA_DIR=/tmp/paperless-tags-probe \
    .venv/bin/python scripts/tag_perf_probe.py
"""

import os
import sys
import time
from collections.abc import Iterable
from contextlib import contextmanager

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")
os.environ.setdefault("PAPERLESS_DEBUG", "1")
os.environ.setdefault("PAPERLESS_REDIS", "locmem://")
os.environ.setdefault("PYTHONPATH", "src")

import django

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402
from django.test.client import RequestFactory  # noqa: E402
from rest_framework.test import force_authenticate  # noqa: E402
from treenode.signals import no_signals  # noqa: E402

from documents.models import Tag  # noqa: E402
from documents.views import TagViewSet  # noqa: E402

User = get_user_model()


@contextmanager
def count_queries():
    total = 0

    def wrapper(execute, sql, params, many, context):
        nonlocal total
        total += 1
        return execute(sql, params, many, context)

    with connection.execute_wrapper(wrapper):
        yield lambda: total


def measure_list(tag_count: int, user) -> tuple[int, float]:
    """Render Tag list with page_size=tag_count and return (queries, seconds)."""
    rf = RequestFactory()
    view = TagViewSet.as_view({"get": "list"})
    request = rf.get("/api/tags/", {"page_size": tag_count})
    force_authenticate(request, user=user)

    with count_queries() as get_count:
        start = time.perf_counter()
        response = view(request)
        response.render()
        elapsed = time.perf_counter() - start
        total_queries = get_count()

    return total_queries, elapsed


def bulk_create_tags(count: int, parents: Iterable[Tag] | None = None) -> None:
    """Create tags; when parents provided, create one child per parent."""
    if parents is None:
        Tag.objects.bulk_create([Tag(name=f"Flat {i}") for i in range(count)])
        return

    children = []
    for p in parents:
        children.append(Tag(name=f"Child {p.id}", tn_parent=p))
    Tag.objects.bulk_create(children)


def run():
    # Ensure tables exist when pointing at a fresh DATA_DIR.
    call_command("migrate", interactive=False, verbosity=0)

    user, _ = User.objects.get_or_create(
        username="admin",
        defaults={"is_superuser": True, "is_staff": True},
    )

    # Flat scenario
    Tag.objects.all().delete()
    start = time.perf_counter()
    bulk_create_tags(200)
    flat_create = time.perf_counter() - start
    q, t = measure_list(tag_count=200, user=user)
    print(f"Flat create 200 -> {flat_create:.2f}s; list -> {q} queries, {t:.2f}s")  # noqa: T201

    # Nested scenario (parents + 2 children each => 600 total)
    Tag.objects.all().delete()
    start = time.perf_counter()
    with no_signals():  # avoid per-save tree rebuild; rebuild once
        parents = Tag.objects.bulk_create([Tag(name=f"Parent {i}") for i in range(200)])
        children = []
        for p in parents:
            children.extend(
                Tag(name=f"Child {p.id}-{j}", tn_parent=p) for j in range(2)
            )
        Tag.objects.bulk_create(children)
    Tag.update_tree()
    nested_create = time.perf_counter() - start
    q, t = measure_list(tag_count=600, user=user)
    print(f"Nested create 600 -> {nested_create:.2f}s; list -> {q} queries, {t:.2f}s")  # noqa: T201

    # Larger nested scenario (1 child per parent, 3000 total)
    Tag.objects.all().delete()
    start = time.perf_counter()
    with no_signals():
        parents = Tag.objects.bulk_create(
            [Tag(name=f"Parent {i}") for i in range(1500)],
        )
        bulk_create_tags(0, parents=parents)
    Tag.update_tree()
    big_create = time.perf_counter() - start
    q, t = measure_list(tag_count=3000, user=user)
    print(f"Nested create 3000 -> {big_create:.2f}s; list -> {q} queries, {t:.2f}s")  # noqa: T201


if __name__ == "__main__":
    if "runserver" in sys.argv:
        print("Run directly: .venv/bin/python scripts/tag_perf_probe.py")  # noqa: T201
        sys.exit(1)
    run()
