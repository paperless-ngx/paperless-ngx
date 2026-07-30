# Benchmark Management Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the standalone `run_benchmarks.py` / `seed_benchmark_data.py` scripts and the Postgres-only `tools/profiling` branch harness with one `manage.py benchmark` management command suite that works against all 3 supported DB backends (PostgreSQL, MariaDB, SQLite).

**Architecture:** A new `paperless_benchmark` Django app (no models/migrations) holds one management command (`benchmark`) with an `action` dispatch (`seed` / `run` / `profile` / `list-scenarios`), backed by small single-responsibility modules: `seeding.py` (tiered dataset builder), `endpoints.py` (timed API-endpoint scenarios), `db.py` (per-backend reset/explain), `harness.py` (repeat-timing + query-count capture), `scenarios.py` (pluggable profile-scenario registry), `results.py` (local JSONL history log).

**Tech Stack:** Django management commands, `documents.tests.factories` (factory-boy), `django-guardian` (permission rows), `rest_framework.test.APIClient`, `django.test.utils.CaptureQueriesContext`.

## Global Constraints

- Target branch: `tools/benchmark-management-commands`, built off current `dev` in the worktree at `C:\Users\tholmes\Documents\Coding\paperless\paperless-ngx-benchmark-commands`. All file paths below are relative to that worktree's repo root.
- No formal pytest coverage required for this work (explicitly waived — dev-only tooling, per spec §"Out of scope").
- `paperless_benchmark` is added to `INSTALLED_APPS` unconditionally (no DEBUG/env gating).
- All Django model/library imports inside `paperless_benchmark` modules are function-local (inside `def`s), not module-level — module-level code must stay import-light so the app loads cheaply during normal Django startup.
- `profile` mode runs on all 3 backends; PostgreSQL/MariaDB get real `EXPLAIN ANALYZE`, SQLite gets `EXPLAIN QUERY PLAN` labeled as plan-only.
- Benchmark results go to `benchmark_results/` at repo root, gitignored, never committed.
- Ruff formatting/lint conventions apply (line length 88, single-line imports) — run `ruff format` and `ruff check` on every new/modified file before committing.
- Reference spec: `docs/superpowers/specs/2026-07-29-benchmark-management-commands-design.md`.

---

### Task 1: App scaffold, settings registration, `.gitignore`

**Files:**

- Create: `src/paperless_benchmark/__init__.py`
- Create: `src/paperless_benchmark/apps.py`
- Create: `src/paperless_benchmark/management/__init__.py`
- Create: `src/paperless_benchmark/management/commands/__init__.py`
- Modify: `src/paperless/settings/__init__.py:128-154` (`INSTALLED_APPS` list)
- Modify: `.gitignore` (append benchmark-results entry)

**Interfaces:**

- Produces: `paperless_benchmark` importable as a Django app, with `PaperlessBenchmarkConfig` as its `AppConfig`. Later tasks add modules under this package; the management command lives at `paperless_benchmark.management.commands.benchmark`.

- [ ] **Step 1: Create the package files**

`src/paperless_benchmark/__init__.py`:

```python

```

(empty file)

`src/paperless_benchmark/apps.py`:

```python
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PaperlessBenchmarkConfig(AppConfig):
    name = "paperless_benchmark"

    verbose_name = _("Paperless benchmark")
```

`src/paperless_benchmark/management/__init__.py`:

```python

```

(empty file)

`src/paperless_benchmark/management/commands/__init__.py`:

```python

```

(empty file)

- [ ] **Step 2: Register the app in `INSTALLED_APPS`**

In `src/paperless/settings/__init__.py`, the `INSTALLED_APPS` list currently ends:

```python
    "treenode",
    *env_apps,
]
```

Change it to:

```python
    "treenode",
    "paperless_benchmark.apps.PaperlessBenchmarkConfig",
    *env_apps,
]
```

- [ ] **Step 3: Add `benchmark_results/` to `.gitignore`**

Append to `.gitignore`:

```
# Benchmark tooling output (local only, never committed)
/benchmark_results/
```

- [ ] **Step 4: Verify the app loads**

Run: `cd src && python manage.py check`
Expected: `System check identified no issues (0 silenced).` (or pre-existing warnings unrelated to this app — there must be no error mentioning `paperless_benchmark`).

- [ ] **Step 5: Commit**

```bash
git add src/paperless_benchmark/__init__.py src/paperless_benchmark/apps.py \
  src/paperless_benchmark/management/__init__.py \
  src/paperless_benchmark/management/commands/__init__.py \
  src/paperless/settings/__init__.py .gitignore
git commit -m "feat(benchmark): scaffold paperless_benchmark app"
```

---

### Task 2: Timing harness (`harness.py`)

**Files:**

- Create: `src/paperless_benchmark/harness.py`

**Interfaces:**

- Produces: `ProfileResult` (dataclass: `best_seconds: float`, `all_seconds: tuple[float, ...]`, `query_count: int`, `result: T`) and `run_profile(fn: Callable[[], T], *, repeat: int = 5) -> ProfileResult[T]`. Used by Task 8's `profile` action.

- [ ] **Step 1: Write the module**

```python
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
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd src && python manage.py shell -c "from paperless_benchmark.harness import run_profile; print(run_profile(lambda: 1 + 1, repeat=2))"`
Expected: prints a `ProfileResult(best_seconds=..., all_seconds=(...), query_count=0, result=2)` line, no traceback.

- [ ] **Step 3: Commit**

```bash
git add src/paperless_benchmark/harness.py
git commit -m "feat(benchmark): add run_profile timing harness"
```

---

### Task 3: Per-backend reset and explain (`db.py`)

**Files:**

- Create: `src/paperless_benchmark/db.py`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: `reset_benchmark_data() -> None` and `capture_explain(queryset: QuerySet) -> str`. Used by Task 8's `seed` (`--reset`) and `profile` (`--explain`) actions.

- [ ] **Step 1: Write the module**

