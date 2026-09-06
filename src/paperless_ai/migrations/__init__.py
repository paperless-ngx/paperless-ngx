"""Schema migrations for the sqlite-vec vector store.

Each migration lives in its own module here, named ``mNNNN_description.py``
(e.g. ``m0001_v1_to_v2.py`` -- a leading digit isn't a valid Python
identifier, hence the ``m`` prefix, unlike Django's own numbered migrations,
which load via a dynamic ``importlib.import_module()`` call rather than a
static import statement), and registers itself into ``MIGRATIONS`` at import
time. ``vector_store.py`` imports those modules at the bottom of the file,
purely for that registration side effect, after ``PaperlessSqliteVecVectorStore``
is fully defined -- migrations need it to implement ``apply()`` (see
``Migration`` below).

To add a new migration: add a new ``mNNNN_description.py`` module here that
imports ``PaperlessSqliteVecVectorStore`` from ``paperless_ai.vector_store``,
defines its ``apply()``, and appends a ``Migration`` to ``MIGRATIONS``; then
import that module at the bottom of ``vector_store.py`` and bump
``SCHEMA_VERSION`` there. A migration must freeze its own historical DDL for
any side table its target version depends on (``DROP TABLE IF EXISTS`` +
its own literal ``CREATE TABLE``/``CREATE INDEX`` statements) rather than
delegating to any "current schema" helper -- see ``m0001_v1_to_v2.py`` for
why and the worked example.
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
    must create every table its target schema needs in ``dst_conn`` and copy
    ``src_conn``'s rows and relevant ``index_meta`` keys into it.
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
