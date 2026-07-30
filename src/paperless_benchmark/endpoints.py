# src/paperless_benchmark/endpoints.py
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from rest_framework.test import APIClient

ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("documents_default", "/api/documents/"),
    ("documents_page50", "/api/documents/?page_size=50"),
    ("tags_all", "/api/tags/?page_size=100000"),
)


@dataclass(frozen=True, slots=True)
class EndpointTiming:
    user_label: str
    endpoint_name: str
    query_count: int
    min_ms: float
    median_ms: float
    max_ms: float


def _timed_requests(client: APIClient, url: str, n: int) -> list[float]:
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        resp = client.get(url)
        t1 = time.perf_counter()
        if resp.status_code != 200:
            raise RuntimeError(
                f"GET {url} -> {resp.status_code}: {resp.content[:300]!r}",
            )
        times.append(t1 - t0)
    return times


def _query_count(client: APIClient, url: str) -> int:
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(url)
    if resp.status_code != 200:
        raise RuntimeError(f"GET {url} -> {resp.status_code}: {resp.content[:300]!r}")
    return len(ctx.captured_queries)


def run_endpoint_benchmarks(
    *,
    perf_target: User,
    perf_admin: User,
    repeat: int,
) -> list[EndpointTiming]:
    from rest_framework.test import APIClient

    results: list[EndpointTiming] = []
    for user_label, user in (("target", perf_target), ("admin", perf_admin)):
        client = APIClient()
        client.force_authenticate(user=user)
        for name, url in ENDPOINTS:
            client.get(url)  # warm-up request, not counted
            qcount = _query_count(client, url)
            times_ms = [t * 1000 for t in _timed_requests(client, url, repeat)]
            results.append(
                EndpointTiming(
                    user_label=user_label,
                    endpoint_name=name,
                    query_count=qcount,
                    min_ms=min(times_ms),
                    median_ms=statistics.median(times_ms),
                    max_ms=max(times_ms),
                ),
            )
    return results