```python
# src/paperless_benchmark/db.py
from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import connection

if TYPE_CHECKING:
    from django.db.models import QuerySet


def _reset_table_names() -> list[str]:
    from documents.models import Correspondent
    from documents.models import Document
    from documents.models import DocumentType
    from documents.models import StoragePath
    from documents.models import Tag
    from guardian.models import GroupObjectPermission
    from guardian.models import UserObjectPermission

    return [
        Document.tags.through._meta.db_table,
        Document._meta.db_table,
        Tag._meta.db_table,
        Correspondent._meta.db_table,
        DocumentType._meta.db_table,
        StoragePath._meta.db_table,
        UserObjectPermission._meta.db_table,
        GroupObjectPermission._meta.db_table,
    ]


def _delete_non_superusers() -> None:
    from django.contrib.auth import get_user_model

    get_user_model().objects.filter(is_superuser=False).delete()


def _reset_postgresql() -> None:
    tables = _reset_table_names()
    with connection.cursor() as cursor:
        cursor.execute(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE;")
    _delete_non_superusers()


def _reset_mariadb() -> None:
    # MariaDB's TRUNCATE has no CASCADE clause and refuses to truncate a
    # table referenced by a foreign key while checks are enabled, so
    # checks are disabled for the duration of the reset.
    tables = _reset_table_names()
    with connection.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        try:
            for table in tables:
                cursor.execute(f"TRUNCATE TABLE {table};")
        finally:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    _delete_non_superusers()


def _reset_sqlite() -> None:
    from documents.models import Correspondent
    from documents.models import Document
    from documents.models import DocumentType
    from documents.models import StoragePath
    from documents.models import Tag

    Document.global_objects.all().delete()
    Tag.objects.all().delete()
    Correspondent.objects.all().delete()
    DocumentType.objects.all().delete()
    StoragePath.objects.all().delete()
    _delete_non_superusers()


def reset_benchmark_data() -> None:
    """
    Remove all previously-seeded benchmark data (documents, tags,
    correspondents, document types, storage paths, guardian permission
    rows, and non-superuser users) so a fresh `benchmark seed` run starts
    from an empty slate. Dispatches per-backend because TRUNCATE syntax
    and cascade behavior differ across the 3 supported databases.
    """
    if connection.vendor == "postgresql":
        _reset_postgresql()
    elif connection.vendor == "mysql":
        # MariaDB also reports vendor == "mysql" under Django's mysql backend.
        _reset_mariadb()
    else:
        _reset_sqlite()


def capture_explain(queryset: QuerySet) -> str:
    """
    Return the query plan for `queryset` using the current backend's
    explain facility. PostgreSQL and MariaDB both support EXPLAIN ANALYZE
    (real execution stats). SQLite only supports EXPLAIN QUERY PLAN (the
    chosen plan, not real timing/row counts) -- that output is clearly
    labeled rather than silently looking equivalent to the other two
    backends' output.
    """
    sql, params = queryset.query.sql_with_params()
    with connection.cursor() as cursor:
        if connection.vendor in ("postgresql", "mysql"):
            cursor.execute(f"EXPLAIN ANALYZE {sql}", params)
            return "\n".join(str(row[0]) for row in cursor.fetchall())
        cursor.execute(f"EXPLAIN QUERY PLAN {sql}", params)
        rows = "\n".join(" | ".join(str(c) for c in row) for row in cursor.fetchall())
        return f"(plan only -- no execution stats on SQLite)\n{rows}"
```

- [ ] **Step 2: Verify it imports and runs against the local (SQLite) dev DB**

Run: `cd src && python manage.py shell -c "from paperless_benchmark.db import reset_benchmark_data; reset_benchmark_data(); print('ok')"`
Expected: prints `ok`, no traceback (safe to run even with no benchmark data present — the reset targets are idempotent no-ops on an empty set).

- [ ] **Step 3: Commit**

```bash
git add src/paperless_benchmark/db.py
git commit -m "feat(benchmark): add per-backend reset and explain helpers"
```

---

### Task 4: Tiered dataset seeding (`seeding.py`)

**Files:**

- Create: `src/paperless_benchmark/seeding.py`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: `Tier = Literal["home", "medium", "large"]`, `SeededData` (dataclass: `perf_target: User`, `perf_admin: User`, `users: tuple[User, ...]`, `groups: tuple[Group, ...]`, `documents: tuple[Document, ...]`, `tags: tuple[Tag, ...]`, `correspondents: tuple[Correspondent, ...]`, `document_types: tuple[DocumentType, ...]`, `storage_paths: tuple[StoragePath, ...]`), and `seed_benchmark_dataset(tier: Tier, *, seed: int = 42) -> SeededData`. Used by Task 8's `seed`/`run`/`profile` actions and Task 7's scenarios.

- [ ] **Step 1: Write the module**

