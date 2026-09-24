from typing import Any

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.db.models import Case
from django.db.models import Count
from django.db.models import IntegerField
from django.db.models import Max
from django.db.models import Sum
from django.db.models import When
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from drf_spectacular.utils import inline_serializer
from rest_framework import parsers
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import Document
from documents.models import DocumentType
from documents.models import SavedView
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow
from documents.permissions import ViewDocumentsPermissions
from documents.permissions import get_objects_for_user_owner_aware
from documents.permissions import has_global_statistics_permission
from documents.permissions import permitted_document_ids
from documents.serialisers.base import DocumentSelectionSerializer
from documents.serialisers.documents import DocumentSerializer
from documents.serialisers.documents import SearchResultSerializer
from documents.serialisers.metadata import CorrespondentSerializer
from documents.serialisers.metadata import CustomFieldSerializer
from documents.serialisers.metadata import DocumentTypeSerializer
from documents.serialisers.metadata import StoragePathSerializer
from documents.serialisers.metadata import TagSerializer
from documents.serialisers.saved_views import SavedViewSerializer
from documents.serialisers.workflows import WorkflowSerializer
from documents.versioning import annotate_effective_content
from paperless.serialisers import GroupSerializer
from paperless.serialisers import UserSerializer
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.serialisers import MailAccountSerializer
from paperless_mail.serialisers import MailRuleSerializer

from .base import _MAX_QUERY_LENGTH
from .base import DocumentSelectionMixin
from .base import PassUserMixin


@extend_schema_view(
    post=extend_schema(
        description="Get selection data for the selected documents",
        responses={
            (200, "application/json"): inline_serializer(
                name="SelectionData",
                fields={
                    "selected_correspondents": serializers.ListSerializer(
                        child=inline_serializer(
                            name="CorrespondentCounts",
                            fields={
                                "id": serializers.IntegerField(),
                                "document_count": serializers.IntegerField(),
                            },
                        ),
                    ),
                    "selected_tags": serializers.ListSerializer(
                        child=inline_serializer(
                            name="TagCounts",
                            fields={
                                "id": serializers.IntegerField(),
                                "document_count": serializers.IntegerField(),
                            },
                        ),
                    ),
                    "selected_document_types": serializers.ListSerializer(
                        child=inline_serializer(
                            name="DocumentTypeCounts",
                            fields={
                                "id": serializers.IntegerField(),
                                "document_count": serializers.IntegerField(),
                            },
                        ),
                    ),
                    "selected_storage_paths": serializers.ListSerializer(
                        child=inline_serializer(
                            name="StoragePathCounts",
                            fields={
                                "id": serializers.IntegerField(),
                                "document_count": serializers.IntegerField(),
                            },
                        ),
                    ),
                    "selected_custom_fields": serializers.ListSerializer(
                        child=inline_serializer(
                            name="CustomFieldCounts",
                            fields={
                                "id": serializers.IntegerField(),
                                "document_count": serializers.IntegerField(),
                            },
                        ),
                    ),
                },
            ),
        },
    ),
)
class SelectionDataView(DocumentSelectionMixin, GenericAPIView[Any]):
    permission_classes = (IsAuthenticated, ViewDocumentsPermissions)
    serializer_class = DocumentSelectionSerializer
    parser_classes = (parsers.MultiPartParser, parsers.JSONParser)

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = self._resolve_document_ids(
            user=request.user,
            validated_data=serializer.validated_data,
        )
        permitted_documents = Document.objects.filter(
            id__in=permitted_document_ids(request.user),
        )
        if permitted_documents.filter(pk__in=ids).count() != len(ids):
            return HttpResponseForbidden("Insufficient permissions")

        correspondents = Correspondent.objects.annotate(
            document_count=Count(
                Case(When(documents__id__in=ids, then=1), output_field=IntegerField()),
            ),
        )

        tags = Tag.objects.annotate(
            document_count=Count(
                Case(When(documents__id__in=ids, then=1), output_field=IntegerField()),
            ),
        )

        types = DocumentType.objects.annotate(
            document_count=Count(
                Case(When(documents__id__in=ids, then=1), output_field=IntegerField()),
            ),
        )

        storage_paths = StoragePath.objects.annotate(
            document_count=Count(
                Case(When(documents__id__in=ids, then=1), output_field=IntegerField()),
            ),
        )

        custom_fields = CustomField.objects.annotate(
            document_count=Count(
                Case(
                    When(
                        fields__document__id__in=ids,
                        then=1,
                    ),
                    output_field=IntegerField(),
                ),
            ),
        )

        r = Response(
            {
                "selected_correspondents": [
                    {"id": t.id, "document_count": t.document_count}
                    for t in correspondents
                ],
                "selected_tags": [
                    {"id": t.id, "document_count": t.document_count} for t in tags
                ],
                "selected_document_types": [
                    {"id": t.id, "document_count": t.document_count} for t in types
                ],
                "selected_storage_paths": [
                    {"id": t.id, "document_count": t.document_count}
                    for t in storage_paths
                ],
                "selected_custom_fields": [
                    {"id": t.id, "document_count": t.document_count}
                    for t in custom_fields
                ],
            },
        )

        return r


