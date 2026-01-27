import math
import uuid
from time import perf_counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import reset_queries
from django.db.models import Count
from django.db.models import Q
from django.db.models import Subquery
from guardian.shortcuts import assign_perm

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import Tag
from documents.permissions import get_objects_for_user_owner_aware


class Command(BaseCommand):
    # e.g. manage.py document_perf_benchmark --documents 500000 --chunk-size 5000 --tags 40 --tags-per-doc 3 --custom-fields 6 --custom-fields-per-doc 2
    help = (
        "Seed a synthetic dataset and benchmark permission-filtered document queries "
        "for superusers vs non-superusers."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--documents",
            type=int,
            default=10000,
            help="Total documents to generate (default: 10,000)",
        )
        parser.add_argument(
            "--owner-ratio",
            type=float,
            default=0.6,
            help="Fraction owned by the benchmarked user (default: 0.6)",
        )
        parser.add_argument(
            "--unowned-ratio",
            type=float,
            default=0.1,
            help="Fraction of unowned documents (default: 0.1)",
        )
        parser.add_argument(
            "--shared-ratio",
            type=float,
            default=0.25,
            help=(
                "Fraction of other-user documents that are shared via object perms "
                "with the benchmarked user (default: 0.25)"
            ),
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=2000,
            help="Bulk create size for documents (default: 2000)",
        )
        parser.add_argument(
            "--iterations",
            type=int,
            default=3,
            help="Number of timing runs per query shape (default: 3)",
        )
        parser.add_argument(
            "--prefix",
            default="perf-benchmark",
            help="Title prefix used to mark generated documents (default: perf-benchmark)",
        )
        parser.add_argument(
            "--username",
            default="perf_user",
            help="Username of the non-superuser to benchmark (default: perf_user)",
        )
        parser.add_argument(
            "--other-username",
            default="perf_owner",
            help="Username used for documents not owned by the benchmarked user (default: perf_owner)",
        )
        parser.add_argument(
            "--super-username",
            default="perf_admin",
            help="Username of the superuser baseline (default: perf_admin)",
        )
        parser.add_argument(
            "--tags",
            type=int,
            default=0,
            help="Number of tags to create and assign (default: 0)",
        )
        parser.add_argument(
            "--tags-per-doc",
            type=int,
            default=1,
            help="How many tags to attach to each document (default: 1)",
        )
        parser.add_argument(
            "--custom-fields",
            type=int,
            default=0,
            help="Number of string custom fields to create (default: 0)",
        )
        parser.add_argument(
            "--custom-fields-per-doc",
            type=int,
            default=1,
            help="How many custom field instances per document (default: 1)",
        )
        parser.add_argument(
            "--reuse-existing",
            action="store_true",
            help="Keep previously generated documents with the given prefix instead of recreating",
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Delete previously generated documents with the given prefix and exit",
        )

    def handle(self, *args, **options):
        document_total = options["documents"]
        owner_ratio = options["owner_ratio"]
        unowned_ratio = options["unowned_ratio"]
        shared_ratio = options["shared_ratio"]
        chunk_size = options["chunk_size"]
        iterations = options["iterations"]
        prefix = options["prefix"]
        tags = options["tags"]
        tags_per_doc = options["tags_per_doc"]
        custom_fields = options["custom_fields"]
        custom_fields_per_doc = options["custom_fields_per_doc"]

        self._validate_ratios(owner_ratio, unowned_ratio)
        if tags_per_doc < 0 or custom_fields_per_doc < 0:
            raise CommandError("Per-document counts must be non-negative")

        target_user, other_user, superuser = self._ensure_users(options)

        skip_seed = False

        if options["cleanup"]:
            removed = self._cleanup(prefix)
            self.stdout.write(
                self.style.SUCCESS(f"Removed {removed} generated documents"),
            )
            return

        if not options["reuse_existing"]:
            removed = self._cleanup(prefix)
            if removed:
                self.stdout.write(f"Removed existing generated documents: {removed}")
        else:
            existing = Document.objects.filter(title__startswith=prefix).count()
            if existing:
                skip_seed = True
                self.stdout.write(
                    f"Reusing existing dataset with prefix '{prefix}': {existing} docs",
                )

        if skip_seed:
            dataset_size = Document.objects.filter(title__startswith=prefix).count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dataset ready (reused): {dataset_size} docs | prefix={prefix}",
                ),
            )
        else:
            self.stdout.write(
                f"Seeding {document_total} documents (owner_ratio={owner_ratio}, "
                f"unowned_ratio={unowned_ratio}, shared_ratio={shared_ratio})",
            )
            created_counts = self._seed_documents(
                total=document_total,
                owner_ratio=owner_ratio,
                unowned_ratio=unowned_ratio,
                shared_ratio=shared_ratio,
                chunk_size=chunk_size,
                prefix=prefix,
                target_user=target_user,
                other_user=other_user,
            )

            created_tags = []
            if tags:
                created_tags = self._seed_tags(prefix=prefix, count=tags)
                if tags_per_doc and created_tags:
                    self._assign_tags_to_documents(
                        prefix=prefix,
                        tags=created_tags,
                        tags_per_doc=tags_per_doc,
                        chunk_size=chunk_size,
                    )

            created_custom_fields = []
            if custom_fields:
                created_custom_fields = self._seed_custom_fields(prefix, custom_fields)
                if custom_fields_per_doc and created_custom_fields:
                    self._seed_custom_field_instances(
                        prefix=prefix,
                        custom_fields=created_custom_fields,
                        per_doc=custom_fields_per_doc,
                        chunk_size=chunk_size,
                    )

            dataset_size = Document.objects.filter(title__startswith=prefix).count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dataset ready: {dataset_size} docs | owned by target {created_counts['owned']} | "
                    f"owned by other {created_counts['other_owned']} | unowned {created_counts['unowned']} | "
                    f"shared-perms {created_counts['shared']} | tags {len(created_tags)} | "
                    f"custom fields {len(created_custom_fields)}",
                ),
            )

        self.stdout.write("\nRunning benchmarks...\n")
        self._run_benchmarks(
            iterations=iterations,
            target_user=target_user,
            superuser=superuser,
            prefix=prefix,
        )

    def _validate_ratios(self, owner_ratio: float, unowned_ratio: float):
        if owner_ratio < 0 or unowned_ratio < 0:
            raise CommandError("Ratios must be non-negative")
        if owner_ratio + unowned_ratio > 1:
            raise CommandError("owner-ratio + unowned-ratio cannot exceed 1.0")

    def _ensure_users(self, options):
        User = get_user_model()
        target_user, _ = User.objects.get_or_create(
            username=options["username"],
            defaults={"email": "perf_user@example.com"},
        )
        other_user, _ = User.objects.get_or_create(
            username=options["other_username"],
            defaults={"email": "perf_owner@example.com"},
        )
        superuser, _ = User.objects.get_or_create(
            username=options["super_username"],
            defaults={
                "email": "perf_admin@example.com",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        return target_user, other_user, superuser

    def _cleanup(self, prefix: str) -> int:
        docs_qs = Document.global_objects.filter(title__startswith=prefix)
        doc_count = docs_qs.count()
        if doc_count:
            docs_qs.hard_delete()

        tag_count = Tag.objects.filter(name__startswith=prefix).count()
        if tag_count:
            Tag.objects.filter(name__startswith=prefix).delete()

        cf_qs = CustomField.objects.filter(name__startswith=prefix)
        cf_count = cf_qs.count()
        if cf_count:
            cf_qs.delete()

        cfi_qs = CustomFieldInstance.global_objects.filter(
            document__title__startswith=prefix,
        )
        cfi_count = cfi_qs.count()
        if cfi_count:
            cfi_qs.hard_delete()

        return doc_count + tag_count + cf_count + cfi_count

    def _seed_documents(
        self,
        *,
        total: int,
        owner_ratio: float,
        unowned_ratio: float,
        shared_ratio: float,
        chunk_size: int,
        prefix: str,
        target_user,
        other_user,
    ) -> dict[str, int]:
        target_count = math.floor(total * owner_ratio)
        unowned_count = math.floor(total * unowned_ratio)
        other_count = total - target_count - unowned_count

        documents: list[Document] = []
        other_docs: list[Document] = []

        for idx in range(total):
            if idx < target_count:
                owner = target_user
            elif idx < target_count + other_count:
                owner = other_user
            else:
                owner = None

            doc = Document(
                owner=owner,
                title=f"{prefix}-{idx:07d}",
                mime_type="application/pdf",
                checksum=self._unique_checksum(idx),
                page_count=1,
            )

            if owner is other_user:
                other_docs.append(doc)

            documents.append(doc)

            if len(documents) >= chunk_size:
                Document.objects.bulk_create(documents, batch_size=chunk_size)
                documents.clear()

        if documents:
            Document.objects.bulk_create(documents, batch_size=chunk_size)

        shared_target = math.floor(len(other_docs) * shared_ratio)
        for doc in other_docs[:shared_target]:
            assign_perm("documents.view_document", target_user, doc)

        return {
            "owned": target_count,
            "other_owned": other_count,
            "unowned": unowned_count,
            "shared": shared_target,
        }

    def _seed_tags(self, *, prefix: str, count: int) -> list[Tag]:
        tags = [
            Tag(
                name=f"{prefix}-tag-{idx:03d}",
            )
            for idx in range(count)
        ]
        Tag.objects.bulk_create(tags, ignore_conflicts=True)
        return list(Tag.objects.filter(name__startswith=prefix))

    def _assign_tags_to_documents(
        self,
        *,
        prefix: str,
        tags: list[Tag],
        tags_per_doc: int,
        chunk_size: int,
    ):
        if not tags or tags_per_doc < 1:
            return

        rels = []
        through = Document.tags.through
        tag_ids = [t.id for t in tags]
        tag_count = len(tag_ids)
        iterator = (
            Document.objects.filter(title__startswith=prefix)
            .values_list(
                "id",
                flat=True,
            )
            .iterator()
        )

        for idx, doc_id in enumerate(iterator):
            start = idx % tag_count
            chosen = set()
            for offset in range(tags_per_doc):
                tag_id = tag_ids[(start + offset) % tag_count]
                if tag_id in chosen:
                    continue
                chosen.add(tag_id)
                rels.append(through(document_id=doc_id, tag_id=tag_id))
            if len(rels) >= chunk_size:
                through.objects.bulk_create(rels, ignore_conflicts=True)
                rels.clear()

        if rels:
            through.objects.bulk_create(rels, ignore_conflicts=True)

    def _seed_custom_fields(self, prefix: str, count: int) -> list[CustomField]:
        fields = [
            CustomField(
                name=f"{prefix}-cf-{idx:03d}",
                data_type=CustomField.FieldDataType.STRING,
            )
            for idx in range(count)
        ]
        CustomField.objects.bulk_create(fields, ignore_conflicts=True)
        return list(CustomField.objects.filter(name__startswith=prefix))

    def _seed_custom_field_instances(
        self,
        *,
        prefix: str,
        custom_fields: list[CustomField],
        per_doc: int,
        chunk_size: int,
    ):
        if not custom_fields or per_doc < 1:
            return

        instances = []
        cf_ids = [cf.id for cf in custom_fields]
        cf_count = len(cf_ids)
        iterator = (
            Document.objects.filter(title__startswith=prefix)
            .values_list(
                "id",
                flat=True,
            )
            .iterator()
        )

        for idx, doc_id in enumerate(iterator):
            start = idx % cf_count
            for offset in range(per_doc):
                cf_id = cf_ids[(start + offset) % cf_count]
                instances.append(
                    CustomFieldInstance(
                        document_id=doc_id,
                        field_id=cf_id,
                        value_text=f"val-{doc_id}-{cf_id}",
                    ),
                )
            if len(instances) >= chunk_size:
                CustomFieldInstance.objects.bulk_create(
                    instances,
                    batch_size=chunk_size,
                    ignore_conflicts=True,
                )
                instances.clear()

        if instances:
            CustomFieldInstance.objects.bulk_create(
                instances,
                batch_size=chunk_size,
                ignore_conflicts=True,
            )

    def _run_benchmarks(self, *, iterations: int, target_user, superuser, prefix: str):
        self._time_query(
            label="non-superuser: id__in(values_list flat=True)",
            iterations=iterations,
            fn=lambda: self._count_with_values_list(target_user),
        )
        self._time_query(
            label="non-superuser: id__in(Subquery(values_list))",
            iterations=iterations,
            fn=lambda: self._count_with_subquery(target_user),
        )
        self._time_query(
            label="superuser baseline",
            iterations=iterations,
            fn=lambda: Document.objects.count(),
        )
        self._time_tag_counts(iterations=iterations, prefix=prefix, user=target_user)
        self._time_custom_field_counts(
            iterations=iterations,
            prefix=prefix,
            user=target_user,
            superuser=superuser,
        )

    def _count_with_values_list(self, user) -> int:
        qs = get_objects_for_user_owner_aware(
            user,
            "documents.view_document",
            Document,
        )
        return Document.objects.filter(id__in=qs.values_list("id", flat=True)).count()

    def _count_with_subquery(self, user) -> int:
        qs = get_objects_for_user_owner_aware(
            user,
            "documents.view_document",
            Document,
        )
        subquery = Subquery(qs.values_list("id"))
        return Document.objects.filter(id__in=subquery).count()

    def _document_filter(self, user, *, use_subquery: bool):
        if user is None or getattr(user, "is_superuser", False):
            return Q(documents__deleted_at__isnull=True)

        qs = get_objects_for_user_owner_aware(
            user,
            "documents.view_document",
            Document,
        )
        ids = (
            Subquery(qs.values_list("id"))
            if use_subquery
            else qs.values_list("id", flat=True)
        )
        return Q(documents__deleted_at__isnull=True, documents__id__in=ids)

    def _tag_queryset(self, *, prefix: str, filter_q: Q):
        return Tag.objects.filter(name__startswith=prefix).annotate(
            document_count=Count("documents", filter=filter_q),
        )

    def _time_tag_counts(self, *, iterations: int, prefix: str, user):
        if not Tag.objects.filter(name__startswith=prefix).exists():
            return

        self._time_query(
            label="tag document_count (values_list)",
            iterations=iterations,
            fn=lambda: list(
                self._tag_queryset(
                    prefix=prefix,
                    filter_q=self._document_filter(user, use_subquery=False),
                ).values_list("id", "document_count"),
            ),
        )
        self._time_query(
            label="tag document_count (Subquery)",
            iterations=iterations,
            fn=lambda: list(
                self._tag_queryset(
                    prefix=prefix,
                    filter_q=self._document_filter(user, use_subquery=True),
                ).values_list("id", "document_count"),
            ),
        )

    def _time_custom_field_counts(
        self,
        *,
        iterations: int,
        prefix: str,
        user,
        superuser,
    ):
        if not CustomField.objects.filter(name__startswith=prefix).exists():
            return

        def _filter(for_user, *, use_subquery: bool):
            if for_user.is_superuser:
                return Q(fields__document__deleted_at__isnull=True)

            qs = get_objects_for_user_owner_aware(
                for_user,
                "documents.view_document",
                Document,
            )
            ids = (
                Subquery(qs.values_list("id"))
                if use_subquery
                else qs.values_list("id", flat=True)
            )
            return Q(
                fields__document__deleted_at__isnull=True,
                fields__document__id__in=ids,
            )

        def _run(filter_q):
            return list(
                CustomField.objects.filter(name__startswith=prefix)
                .annotate(
                    document_count=Count("fields", filter=filter_q),
                )
                .values_list("id", "document_count"),
            )

        self._time_query(
            label="custom fields document_count (values_list)",
            iterations=iterations,
            fn=lambda: _run(_filter(user, use_subquery=False)),
        )
        self._time_query(
            label="custom fields document_count (Subquery)",
            iterations=iterations,
            fn=lambda: _run(_filter(user, use_subquery=True)),
        )
        self._time_query(
            label="custom fields document_count superuser baseline",
            iterations=iterations,
            fn=lambda: _run(_filter(superuser, use_subquery=False)),
        )

    def _time_query(self, *, label: str, iterations: int, fn):
        durations = []
        for _ in range(iterations):
            reset_queries()
            start = perf_counter()
            fn()
            durations.append(perf_counter() - start)

        avg = sum(durations) / len(durations)
        self.stdout.write(
            f"{label}: min={min(durations):.4f}s avg={avg:.4f}s max={max(durations):.4f}s",
        )

    def _unique_checksum(self, idx: int) -> str:
        return f"{uuid.uuid4().hex}{idx:08d}"[:32]