```python
# src/paperless_benchmark/seeding.py
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Literal

if TYPE_CHECKING:
    from django.contrib.auth.models import Group
    from django.contrib.auth.models import User

    from documents.models import Correspondent
    from documents.models import Document
    from documents.models import DocumentType
    from documents.models import StoragePath
    from documents.models import Tag

Tier = Literal["home", "medium", "large"]

CHUNK_SIZE = 5_000

MIME_TYPES = (
    "application/pdf",
    "image/png",
    "image/jpeg",
    "text/plain",
)

# Ownership split for documents, mirroring the shape used in the #11950
# perf-benchmark dataset (owned-by-target / owned-by-other / unowned).
OWNED_BY_TARGET_FRACTION = 0.60
OWNED_BY_OTHER_FRACTION = 0.30
# remainder (0.10) is unowned

# Of documents owned by "other" users, the fraction explicitly shared
# (view, or view+change) with perf_target via guardian permissions --
# this is what exercises the get_user_can_change() per-row N+1 that the
# `run` endpoint benchmarks measure.
SHARED_WITH_TARGET_FRACTION = 0.5
SHARED_WITH_CHANGE_FRACTION = 0.5

# Guardian permission-row ratios measured from a real install (discussion
# #13276): 1,414 user-perm rows / 27,232 group-perm rows over 12,000
# documents. Layered across ALL owned documents for the general user/group
# pool (not just perf_target's shares), so `profile` scenarios exercise a
# realistic permission-join shape for arbitrary users, not only perf_target.
USER_PERM_ROWS_PER_DOC = 1_414 / 12_000
GROUP_PERM_ROWS_PER_DOC = 27_232 / 12_000


@dataclass(frozen=True, slots=True)
class _TierCounts:
    documents: int
    tags: int
    correspondents: int
    document_types: int
    storage_paths: int
    other_users: int
    groups: int
    tags_per_doc: tuple[int, int]


TIERS: dict[Tier, _TierCounts] = {
    "home": _TierCounts(
        documents=500,
        tags=20,
        correspondents=10,
        document_types=8,
        storage_paths=5,
        other_users=3,
        groups=2,
        tags_per_doc=(1, 3),
    ),
    "medium": _TierCounts(
        documents=20_000,
        tags=100,
        correspondents=300,
        document_types=50,
        storage_paths=20,
        other_users=10,
        groups=5,
        tags_per_doc=(2, 6),
    ),
    "large": _TierCounts(
        documents=360_000,
        tags=1_000,
        correspondents=5_000,
        document_types=300,
        storage_paths=50,
        other_users=25,
        groups=10,
        tags_per_doc=(3, 7),
    ),
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


@dataclass(frozen=True, slots=True)
class SeededData:
    perf_target: User
    perf_admin: User
    users: tuple[User, ...]
    groups: tuple[Group, ...]
    documents: tuple[Document, ...]
    tags: tuple[Tag, ...]
    correspondents: tuple[Correspondent, ...]
    document_types: tuple[DocumentType, ...]
    storage_paths: tuple[StoragePath, ...]


def _create_users_and_groups(counts: _TierCounts):
    from django.contrib.auth.models import Group

    from documents.tests.factories import UserFactory

    perf_target = UserFactory.create(username="perf_target")
    perf_admin = UserFactory.create(username="perf_admin", superuser=True)
    other_users = tuple(UserFactory.create_batch(counts.other_users))
    groups = tuple(
        Group.objects.create(name=f"benchmark_group_{i}")
        for i in range(counts.groups)
    )
    log(
        f"Created users: 1 target, 1 superuser, {len(other_users)} other, "
        f"{len(groups)} groups.",
    )
    return perf_target, perf_admin, other_users, groups


def _create_lookup_tables(counts: _TierCounts):
    from documents.models import Correspondent
    from documents.models import DocumentType
    from documents.models import StoragePath
    from documents.models import Tag
    from documents.tests.factories import CorrespondentFactory
    from documents.tests.factories import DocumentTypeFactory
    from documents.tests.factories import StoragePathFactory
    from documents.tests.factories import TagFactory

    tags = tuple(Tag.objects.bulk_create(TagFactory.build_batch(counts.tags)))
    correspondents = tuple(
        Correspondent.objects.bulk_create(
            CorrespondentFactory.build_batch(counts.correspondents),
        ),
    )
    document_types = tuple(
        DocumentType.objects.bulk_create(
            DocumentTypeFactory.build_batch(counts.document_types),
        ),
    )
    storage_paths = tuple(
        StoragePath.objects.bulk_create(
            StoragePathFactory.build_batch(counts.storage_paths),
        ),
    )
    log(
        f"Created {len(tags)} tags, {len(correspondents)} correspondents, "
        f"{len(document_types)} document types, {len(storage_paths)} storage paths.",
    )
    return tags, correspondents, document_types, storage_paths


def _assign_owner(rng: random.Random, perf_target, other_users):
    roll = rng.random()
    if roll < OWNED_BY_TARGET_FRACTION:
        return perf_target, "target"
    if roll < OWNED_BY_TARGET_FRACTION + OWNED_BY_OTHER_FRACTION:
        return rng.choice(other_users), "other"
    return None, "unowned"


def _seed_documents(
    rng: random.Random,
    counts: _TierCounts,
    tags,
    correspondents,
    document_types,
    perf_target,
    other_users,
):
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    from guardian.models import UserObjectPermission

    from documents.models import Document
    from documents.tests.factories import DocumentFactory

    tag_ids = [t.pk for t in tags]
    correspondent_ids = [c.pk for c in correspondents]
    document_type_ids = [d.pk for d in document_types]

    doc_content_type = ContentType.objects.get_for_model(Document)
    view_perm = Permission.objects.get(
        codename="view_document",
        content_type=doc_content_type,
    )
    change_perm = Permission.objects.get(
        codename="change_document",
        content_type=doc_content_type,
    )
    through_model = Document.tags.through

    documents: list[Document] = []
    remaining = counts.documents
    while remaining > 0:
        chunk_n = min(CHUNK_SIZE, remaining)
        remaining -= chunk_n

        batch = []
        owner_buckets = []
        for _ in range(chunk_n):
            doc = DocumentFactory.build(
                mime_type=rng.choice(MIME_TYPES),
                page_count=rng.randint(1, 30),
                correspondent_id=(
                    rng.choice(correspondent_ids)
                    if correspondent_ids and rng.random() < 0.8
                    else None
                ),
                document_type_id=(
                    rng.choice(document_type_ids)
                    if document_type_ids and rng.random() < 0.6
                    else None
                ),
            )
            owner, bucket = _assign_owner(rng, perf_target, other_users)
            doc.owner_id = owner.pk if owner else None
            batch.append(doc)
            owner_buckets.append(bucket)

        created = Document.objects.bulk_create(batch, batch_size=CHUNK_SIZE)

        through_rows = []
        for doc in created:
            k = rng.randint(*counts.tags_per_doc)
            for tag_id in rng.sample(tag_ids, min(k, len(tag_ids))):
                through_rows.append(through_model(document_id=doc.pk, tag_id=tag_id))
        if through_rows:
            through_model.objects.bulk_create(through_rows, batch_size=CHUNK_SIZE)

        perm_rows = []
        for doc, bucket in zip(created, owner_buckets, strict=True):
            if bucket != "other":
                continue
            if rng.random() >= SHARED_WITH_TARGET_FRACTION:
                continue
            perm_rows.append(
                UserObjectPermission(
                    permission=view_perm,
                    content_type=doc_content_type,
                    object_pk=str(doc.pk),
                    user=perf_target,
                ),
            )
            if rng.random() < SHARED_WITH_CHANGE_FRACTION:
                perm_rows.append(
                    UserObjectPermission(
                        permission=change_perm,
                        content_type=doc_content_type,
                        object_pk=str(doc.pk),
                        user=perf_target,
                    ),
                )
        if perm_rows:
            UserObjectPermission.objects.bulk_create(perm_rows, batch_size=CHUNK_SIZE)

        documents.extend(created)
        log(f"  {len(documents)}/{counts.documents} documents seeded")

    return tuple(documents)


def _grant_general_permissions(rng: random.Random, documents, users, groups) -> None:
    """
    Layer realistic (issue #13276-derived) guardian permission-row ratios
    across owned documents for the general user/group pool, so `profile`
    scenarios exercise the same permission-join shape regardless of which
    user they check visibility for (not just perf_target).
    """
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    from guardian.models import GroupObjectPermission
    from guardian.models import UserObjectPermission

    from documents.models import Document

    owned_documents = [d for d in documents if d.owner_id is not None]
    if not owned_documents or not users:
        return

    doc_content_type = ContentType.objects.get_for_model(Document)
    view_perm = Permission.objects.get(
        codename="view_document",
        content_type=doc_content_type,
    )

    n_user_perms = round(len(owned_documents) * USER_PERM_ROWS_PER_DOC)
    n_group_perms = (
        round(len(owned_documents) * GROUP_PERM_ROWS_PER_DOC) if groups else 0
    )

    user_rows = [
        UserObjectPermission(
            permission=view_perm,
            content_type=doc_content_type,
            object_pk=str(rng.choice(owned_documents).pk),
            user=rng.choice(users),
        )
        for _ in range(n_user_perms)
    ]
    if user_rows:
        UserObjectPermission.objects.bulk_create(
            user_rows,
            batch_size=CHUNK_SIZE,
            ignore_conflicts=True,
        )

    group_rows = [
        GroupObjectPermission(
            permission=view_perm,
            content_type=doc_content_type,
            object_pk=str(rng.choice(owned_documents).pk),
            group=rng.choice(groups),
        )
        for _ in range(n_group_perms)
    ]
    if group_rows:
        GroupObjectPermission.objects.bulk_create(
            group_rows,
            batch_size=CHUNK_SIZE,
            ignore_conflicts=True,
        )

    log(f"  Granted {len(user_rows)} user perms, {len(group_rows)} group perms.")


def seed_benchmark_dataset(tier: Tier, *, seed: int = 42) -> SeededData:
    """
    Build a benchmark dataset at the given scale tier: a named perf_target
    (mixed owned/shared documents) and perf_admin (superuser) for endpoint
    benchmarking, plus a general user/group pool with realistic guardian
    permission-row ratios for profile scenarios.
    """
    counts = TIERS[tier]
    rng = random.Random(seed)

    log(f"Seeding tier={tier!r}")
    perf_target, perf_admin, other_users, groups = _create_users_and_groups(counts)
    tags, correspondents, document_types, storage_paths = _create_lookup_tables(counts)
    documents = _seed_documents(
        rng,
        counts,
        tags,
        correspondents,
        document_types,
        perf_target,
        other_users,
    )
    all_users = (perf_target, *other_users)
    _grant_general_permissions(rng, documents, all_users, groups)

    log(f"Done. {len(documents)} documents seeded for tier={tier!r}.")

    return SeededData(
        perf_target=perf_target,
        perf_admin=perf_admin,
        users=all_users,
        groups=groups,
        documents=documents,
        tags=tags,
        correspondents=correspondents,
        document_types=document_types,
        storage_paths=storage_paths,
    )
```

