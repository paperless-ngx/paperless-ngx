# src/paperless_benchmark/harness.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar

from django.db import connection
from django.test.utils import CaptureQueriesContext

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ProfileResult(Generic[T]):
    best_seconds: float
    all_seconds: tuple[float, ...]
    query_count: int
    result: T


def run_profile(fn: Callable[[], T], *, repeat: int = 5) -> ProfileResult[T]:
    """
    Call `fn` `repeat` times, capturing wall-clock time for every call and
    the SQL query count for the final call. Returns the best (minimum)
    time across all repeats, since the first call(s) can be skewed by
    connection warm-up or cold caches.
    """
    all_seconds: list[float] = []
    result: T | None = None
    query_count = 0
    for i in range(repeat):
        with CaptureQueriesContext(connection) as ctx:
            start = time.perf_counter()
            result = fn()
            all_seconds.append(time.perf_counter() - start)
        if i == repeat - 1:
            query_count = len(ctx.captured_queries)
    assert result is not None  # repeat >= 1 guarantees at least one assignment
    return ProfileResult(
        best_seconds=min(all_seconds),
        all_seconds=tuple(all_seconds),
        query_count=query_count,
        result=result,
    )
