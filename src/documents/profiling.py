"""
Temporary profiling utilities for comparing implementations.

Usage in a management command or shell::

    from documents.profiling import profile_block

    with profile_block("new check_sanity"):
        messages = check_sanity()

    with profile_block("old check_sanity"):
        messages = check_sanity_old()

Drop this file when done.
"""

from __future__ import annotations

import tracemalloc
from contextlib import contextmanager
from time import perf_counter
from typing import TYPE_CHECKING

from django.db import connection
from django.db import reset_queries
from django.test.utils import override_settings

if TYPE_CHECKING:
    from collections.abc import Generator


@contextmanager
def profile_block(label: str = "block") -> Generator[None, None, None]:
    """Profile memory, wall time, and DB queries for a code block.

    Prints a summary to stdout on exit. Requires no external packages.
    Enables DEBUG temporarily to capture Django's query log.
    """
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    with override_settings(DEBUG=True):
        reset_queries()
        start = perf_counter()

        yield

        elapsed = perf_counter() - start
        queries = list(connection.queries)

    snapshot_after = tracemalloc.take_snapshot()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Compare snapshots for top allocations
    stats = snapshot_after.compare_to(snapshot_before, "lineno")

    query_time = sum(float(q["time"]) for q in queries)
    mem_diff = sum(s.size_diff for s in stats)

    print(f"\n{'=' * 60}")  # noqa: T201
    print(f"  Profile: {label}")  # noqa: T201
    print(f"{'=' * 60}")  # noqa: T201
    print(f"  Wall time:    {elapsed:.4f}s")  # noqa: T201
    print(f"  Queries:      {len(queries)} ({query_time:.4f}s)")  # noqa: T201
    print(f"  Memory delta: {mem_diff / 1024:.1f} KiB")  # noqa: T201
    print(f"  Peak memory:  {peak / 1024:.1f} KiB")  # noqa: T201
    print("\n  Top 5 allocations:")  # noqa: T201
    for stat in stats[:5]:
        print(f"    {stat}")  # noqa: T201
    print(f"{'=' * 60}\n")  # noqa: T201