- [ ] **Step 2: Verify a small seed run works end-to-end**

Run: `cd src && python manage.py shell -c "
from paperless_benchmark.db import reset_benchmark_data
from paperless_benchmark.seeding import seed_benchmark_dataset
reset_benchmark_data()
data = seed_benchmark_dataset('home', seed=1)
print(len(data.documents), data.perf_target.username, data.perf_admin.username, len(data.users), len(data.groups))
"`
Expected: prints `500 perf_target perf_admin 4 2` (4 = perf_target + 3 other_users) with no traceback.

- [ ] **Step 3: Commit**

```bash
git add src/paperless_benchmark/seeding.py
git commit -m "feat(benchmark): add tiered dataset seeding"
```

---

### Task 5: Results history log (`results.py`)

**Files:**

- Create: `src/paperless_benchmark/results.py`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: `append_history(entry: dict[str, Any], *, code_ref: str | None = None) -> None`. Used by Task 8's `run` and `profile` actions.

- [ ] **Step 1: Write the module**

```python
# src/paperless_benchmark/results.py
from __future__ import annotations

import json
import subprocess
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "benchmark_results"


def _current_git_ref() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def append_history(entry: dict[str, Any], *, code_ref: str | None = None) -> None:
    """
    Append one line to benchmark_results/history.jsonl -- a local-only,
    append-only, cross-session record of every `benchmark run`/`profile`
    invocation. Unlike a single overwritten snapshot file, this survives
    across sessions so a benchmarking effort picked back up days later has
    a full timeline instead of only the most recent result.
    """
    RESULTS_DIR.mkdir(exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "code_ref": code_ref or _current_git_ref(),
        **entry,
    }
    with (RESULTS_DIR / "history.jsonl").open("a") as f:
        f.write(json.dumps(record) + "\n")
```

- [ ] **Step 2: Verify it writes correctly**

Run: `cd src && python manage.py shell -c "
from paperless_benchmark.results import append_history, RESULTS_DIR
append_history({'mode': 'test', 'value': 1})
print((RESULTS_DIR / 'history.jsonl').read_text())
"`
Expected: prints one JSON line containing `"mode": "test"` and `"value": 1`. Then confirm the file is ignored: `git status --porcelain benchmark_results/` prints nothing.

- [ ] **Step 3: Commit**

```bash
git add src/paperless_benchmark/results.py
git commit -m "feat(benchmark): add local JSONL results history log"
```

---

### Task 6: Endpoint timing scenarios (`endpoints.py`)

**Files:**

- Create: `src/paperless_benchmark/endpoints.py`

**Interfaces:**

- Consumes: nothing from earlier tasks (takes plain `User` instances as arguments).
- Produces: `EndpointTiming` (dataclass: `user_label: str`, `endpoint_name: str`, `query_count: int`, `min_ms: float`, `median_ms: float`, `max_ms: float`) and `run_endpoint_benchmarks(*, perf_target, perf_admin, repeat: int) -> list[EndpointTiming]`. Used by Task 8's `run` action.

- [ ] **Step 1: Write the module**

```python
# src/paperless_benchmark/endpoints.py
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import User

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


def _timed_requests(client, url: str, n: int) -> list[float]:
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


def _query_count(client, url: str) -> int:
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
```

- [ ] **Step 2: Verify against the home-tier data seeded in Task 4**

Run: `cd src && python manage.py shell -c "
from django.contrib.auth import get_user_model
from paperless_benchmark.endpoints import run_endpoint_benchmarks
User = get_user_model()
target = User.objects.get(username='perf_target')
admin = User.objects.get(username='perf_admin')
results = run_endpoint_benchmarks(perf_target=target, perf_admin=admin, repeat=2)
for r in results:
    print(r)
"`
Expected: 6 `EndpointTiming(...)` lines (2 users × 3 endpoints), no traceback.

- [ ] **Step 3: Commit**

```bash
git add src/paperless_benchmark/endpoints.py
git commit -m "feat(benchmark): add timed API endpoint scenarios"
```

---

### Task 7: Pluggable profile-scenario registry (`scenarios.py`)

**Files:**

- Create: `src/paperless_benchmark/scenarios.py`

**Interfaces:**

