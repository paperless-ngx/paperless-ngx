"""
Temporary profiling utilities for comparing implementations.

Usage in a management command or shell::

    from profiling import profile_block, profile_cpu, measure_memory

    with profile_block("new check_sanity"):
        messages = check_sanity()

    with profile_block("old check_sanity"):
        messages = check_sanity_old()

Drop this file when done.
"""

from __future__ import annotations

import tracemalloc
from collections.abc import Callable  # noqa: TC003
from collections.abc import Generator  # noqa: TC003
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from django.db import connection
from django.db import reset_queries
from django.test.utils import override_settings


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


def profile_cpu(
    fn: Callable[[], Any],
    *,
    label: str,
    top: int = 30,
    sort: str = "cumtime",
) -> tuple[Any, float]:
    """Run *fn()* under cProfile, print stats, return (result, elapsed_s).

    Args:
        fn: Zero-argument callable to profile.
        label: Human-readable label printed in the header.
        top: Number of cProfile rows to print.
        sort: cProfile sort key (default: cumulative time).

    Returns:
        ``(result, elapsed_s)`` where *result* is the return value of *fn()*.
    """
    import cProfile
    import io
    import pstats

    pr = cProfile.Profile()
    t0 = perf_counter()
    pr.enable()
    result = fn()
    pr.disable()
    elapsed = perf_counter() - t0

    buf = io.StringIO()
    ps = pstats.Stats(pr, stream=buf).sort_stats(sort)
    ps.print_stats(top)

    print(f"\n{'=' * 72}")  # noqa: T201
    print(f"  {label}")  # noqa: T201
    print(f"  wall time: {elapsed * 1000:.1f} ms")  # noqa: T201
    print(f"{'=' * 72}")  # noqa: T201
    print(buf.getvalue())  # noqa: T201

    return result, elapsed


def measure_memory(fn: Callable[[], Any], *, label: str) -> tuple[Any, float, float]:
    """Run *fn()* under tracemalloc, print allocation report.

    Args:
        fn: Zero-argument callable to profile.
        label: Human-readable label printed in the header.

    Returns:
        ``(result, peak_kib, delta_kib)``.
    """
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()
    t0 = perf_counter()
    result = fn()
    elapsed = perf_counter() - t0
    snapshot_after = tracemalloc.take_snapshot()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    delta_kib = sum(s.size_diff for s in stats) / 1024

    print(f"\n{'=' * 72}")  # noqa: T201
    print(f"  [memory] {label}")  # noqa: T201
    print(f"  wall time:    {elapsed * 1000:.1f} ms")  # noqa: T201
    print(f"  memory delta: {delta_kib:+.1f} KiB")  # noqa: T201
    print(f"  peak traced:  {peak / 1024:.1f} KiB")  # noqa: T201
    print(f"{'=' * 72}")  # noqa: T201
    print("  Top allocation sites (by size_diff):")  # noqa: T201
    for stat in stats[:20]:
        if stat.size_diff != 0:
            print(  # noqa: T201
                f"    {stat.size_diff / 1024:+8.1f} KiB  {stat.traceback.format()[0]}",
            )

    return result, peak / 1024, delta_kib
