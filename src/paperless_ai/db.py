from __future__ import annotations

from contextlib import contextmanager

from django.db import connections


@contextmanager
def db_connection_released():
    """
    Return any checked-out DB connections to the pool for the duration of the
    wrapped block.

    The AI endpoints run inside a synchronous web request (``ai_suggestions``)
    or a streaming response (``chat``). Django keeps the request's database
    connection checked out for the entire request/response, so a blocking LLM
    call - which can take many seconds - pins a pooled connection the whole
    time. With connection pooling enabled, enough concurrent AI requests check
    out every slot and all other requests then fail with
    ``psycopg_pool.PoolTimeout`` (see issue #12976).

    No Django ORM access happens during the LLM call, so we hand the connection
    back to the pool first; Django transparently re-checks-out a connection on
    the next ORM use after the block.
    """
    connections.close_all()
    try:
        yield
    finally:
        connections.close_all()