- Consumes: `SeededData` from Task 4 (`paperless_benchmark.seeding.SeededData`).
- Produces: `Scenario` (dataclass: `name: str`, `describe: str`, `run: Callable[[SeededData], Any]`, `queryset_for_explain: Callable[[SeededData], QuerySet] | None`), `register(scenario: Scenario) -> None`, `get(name: str) -> Scenario` (raises `CommandError` on unknown name), `all_scenarios() -> tuple[Scenario, ...]`. Registers two scenarios ported from `tools/profiling`'s guardian-permission investigation. Used by Task 8's `profile` and `list-scenarios` actions.

- [ ] **Step 1: Write the module**

```python
# src/paperless_benchmark/scenarios.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from paperless_benchmark.seeding import SeededData


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    describe: str
    run: Callable[[SeededData], Any]
    queryset_for_explain: Callable[[SeededData], QuerySet] | None = None


_SCENARIOS: dict[str, Scenario] = {}


def register(scenario: Scenario) -> None:
    _SCENARIOS[scenario.name] = scenario


def get(name: str) -> Scenario:
    from django.core.management.base import CommandError

    try:
        return _SCENARIOS[name]
    except KeyError:
        available = ", ".join(sorted(_SCENARIOS)) or "(none registered)"
        raise CommandError(
            f"Unknown benchmark scenario {name!r}. Available: {available}",
        ) from None


def all_scenarios() -> tuple[Scenario, ...]:
    return tuple(_SCENARIOS.values())


def _guardian_visibility_query_run(data: SeededData) -> list[int]:
    from documents.models import Document
    from documents.permissions import get_objects_for_user_owner_aware

    user = data.users[0]
    return list(
        get_objects_for_user_owner_aware(
            user,
            "documents.view_document",
            Document,
        ).values_list("id", flat=True),
    )


def _guardian_visibility_query_queryset(data: SeededData) -> QuerySet:
    from documents.models import Document
    from documents.permissions import get_objects_for_user_owner_aware

    user = data.users[0]
    return get_objects_for_user_owner_aware(user, "documents.view_document", Document)


register(
    Scenario(
        name="guardian_visibility_query",
        describe=(
            "Document-visibility queryset for a user with mixed owned/shared "
            "documents -- exercises documents.permissions."
            "get_objects_for_user_owner_aware's guardian permission join."
        ),
        run=_guardian_visibility_query_run,
        queryset_for_explain=_guardian_visibility_query_queryset,
    ),
)


def _permitted_document_ids_run(data: SeededData) -> list[int]:
    from documents.models import Document
    from documents.permissions import permitted_document_ids

    user = data.users[0]
    return list(
        Document.objects.filter(id__in=permitted_document_ids(user)).values_list(
            "id",
            flat=True,
        ),
    )


def _permitted_document_ids_queryset(data: SeededData) -> QuerySet:
    from documents.models import Document
    from documents.permissions import permitted_document_ids

    user = data.users[0]
    return Document.objects.filter(id__in=permitted_document_ids(user))


register(
    Scenario(
        name="permitted_document_ids",
        describe=(
            "Document-visibility query built from documents.permissions."
            "permitted_document_ids -- the resolved-ID-set alternative to "
            "guardian_visibility_query, for side-by-side comparison."
        ),
        run=_permitted_document_ids_run,
        queryset_for_explain=_permitted_document_ids_queryset,
    ),
)
```

- [ ] **Step 2: Verify registration and lookup**

Run: `cd src && python manage.py shell -c "
from paperless_benchmark.scenarios import all_scenarios, get
print([s.name for s in all_scenarios()])
print(get('guardian_visibility_query').describe)
"`
Expected: prints `['guardian_visibility_query', 'permitted_document_ids']` then the describe string, no traceback.

- [ ] **Step 3: Verify unknown-scenario error**

Run: `cd src && python manage.py shell -c "
from paperless_benchmark.scenarios import get
get('nonexistent')
"`
Expected: raises `CommandError: Unknown benchmark scenario 'nonexistent'. Available: guardian_visibility_query, permitted_document_ids`.

- [ ] **Step 4: Commit**

```bash
git add src/paperless_benchmark/scenarios.py
git commit -m "feat(benchmark): add pluggable profile-scenario registry"
```

---

### Task 8: The `benchmark` management command

**Files:**

- Create: `src/paperless_benchmark/management/commands/benchmark.py`

**Interfaces:**

- Consumes: `reset_benchmark_data`, `capture_explain` (Task 3); `seed_benchmark_dataset` (Task 4); `append_history` (Task 5); `run_endpoint_benchmarks` (Task 6); `run_profile` (Task 2); `get`, `all_scenarios` (Task 7).
- Produces: the `manage.py benchmark {seed,run,profile,list-scenarios}` CLI.

- [ ] **Step 1: Write the command**

