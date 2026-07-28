"""Schema migrations for the sqlite-vec vector store.

Each migration lives in its own module here, named ``mNNNN_description.py``
(e.g. ``m0001_add_document_chunks.py`` -- a leading digit isn't a valid
Python identifier, hence the ``m`` prefix, unlike Django's own numbered
migrations, which load via a dynamic ``importlib.import_module()`` call
rather than a static import statement), and registers itself into
``MIGRATIONS`` at import time. ``vector_store.py`` imports those modules at
the bottom of the file, purely for that registration side effect, after
``PaperlessSqliteVecVectorStore`` is fully defined -- migrations need it to
implement ``apply()`` (see ``Migration`` below).

To add a new migration: add a new ``mNNNN_description.py`` module here that
imports ``PaperlessSqliteVecVectorStore`` from ``paperless_ai.vector_store``,
defines its ``apply()`` (most likely just a call to
``PaperlessSqliteVecVectorStore._rebuild_into()``, see ``Migration`` below),
and appends a ``Migration`` to ``MIGRATIONS``; then import that module at the
bottom of ``vector_store.py`` and bump ``SCHEMA_VERSION`` there.
"""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import Literal


@dataclass
class Migration:
    """A schema migration for the sqlite-vec vector store.

    kind="structural": rows are copied into a new-schema file with no
    re-embedding needed.  Supply ``apply(src_conn, dst_conn, dim)``, which
    must create the vec0 table in ``dst_conn`` and copy ``src_conn``'s rows
    and index_meta into it -- usually just a call to
    ``PaperlessSqliteVecVectorStore._rebuild_into(src_conn, dst_conn, dim)``.
    ``schema_version`` is written by the migration runner after ``apply``
    returns, not by ``apply`` itself.

    kind="re-embed": the new schema requires fresh embeddings.
    ``check_and_run_migrations()`` returns True when it encounters one of
    these so the caller can force a full rebuild (which recreates the table
    at the current SCHEMA_VERSION).
    """

    from_version: int
    to_version: int
    kind: Literal["structural", "re-embed"]
    description: str
    apply: Callable[[sqlite3.Connection, sqlite3.Connection, int], None] | None = field(
        default=None,
        repr=False,
    )


# Registry of all schema migrations in order, populated by each migration
# module's import-time registration (see the module docstring above).
MIGRATIONS: list[Migration] = []