@extend_schema_view(
    get=extend_schema(
        description="Get a list of all available tags",
        parameters=[
            OpenApiParameter(
                name="term",
                required=False,
                type=str,
                description="Term to search for",
            ),
            OpenApiParameter(
                name="limit",
                required=False,
                type=int,
                description="Number of completions to return",
            ),
        ],
        responses={
            (200, "application/json"): serializers.ListSerializer(
                child=serializers.CharField(),
            ),
        },
    ),
)
class SearchAutoCompleteView(GenericAPIView[Any]):
    permission_classes = (IsAuthenticated, ViewDocumentsPermissions)

    def get(self, request, format=None):
        user = self.request.user if hasattr(self.request, "user") else None

        if "term" in request.query_params:
            term = request.query_params["term"].strip()
        else:
            return HttpResponseBadRequest("Term required")

        if "limit" in request.query_params:
            limit = int(request.query_params["limit"])
            if limit <= 0:
                return HttpResponseBadRequest("Invalid limit")
        else:
            limit = 10

        from documents.search import get_backend

        return Response(get_backend().autocomplete(term, limit, user))


@extend_schema_view(
    get=extend_schema(
        description="Global search",
        parameters=[
            OpenApiParameter(
                name="query",
                required=True,
                type=str,
                description="Query to search for",
            ),
            OpenApiParameter(
                name="db_only",
                required=False,
                type=bool,
                description="Search only the database",
            ),
        ],
        responses={
            (200, "application/json"): inline_serializer(
                name="SearchResult",
                fields={
                    "total": serializers.IntegerField(),
                    "documents": DocumentSerializer(many=True),
                    "saved_views": SavedViewSerializer(many=True),
                    "tags": TagSerializer(many=True),
                    "correspondents": CorrespondentSerializer(many=True),
                    "document_types": DocumentTypeSerializer(many=True),
                    "storage_paths": StoragePathSerializer(many=True),
                    "users": UserSerializer(many=True),
                    "groups": GroupSerializer(many=True),
                    "mail_rules": MailRuleSerializer(many=True),
                    "mail_accounts": MailAccountSerializer(many=True),
                    "workflows": WorkflowSerializer(many=True),
                    "custom_fields": CustomFieldSerializer(many=True),
                },
            ),
        },
    ),
)
class GlobalSearchView(PassUserMixin):
    permission_classes = (IsAuthenticated,)
    serializer_class = SearchResultSerializer

    def get(self, request, *args, **kwargs):
        from documents.search import SearchMode
        from documents.search import get_backend

        query = request.query_params.get("query", None)
        if query is None:
            return HttpResponseBadRequest("Query required")
        if len(query) < 3:
            return HttpResponseBadRequest("Query must be at least 3 characters")
        if len(query) > _MAX_QUERY_LENGTH:
            return HttpResponseBadRequest(
                f"Query must be at most {_MAX_QUERY_LENGTH} characters",
            )

        db_only = request.query_params.get("db_only", False)

        OBJECT_LIMIT = 3
        docs = []
        if request.user.has_perm("documents.view_document"):
            # Never more than OBJECT_LIMIT rows come back here, so annotating
            # is cheap -- and without it these results show the root
            # document's superseded content.
            all_docs = annotate_effective_content(
                Document.objects.filter(
                    id__in=permitted_document_ids(request.user),
                ),
            )
            if db_only:
                docs = all_docs.filter(title__icontains=query)[:OBJECT_LIMIT]
            else:
                user = None if request.user.is_superuser else request.user
                matching_ids = get_backend().search_ids(
                    query,
                    user=user,
                    search_mode=SearchMode.TEXT,
                    limit=OBJECT_LIMIT * 3,
                )
                docs_by_id = all_docs.in_bulk(matching_ids)
                docs = [
                    docs_by_id[doc_id]
                    for doc_id in matching_ids
                    if doc_id in docs_by_id
                ][:OBJECT_LIMIT]
        saved_views = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_savedview",
                SavedView,
            ).filter(name__icontains=query)
            if request.user.has_perm("documents.view_savedview")
            else []
        )
        saved_views = saved_views[:OBJECT_LIMIT]
        tags = (
            get_objects_for_user_owner_aware(request.user, "view_tag", Tag).filter(
                name__icontains=query,
            )
            if request.user.has_perm("documents.view_tag")
            else []
        )
        tags = tags[:OBJECT_LIMIT]
        correspondents = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_correspondent",
                Correspondent,
            ).filter(name__icontains=query)
            if request.user.has_perm("documents.view_correspondent")
            else []
        )
        correspondents = correspondents[:OBJECT_LIMIT]
        document_types = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_documenttype",
                DocumentType,
            ).filter(name__icontains=query)
            if request.user.has_perm("documents.view_documenttype")
            else []
        )
        document_types = document_types[:OBJECT_LIMIT]
        storage_paths = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_storagepath",
                StoragePath,
            ).filter(name__icontains=query)
            if request.user.has_perm("documents.view_storagepath")
            else []
        )
        storage_paths = storage_paths[:OBJECT_LIMIT]
        users = (
            User.objects.filter(username__icontains=query)
            if request.user.has_perm("auth.view_user")
            else []
        )
        users = users[:OBJECT_LIMIT]
        groups = (
            Group.objects.filter(name__icontains=query)
            if request.user.has_perm("auth.view_group")
            else []
        )
        groups = groups[:OBJECT_LIMIT]
        mail_rules = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_mailrule",
                MailRule,
            ).filter(name__icontains=query)
            if request.user.has_perm("paperless_mail.view_mailrule")
            else []
        )
        mail_rules = mail_rules[:OBJECT_LIMIT]
        mail_accounts = (
            get_objects_for_user_owner_aware(
                request.user,
                "view_mailaccount",
                MailAccount,
            ).filter(name__icontains=query)
            if request.user.has_perm("paperless_mail.view_mailaccount")
            else []
        )
        mail_accounts = mail_accounts[:OBJECT_LIMIT]
        workflows = (
            Workflow.objects.filter(name__icontains=query)
            if request.user.has_perm("documents.view_workflow")
            else []
        )
        workflows = workflows[:OBJECT_LIMIT]
        custom_fields = (
            CustomField.objects.filter(name__icontains=query)
            if request.user.has_perm("documents.view_customfield")
            else []
        )
        custom_fields = custom_fields[:OBJECT_LIMIT]

        context = {
            "request": request,
        }

        docs_serializer = DocumentSerializer(docs, many=True, context=context)
        saved_views_serializer = SavedViewSerializer(
            saved_views,
            many=True,
            context=context,
        )
        tags_serializer = TagSerializer(tags, many=True, context=context)
        correspondents_serializer = CorrespondentSerializer(
            correspondents,
            many=True,
            context=context,
        )
        document_types_serializer = DocumentTypeSerializer(
            document_types,
            many=True,
            context=context,
        )
        storage_paths_serializer = StoragePathSerializer(
            storage_paths,
            many=True,
            context=context,
        )
        users_serializer = UserSerializer(users, many=True, context=context)
        groups_serializer = GroupSerializer(groups, many=True, context=context)
        mail_rules_serializer = MailRuleSerializer(
            mail_rules,
            many=True,
            context=context,
        )
        mail_accounts_serializer = MailAccountSerializer(
            mail_accounts,
            many=True,
            context=context,
        )
        workflows_serializer = WorkflowSerializer(workflows, many=True, context=context)
        custom_fields_serializer = CustomFieldSerializer(
            custom_fields,
            many=True,
            context=context,
        )

        return Response(
            {
                "total": len(docs)
                + len(saved_views)
                + len(tags)
                + len(correspondents)
                + len(document_types)
                + len(storage_paths)
                + len(users)
                + len(groups)
                + len(mail_rules)
                + len(mail_accounts)
                + len(workflows)
                + len(custom_fields),
                "documents": docs_serializer.data,
                "saved_views": saved_views_serializer.data,
                "tags": tags_serializer.data,
                "correspondents": correspondents_serializer.data,
                "document_types": document_types_serializer.data,
                "storage_paths": storage_paths_serializer.data,
                "users": users_serializer.data,
                "groups": groups_serializer.data,
                "mail_rules": mail_rules_serializer.data,
                "mail_accounts": mail_accounts_serializer.data,
                "workflows": workflows_serializer.data,
                "custom_fields": custom_fields_serializer.data,
            },
        )