```python
# src/paperless_benchmark/management/commands/benchmark.py
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.core.management.base import CommandParser


class Command(BaseCommand):
    help = "Seed, run, and profile paperless-ngx performance benchmarks."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "action",
            choices=["seed", "run", "profile", "list-scenarios"],
            help="Which benchmark action to perform.",
        )
        parser.add_argument(
            "scenario",
            nargs="?",
            default=None,
            help="Scenario name (required for `profile`; see `list-scenarios`).",
        )
        parser.add_argument(
            "--tier",
            choices=["home", "medium", "large"],
            default="medium",
            help="Dataset scale tier for `seed` and `profile` (default: medium).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            default=False,
            help="For `seed`: truncate existing benchmark data first.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="RNG seed for reproducible datasets (default: 42).",
        )
        parser.add_argument(
            "--repeat",
            type=int,
            default=5,
            help="Number of timed repetitions for `run`/`profile` (default: 5).",
        )
        parser.add_argument(
            "--label",
            default="baseline",
            help="Free-text tag for a `run`, printed and recorded in history only.",
        )
        parser.add_argument(
            "--explain",
            action="store_true",
            default=False,
            help="For `profile`: also capture and print the query plan.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        action = options["action"]
        if action == "seed":
            self._handle_seed(options)
        elif action == "run":
            self._handle_run(options)
        elif action == "profile":
            self._handle_profile(options)
        else:
            self._handle_list_scenarios()

    def _handle_seed(self, options: dict[str, Any]) -> None:
        from paperless_benchmark.db import reset_benchmark_data
        from paperless_benchmark.seeding import seed_benchmark_dataset

        if options["reset"]:
            self.stdout.write("Resetting existing benchmark data...")
            reset_benchmark_data()

        data = seed_benchmark_dataset(options["tier"], seed=options["seed"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded tier={options['tier']!r}: {len(data.documents)} documents, "
                f"{len(data.users)} users, {len(data.groups)} groups.",
            ),
        )

    def _handle_run(self, options: dict[str, Any]) -> None:
        from django.contrib.auth import get_user_model

        from paperless_benchmark.endpoints import run_endpoint_benchmarks
        from paperless_benchmark.results import append_history

        user_model = get_user_model()
        try:
            perf_target = user_model.objects.get(username="perf_target")
            perf_admin = user_model.objects.get(username="perf_admin")
        except user_model.DoesNotExist as e:
            raise CommandError(
                "No benchmark dataset found. Run `manage.py benchmark seed` first.",
            ) from e

        results = run_endpoint_benchmarks(
            perf_target=perf_target,
            perf_admin=perf_admin,
            repeat=options["repeat"],
        )

        self.stdout.write(f"# label={options['label']} repeat={options['repeat']}")
        self.stdout.write(
            f"{'user':7s} {'endpoint':20s} {'queries':>8s} "
            f"{'min_ms':>9s} {'median_ms':>10s} {'max_ms':>9s}",
        )
        for r in results:
            self.stdout.write(
                f"{r.user_label:7s} {r.endpoint_name:20s} {r.query_count:8d} "
                f"{r.min_ms:9.1f} {r.median_ms:10.1f} {r.max_ms:9.1f}",
            )
            append_history(
                {
                    "mode": "run",
                    "label": options["label"],
                    "user": r.user_label,
                    "endpoint": r.endpoint_name,
                    "query_count": r.query_count,
                    "min_ms": r.min_ms,
                    "median_ms": r.median_ms,
                    "max_ms": r.max_ms,
                },
            )

    def _handle_profile(self, options: dict[str, Any]) -> None:
        from paperless_benchmark.db import capture_explain
        from paperless_benchmark.harness import run_profile
        from paperless_benchmark.results import append_history
        from paperless_benchmark.scenarios import get as get_scenario
        from paperless_benchmark.seeding import seed_benchmark_dataset

        if not options["scenario"]:
            raise CommandError(
                "`profile` requires a scenario name; see `list-scenarios`.",
            )

        scenario = get_scenario(options["scenario"])
        data = seed_benchmark_dataset(options["tier"], seed=options["seed"])

        profile = run_profile(lambda: scenario.run(data), repeat=options["repeat"])
        self.stdout.write(
            f"{scenario.name}: best={profile.best_seconds:.4f}s "
            f"queries={profile.query_count} (tier={options['tier']})",
        )

        if options["explain"] and scenario.queryset_for_explain is not None:
            plan = capture_explain(scenario.queryset_for_explain(data))
            self.stdout.write(plan)

        append_history(
            {
                "mode": "profile",
                "scenario": scenario.name,
                "tier": options["tier"],
                "best_seconds": profile.best_seconds,
                "query_count": profile.query_count,
            },
        )

    def _handle_list_scenarios(self) -> None:
        from paperless_benchmark.scenarios import all_scenarios

        for scenario in all_scenarios():
            self.stdout.write(f"{scenario.name}: {scenario.describe}")
```

- [ ] **Step 2: Verify `list-scenarios`**

Run: `cd src && python manage.py benchmark list-scenarios`
Expected: two lines, `guardian_visibility_query: ...` and `permitted_document_ids: ...`.

- [ ] **Step 3: Verify `seed` end-to-end (reset + home tier)**

Run: `cd src && python manage.py benchmark seed --tier home --reset`
Expected: a `Resetting existing benchmark data...` line followed by `Seeded tier='home': 500 documents, 4 users, 2 groups.` in green.

- [ ] **Step 4: Verify `run` against the just-seeded data**

Run: `cd src && python manage.py benchmark run --repeat 2 --label smoke-test`
Expected: a `# label=smoke-test repeat=2` header, a column header row, and 6 data rows (2 users × 3 endpoints). Then confirm history was recorded: `cd .. && python -c "print(open('benchmark_results/history.jsonl').read().count(chr(10)))"` prints a number ≥ 6.

- [ ] **Step 5: Verify `profile` against the just-seeded data, with `--explain`**

Run: `cd src && python manage.py benchmark profile guardian_visibility_query --tier home --repeat 2 --explain`
Expected: a `guardian_visibility_query: best=...s queries=... (tier=home)` line, followed by either `(plan only -- no execution stats on SQLite)` plus plan rows (if running against the default SQLite dev DB) or real `EXPLAIN ANALYZE` output (if `PAPERLESS_DBENGINE` points at Postgres/MariaDB).

- [ ] **Step 6: Verify the unknown-action and missing-scenario error paths**

Run: `cd src && python manage.py benchmark profile`
Expected: `CommandError: profile requires a scenario name; see list-scenarios.` (Django prints this as an error, non-zero exit.)

- [ ] **Step 7: Commit**

```bash
git add src/paperless_benchmark/management/commands/benchmark.py
git commit -m "feat(benchmark): add manage.py benchmark command (seed/run/profile/list-scenarios)"
```

---

### Task 9: Remove superseded root scripts, final ruff pass

**Files:**

- Delete: `run_benchmarks.py` (repo root)
- Delete: `seed_benchmark_data.py` (repo root)

**Interfaces:** none — cleanup only.

- [ ] **Step 1: Confirm nothing else references the root scripts**

Run: `grep -rn "run_benchmarks\|seed_benchmark_data" --include="*.py" --include="*.md" --include="*.yml" --include="*.yaml" . | grep -v "^./docs/superpowers/"`
Expected: no output (no CI workflow, doc, or script references them outside the design/plan docs).

- [ ] **Step 2: Delete the superseded scripts**

```bash
git rm run_benchmarks.py seed_benchmark_data.py
```

- [ ] **Step 3: Run ruff over every new file**

Run: `ruff format src/paperless_benchmark/ && ruff check src/paperless_benchmark/ --fix`
Expected: `ruff format` reports files left unchanged or reformatted cleanly; `ruff check` reports no remaining issues. If `ruff check` flags anything `--fix` can't resolve, fix it manually and re-run both commands until clean.

- [ ] **Step 4: Final end-to-end smoke test on a clean reset**

