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
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)  # noqa: T201


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
        Group.objects.create(name=f"benchmark_group_{i}") for i in range(counts.groups)
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