@extend_schema_view(
    get=extend_schema(
        description="Get statistics for the current user",
        responses={
            (200, "application/json"): OpenApiTypes.OBJECT,
        },
    ),
)
class StatisticsView(GenericAPIView[Any]):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        user = request.user if request.user is not None else None
        can_view_global_stats = has_global_statistics_permission(user) or user is None

        documents = (
            Document.objects.all()
            if can_view_global_stats
            else Document.objects.filter(id__in=permitted_document_ids(user))
        ).filter(root_document__isnull=True)
        tags = (
            Tag.objects.all()
            if can_view_global_stats
            else get_objects_for_user_owner_aware(user, "documents.view_tag", Tag)
        ).only("id", "is_inbox_tag")
        correspondent_count = (
            Correspondent.objects.count()
            if can_view_global_stats
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_correspondent",
                Correspondent,
            ).count()
        )
        document_type_count = (
            DocumentType.objects.count()
            if can_view_global_stats
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_documenttype",
                DocumentType,
            ).count()
        )
        storage_path_count = (
            StoragePath.objects.count()
            if can_view_global_stats
            else get_objects_for_user_owner_aware(
                user,
                "documents.view_storagepath",
                StoragePath,
            ).count()
        )

        inbox_tag_pks = list(
            tags.filter(is_inbox_tag=True).values_list("pk", flat=True),
        )

        documents_inbox = (
            documents.filter(tags__id__in=inbox_tag_pks).values("id").distinct().count()
            if inbox_tag_pks
            else None
        )

        # Single SQL request for document stats and mime type counts
        mime_type_stats = list(
            documents.values("mime_type")
            .annotate(
                mime_type_count=Count("id"),
                mime_type_chars=Sum("content_length"),
            )
            .order_by("-mime_type_count"),
        )

        # Calculate totals from grouped results
        documents_total = sum(row["mime_type_count"] for row in mime_type_stats)
        character_count = sum(row["mime_type_chars"] or 0 for row in mime_type_stats)
        document_file_type_counts = [
            {"mime_type": row["mime_type"], "mime_type_count": row["mime_type_count"]}
            for row in mime_type_stats
        ]

        current_asn = Document.objects.aggregate(
            Max("archive_serial_number", default=0),
        ).get(
            "archive_serial_number__max",
        )

        return Response(
            {
                "documents_total": documents_total,
                "documents_inbox": documents_inbox,
                "inbox_tag": (
                    inbox_tag_pks[0] if inbox_tag_pks else None
                ),  # backwards compatibility
                "inbox_tags": (inbox_tag_pks or None),
                "document_file_type_counts": document_file_type_counts,
                "character_count": character_count,
                "tag_count": len(tags),
                "correspondent_count": correspondent_count,
                "document_type_count": document_type_count,
                "storage_path_count": storage_path_count,
                "current_asn": current_asn,
            },
        )