Run: `cd src && python manage.py benchmark seed --tier home --reset && python manage.py benchmark run --repeat 1 --label final-check && python manage.py benchmark profile permitted_document_ids --tier home --repeat 1`
Expected: all three commands complete without traceback, matching the output shapes verified in Task 8.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(benchmark): remove superseded root benchmark scripts"
```

---

### Task 10: Fix reset and permission quirks

**Files:**

- Modify: `src/paperless_benchmark/db.py` (`_delete_non_superusers` → `_delete_all_users_and_groups`)
- Modify: `src/paperless_benchmark/seeding.py` (`_create_users_and_groups`)

**Interfaces:**

- Consumes: nothing new.
- Produces: `reset_benchmark_data()` now fully reverses a `seed`, including `perf_admin` and all benchmark groups. `seed_benchmark_dataset(...)` now leaves `perf_target` able to hit `/api/documents/` and `/api/tags/` without a manual permission grant.

**Background:** Tasks 6, 8, and 9's real verification runs all independently hit the same two rough edges: (1) `reset_benchmark_data()`'s `_delete_non_superusers()` only deletes non-superuser users, so the `perf_admin` superuser (and `benchmark_group_*` groups) survive a `--reset` and collide on re-seed with a `UNIQUE constraint failed` error; (2) `perf_target` only gets per-object guardian permissions during seeding, but DRF's `PaperlessObjectPermissions` class checks Django's _model-level_ `view`/`add`/`change` permission before guardian's object-level checks are ever consulted, so `perf_target` gets a blanket `403` on list endpoints regardless of which documents it can actually see. This tool only ever runs against a disposable benchmark database (never a real production install — see the module docstrings from the original standalone scripts this was ported from), so a full wipe on reset is safe and intentional here.

- [ ] **Step 1: Fix `reset_benchmark_data()` to fully clear users and groups**

In `src/paperless_benchmark/db.py`, replace:

```python
def _delete_non_superusers() -> None:
    from django.contrib.auth import get_user_model

    get_user_model().objects.filter(is_superuser=False).delete()
```

with:

```python
def _delete_all_users_and_groups() -> None:
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    get_user_model().objects.all().delete()
    Group.objects.all().delete()
```

Then update all three call sites (`_reset_postgresql`, `_reset_mariadb`, `_reset_sqlite`) to call `_delete_all_users_and_groups()` instead of `_delete_non_superusers()`.

- [ ] **Step 2: Grant `perf_target` model-level permissions during seeding**

In `src/paperless_benchmark/seeding.py`, add a new helper and call it right after creating `perf_target` inside `_create_users_and_groups`:

```python
def _grant_model_level_permissions(user) -> None:
    """
    Grant perf_target Django model-level view/add/change permissions on
    Document and Tag, on top of the per-object guardian grants seeding
    creates elsewhere. DRF's PaperlessObjectPermissions checks model-level
    permissions before guardian's object-level ones are ever consulted, so
    without this perf_target gets a blanket 403 on /api/documents/ and
    /api/tags/ regardless of which documents guardian says it can see.
    """
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    from documents.models import Document
    from documents.models import Tag

    for model in (Document, Tag):
        content_type = ContentType.objects.get_for_model(model)
        codenames = [
            f"{action}_{model._meta.model_name}"
            for action in ("view", "add", "change")
        ]
        perms = Permission.objects.filter(
            content_type=content_type,
            codename__in=codenames,
        )
        user.user_permissions.add(*perms)
```

Update `_create_users_and_groups` so it calls this right after creating `perf_target`:

```python
def _create_users_and_groups(counts: _TierCounts):
    from django.contrib.auth.models import Group

    from documents.tests.factories import UserFactory

    perf_target = UserFactory.create(username="perf_target")
    _grant_model_level_permissions(perf_target)
    perf_admin = UserFactory.create(username="perf_admin", superuser=True)
    other_users = tuple(UserFactory.create_batch(counts.other_users))
    groups = tuple(
        Group.objects.create(name=f"benchmark_group_{i}")
        for i in range(counts.groups)
    )
    log(
        f"Created users: 1 target, 1 superuser, {len(other_users)} other, "
        f"{len(groups)} groups.",
    )
    return perf_target, perf_admin, other_users, groups
```

- [ ] **Step 3: Verify the full chain works with no manual workarounds**

Run (against the local/VM dev DB, resetting first to include any stale `perf_admin`/groups from earlier manual testing):

```
cd src && python manage.py benchmark seed --tier home --reset
python manage.py benchmark run --repeat 1 --label quirk-fix-check
python manage.py benchmark profile guardian_visibility_query --repeat 1
python manage.py benchmark seed --tier home --reset
```

Expected: every command succeeds with no traceback and no manual `manage.py shell` permission-granting or DB-file-deletion step — in particular, `run`'s `documents_default`/`documents_page50`/`tags_all` rows for the `target` user must show `200`-driven real query counts (not a 403), and the second `seed --reset` must succeed cleanly (proving `perf_admin` and groups were actually cleared by the first reset).

- [ ] **Step 4: Commit**

```bash
git add src/paperless_benchmark/db.py src/paperless_benchmark/seeding.py
git commit -m "fix(benchmark): fully clear users/groups on reset, grant perf_target model perms"
```

---

### Task 11: `paperless-benchmarking` skill

**Files:**

- Create: `.claude/skills/paperless-benchmarking/SKILL.md`

**Interfaces:** none — documentation only.

**Background:** This is a project skill (committed on `tools/benchmark-management-commands`, travels with the branch) that teaches an agent how to use the `manage.py benchmark` tool, the branch/merge-back workflow for performance investigations, and how to judge when a one-off profiling scenario is worth turning into a permanent registered scenario. This branch is intended to stay merged-up-to-date with `dev`; new performance investigations fork a fresh branch _from this branch_ (not from `dev`), do their investigation there, and PR only newly-useful scenarios back into `tools/benchmark-management-commands` — the investigation branch itself never merges into `dev`/production.

- [ ] **Step 1: Write the skill file**

```markdown
---
name: paperless-benchmarking
description: Use when profiling paperless-ngx performance, running `manage.py benchmark`, investigating a slow query or endpoint, or deciding whether a profiling finding should become a permanent registered scenario. Covers command reference, the fork/merge-back branch workflow for perf investigations, and how to read query-plan output.
---

# Paperless-ngx Benchmarking

This repo has a built-in benchmarking/profiling tool: `manage.py benchmark`, in
the `paperless_benchmark` Django app. It replaces ad hoc standalone scripts —
use it instead of writing new one-off seed/timing scripts.

## Command reference
```

manage.py benchmark seed --tier {home,medium,large} [--reset] [--seed N]
manage.py benchmark run --repeat 5 [--label baseline]
manage.py benchmark profile <scenario_name> [--repeat 5] [--explain]
manage.py benchmark list-scenarios

```

