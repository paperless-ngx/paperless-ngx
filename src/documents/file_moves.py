"""
Document file moves, coalesced to once per unit of work.

Every save that can change a document's generated filename asks for a file
move through request_file_move(). Inside a scope opened by defer_file_moves()
(a request, a Celery task, the consumer, or a per-item command step) the
request is only recorded, and the outermost scope moves each recorded document
once, after its own writes have committed. Outside any scope the move happens
immediately.

The mover always takes media.lock first and then reads the document fresh, so
it starts from the latest committed state and never waits on media.lock while
its own transaction holds document rows.
"""

from __future__ import annotations

from django.db import transaction


def in_user_transaction() -> bool:
    """
    True when the default connection is inside an atomic block that was not
    created by Django's test case machinery.

    Django marks the atomic blocks TestCase (and pytest-django) wrap around
    each test with _from_testcase, the same flag it uses for durable checks.
    Ignoring them keeps tests on the same path as production.
    """
    connection = transaction.get_connection()
    return any(not block._from_testcase for block in connection.atomic_blocks)