- **`seed`** builds a realistic dataset at one of three scales: `home` (500
  documents — fast, use this for iteration), `medium` (20,000), `large`
  (360,000 — matches the scale reported in real large-install bug reports;
  slow, only use it when a finding needs confirming at real scale). `--reset`
  wipes any previously-seeded benchmark data first — always pass it unless you
  specifically want to layer more data onto an existing seed. `seed` creates
  two named users, `perf_target` (mixed owned/shared documents, realistic
  guardian permission grants) and `perf_admin` (superuser), plus a general
  user/group pool with realistic permission-row ratios.
- **`run`** times the 3 built-in API endpoint benchmarks
  (`/api/documents/`, `/api/documents/?page_size=50`, `/api/tags/`) for both
  `perf_target` and `perf_admin`, reporting min/median/max wall-clock and SQL
  query count. Requires `seed` to have already run — it reuses that data, it
  does not seed its own.
- **`profile`** times one named scenario from the registry (see
  `list-scenarios`) via best-of-N repeat timing and SQL query count, against
  `perf_target`. `--explain` additionally captures and prints the query plan:
  real `EXPLAIN ANALYZE` execution stats on PostgreSQL/MariaDB, or
  `EXPLAIN QUERY PLAN` (plan only, no real timing/row counts — clearly labeled
  as such) on SQLite. Like `run`, `profile` requires `seed` to have already
  run — it does not seed its own data either.
- Every `run`/`profile` invocation appends a JSON line to
  `benchmark_results/history.jsonl` at the repo root (local-only, gitignored —
  never commit this file). Use it to compare a `before`/`after` pair across
  two invocations without hand-copying numbers.
- Full chain example: `seed --reset` once, then `run` and `profile` as many
  times as you want against that same seeded data — no need to reseed between
  them.

## Adding a new scenario

A "scenario" is a named, registered query/operation that `profile` can time
and explain. To add one, edit `src/paperless_benchmark/scenarios.py`: write a
`_<name>_run(user)` function (returns whatever `run_profile` should time) and
optionally a `_<name>_queryset(user)` function (returns the `QuerySet` for
`--explain` to analyze), then `register(Scenario(name=..., describe=...,
run=..., queryset_for_explain=...))` at module level. Both functions receive
the already-seeded `perf_target` user — they should not seed their own data.

## Branch workflow

`tools/benchmark-management-commands` is a **long-lived tooling branch**, not
a feature branch that gets merged and closed:

1. It is periodically brought up to date with `dev` (merge `dev` into it) so
   the tooling doesn't drift from the schema/codebase it profiles. Do this
   before starting a new investigation if it's been a while since the last
   sync.
2. **Every performance investigation forks its own branch from
   `tools/benchmark-management-commands`** (not from `dev`). Do the
   investigation there: write throwaway profiling code, try fixes, capture
   before/after numbers.
3. **That investigation branch never merges into `dev` or production.** Its
   only job is to produce evidence and, optionally, a reusable scenario.
4. If the investigation turns up a scenario worth keeping permanently (see
   "When to graduate a scenario" below), open a PR that adds **just that
   scenario** back into `tools/benchmark-management-commands` — not the rest
   of the investigation branch's throwaway code.
5. Any actual production fix the investigation motivates (e.g. an ORM query
   change) goes into its own normal feature branch off `dev`, following the
   project's regular contribution process — profiling evidence informs that
   PR's description, but the profiling code itself does not travel with it.

## Reading query-plan output

- **PostgreSQL/MariaDB** `EXPLAIN ANALYZE`: look for `Seq Scan` on a large
  table (missing index), a large gap between `rows=N` (planner's estimate)
  and the actual row count in parentheses (stale statistics or a bad
  cardinality estimate), and nested-loop joins driven by an outer relation
  with many rows (usually the N+1 pattern this tool exists to catch).
- **SQLite** `EXPLAIN QUERY PLAN`: no real timing/row-count data, only the
  chosen access path (`SCAN` vs `SEARCH`, which index if any). Useful for
  confirming an index is even being considered, not for judging real-world
  cost — corroborate any SQLite finding against Postgres/MariaDB before
  trusting it, since planner behavior differs meaningfully between them.
- Compare query **count**, not just timing, between before/after: a fix that
  keeps the same wall-clock time but drops query count from O(n) to O(1) is
  still a real, durable improvement — timing alone is noisy and
  environment-dependent, query count is not.

## When to graduate a one-off finding into a permanent scenario

Register a scenario (rather than leaving it as throwaway code on the
investigation branch) when **both** are true:
- The query pattern is one this codebase is likely to regress on again (e.g.
  it involves a permission-check join, a bulk operation, or anything else
  with an easy-to-reintroduce N+1) — not a one-time fluke specific to this
  investigation.
- Re-running it later, against a fresh seed, would still produce a
  meaningful signal (it doesn't depend on investigation-specific throwaway
  data or a fix that's already permanently landed and can't regress the same
  way).

If a finding doesn't meet both bars, keep it as disposable code on the
investigation branch and let the branch's evidence (captured in the PR
description of whatever production fix it motivates) be the permanent
record instead.
```

- [ ] **Step 2: Verify the skill file is well-formed**

Run: `python -c "import re, pathlib; text = pathlib.Path('.claude/skills/paperless-benchmarking/SKILL.md').read_text(); m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL); assert m, 'no frontmatter found'; assert 'name: paperless-benchmarking' in m.group(1); assert 'description:' in m.group(1); print('frontmatter OK')"`
Expected: prints `frontmatter OK`, no traceback.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/paperless-benchmarking/SKILL.md
git commit -m "docs(benchmark): add paperless-benchmarking skill"
```

---

## Post-plan notes

- `tools/profiling` (the source branch this work was ported from) is left untouched — not merged, not deleted.
- Large-tier (`--tier large`, 360k documents) and MariaDB/PostgreSQL-specific verification are not exercised by the steps above (which use the fast, local `home` tier against whatever DB backend the dev environment defaults to — typically SQLite). Before relying on this tooling for a real perf investigation, run at least one `--tier large` seed against Postgres and MariaDB using the project's VM test setup (see `CLAUDE.md`'s "Running tests" section for the SSH/worktree pattern) to confirm `_reset_mariadb`'s `TRUNCATE`/`FOREIGN_KEY_CHECKS` sequencing and the `EXPLAIN ANALYZE` dispatch behave as expected outside SQLite.
- Task 9 found the two root scripts (`run_benchmarks.py`, `seed_benchmark_data.py`) never existed in the `tools/benchmark-management-commands` worktree — they were untracked files only in the unrelated original checkout this branch's worktree was created alongside. No further action needed; there is nothing left to delete.
