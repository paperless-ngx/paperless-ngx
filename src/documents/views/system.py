import logging
import os
import platform
import re
from datetime import datetime
from datetime import timedelta
from time import sleep
from typing import Any
from urllib.parse import urlparse

import httpx
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Count
from django.db.models import Q
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.utils.timezone import make_aware
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from drf_spectacular.utils import inline_serializer
from packaging import version as packaging_version
from redis import Redis
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from documents.filters import PermittedObjectsFilter
from documents.models import Document
from documents.models import PaperlessTask
from documents.models import UiSettings
from documents.permissions import PaperlessObjectPermissions
from documents.permissions import TrashPermissions
from documents.permissions import has_system_status_permission
from documents.permissions import permitted_document_ids
from documents.serialisers.documents import DocumentSerializer
from documents.serialisers.system import TrashSerializer
from documents.serialisers.system import UiSettingsViewSerializer
from documents.tasks import empty_trash
from paperless import version
from paperless.celery import app as celery_app
from paperless.config import AIConfig
from paperless.config import GeneralConfig
from paperless.config import RemoteOCRConfig
from paperless.parsers.remote import RemoteEngineConfig
from paperless.views import StandardPagination
from paperless_mail.oauth import PaperlessMailOAuth2Manager

from .base import PassUserMixin

logger = logging.getLogger("paperless.api")


class UiSettingsView(GenericAPIView[Any]):
    queryset = UiSettings.objects.all()
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)
    serializer_class = UiSettingsViewSerializer

    def get(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.select_related("ui_settings").get(pk=request.user.id)
        ui_settings = {}
        if hasattr(user, "ui_settings"):
            ui_settings = user.ui_settings.settings
        if "update_checking" in ui_settings:
            ui_settings["update_checking"]["backend_setting"] = (
                settings.ENABLE_UPDATE_CHECK
            )
        else:
            ui_settings["update_checking"] = {
                "backend_setting": settings.ENABLE_UPDATE_CHECK,
            }

        ui_settings["trash_delay"] = settings.EMPTY_TRASH_DELAY

        general_config = GeneralConfig()

        ui_settings["version"] = version.__full_version_str__

        ui_settings["app_title"] = settings.APP_TITLE
        if general_config.app_title is not None and len(general_config.app_title) > 0:
            ui_settings["app_title"] = general_config.app_title
        ui_settings["app_logo"] = settings.APP_LOGO
        if general_config.app_logo is not None and len(general_config.app_logo) > 0:
            ui_settings["app_logo"] = general_config.app_logo

        ui_settings["auditlog_enabled"] = settings.AUDIT_LOG_ENABLED

        ui_settings["remote_ocr"] = {
            "configured": RemoteEngineConfig.from_app_config().engine_is_valid(),
            "mode": RemoteOCRConfig().remote_ocr_mode,
        }

        if settings.GMAIL_OAUTH_ENABLED or settings.OUTLOOK_OAUTH_ENABLED:
            manager = PaperlessMailOAuth2Manager()
            if settings.GMAIL_OAUTH_ENABLED:
                ui_settings["gmail_oauth_url"] = manager.get_gmail_authorization_url()
                request.session["oauth_state"] = manager.state
            if settings.OUTLOOK_OAUTH_ENABLED:
                ui_settings["outlook_oauth_url"] = (
                    manager.get_outlook_authorization_url()
                )
                request.session["oauth_state"] = manager.state

        ui_settings["email_enabled"] = settings.EMAIL_ENABLED

        ai_config = AIConfig()

        ui_settings["ai_enabled"] = ai_config.ai_enabled

        user_resp = {
            "id": user.id,
            "username": user.username,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "groups": list(user.groups.values_list("id", flat=True)),
        }

        if len(user.first_name) > 0:
            user_resp["first_name"] = user.first_name
        if len(user.last_name) > 0:
            user_resp["last_name"] = user.last_name

        # strip <app_label>.
        roles = map(lambda perm: re.sub(r"^\w+.", "", perm), user.get_all_permissions())
        return Response(
            {
                "user": user_resp,
                "settings": ui_settings,
                "permissions": roles,
            },
        )

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save(user=self.request.user)

        return Response(
            {
                "success": True,
            },
        )


@extend_schema_view(
    get=extend_schema(
        description="Get the current version of the Paperless-NGX server",
        responses={
            (200, "application/json"): OpenApiTypes.OBJECT,
        },
    ),
)
class RemoteVersionView(GenericAPIView[Any]):
    cache_key = "remote_version_view_latest_release"

    def get(self, request, format=None):
        current_version = packaging_version.parse(version.__full_version_str__)
        remote_version = cache.get(self.cache_key)
        if remote_version is None:
            try:
                resp = httpx.get(
                    "https://api.github.com/repos/paperless-ngx/paperless-ngx/releases/latest",
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                remote_version = data["tag_name"]
                # Some early tags used ngx-x.y.z
                remote_version = remote_version.removeprefix("ngx-")
            except ValueError as e:
                logger.debug(f"An error occurred parsing remote version json: {e}")
            except httpx.HTTPError as e:
                logger.debug(f"An error occurred checking for available updates: {e}")

            if remote_version:
                cache.set(self.cache_key, remote_version, 60 * 15)
            else:
                remote_version = "0.0.0"

        is_greater_than_current = (
            packaging_version.parse(remote_version) > current_version
        )

        return Response(
            {
                "version": remote_version,
                "update_available": is_greater_than_current,
            },
        )


@extend_schema_view(
    get=extend_schema(
        description="Get the current system status of the Paperless-NGX server",
        responses={
            (200, "application/json"): inline_serializer(
                name="SystemStatus",
                fields={
                    "pngx_version": serializers.CharField(),
                    "server_os": serializers.CharField(),
                    "install_type": serializers.CharField(),
                    "storage": inline_serializer(
                        name="Storage",
                        fields={
                            "total": serializers.IntegerField(),
                            "available": serializers.IntegerField(),
                        },
                    ),
                    "database": inline_serializer(
                        name="Database",
                        fields={
                            "type": serializers.CharField(),
                            "url": serializers.CharField(),
                            "status": serializers.CharField(),
                            "error": serializers.CharField(),
                            "migration_status": inline_serializer(
                                name="MigrationStatus",
                                fields={
                                    "latest_migration": serializers.CharField(),
                                    "unapplied_migrations": serializers.ListSerializer(
                                        child=serializers.CharField(),
                                    ),
                                },
                            ),
                        },
                    ),
                    "tasks": inline_serializer(
                        name="Tasks",
                        fields={
                            "redis_url": serializers.CharField(),
                            "redis_status": serializers.CharField(),
                            "redis_error": serializers.CharField(),
                            "celery_status": serializers.CharField(),
                            "summary": inline_serializer(
                                name="TasksSummaryOverview",
                                fields={
                                    "days": serializers.IntegerField(),
                                    "total_count": serializers.IntegerField(),
                                    "pending_count": serializers.IntegerField(),
                                    "success_count": serializers.IntegerField(),
                                    "failure_count": serializers.IntegerField(),
                                },
                            ),
                        },
                    ),
                    "index": inline_serializer(
                        name="Index",
                        fields={
                            "status": serializers.CharField(),
                            "error": serializers.CharField(),
                            "last_modified": serializers.DateTimeField(),
                        },
                    ),
                    "classifier": inline_serializer(
                        name="Classifier",
                        fields={
                            "status": serializers.CharField(),
                            "error": serializers.CharField(),
                            "last_trained": serializers.DateTimeField(),
                        },
                    ),
                    "sanity_check": inline_serializer(
                        name="SanityCheck",
                        fields={
                            "status": serializers.CharField(),
                            "error": serializers.CharField(),
                            "last_run": serializers.DateTimeField(),
                        },
                    ),
                },
            ),
        },
    ),
)
class SystemStatusView(PassUserMixin):
    permission_classes = (IsAuthenticated,)
    TASK_SUMMARY_DAYS = 30

    def get(self, request, format=None):
        if not has_system_status_permission(request.user):
            return HttpResponseForbidden("Insufficient permissions")

        current_version = version.__full_version_str__

        install_type = "bare-metal"
        if os.environ.get("KUBERNETES_SERVICE_HOST") is not None:
            install_type = "kubernetes"
        elif os.environ.get("PNGX_CONTAINERIZED") == "1":
            install_type = "docker"

        db_conn = connections["default"]
        db_url = str(db_conn.settings_dict["NAME"])
        db_error = None

        try:
            db_conn.ensure_connection()
            db_status = "OK"
            loader = MigrationLoader(connection=db_conn)
            all_migrations = [f"{app}.{name}" for app, name in loader.graph.nodes]
            applied_migrations = [
                f"{m.app}.{m.name}"
                for m in MigrationRecorder.Migration.objects.all().order_by("id")
            ]
        except Exception as e:  # pragma: no cover
            applied_migrations = []
            db_status = "ERROR"
            logger.exception(
                f"System status detected a possible problem while connecting to the database: {e}",
            )
            db_error = "Error connecting to database, check logs for more detail."

        media_stats = os.statvfs(settings.MEDIA_ROOT)

        redis_url = settings._CHANNELS_REDIS_URL
        redis_url_parsed = urlparse(redis_url)
        redis_constructed_url = f"{redis_url_parsed.scheme}://{redis_url_parsed.path or redis_url_parsed.hostname}"
        if redis_url_parsed.hostname is not None:
            redis_constructed_url += f":{redis_url_parsed.port}"
        redis_error = None
        with Redis.from_url(url=redis_url) as client:
            try:
                client.ping()
                redis_status = "OK"
            except Exception as e:
                redis_status = "ERROR"
                logger.exception(
                    f"System status detected a possible problem while connecting to redis: {e}",
                )
                redis_error = "Error connecting to redis, check logs for more detail."

        celery_error = None
        celery_url = None
        try:
            celery_ping = None
            for ping_attempt in range(3):
                celery_ping = celery_app.control.inspect().ping()
                if celery_ping:
                    break
                if ping_attempt < 2:
                    sleep(0.25)

            if not celery_ping:
                celery_active = "WARNING"
                celery_error = (
                    "No celery workers responded to ping. This may be temporary."
                )
            else:
                celery_url, first_worker_ping = next(iter(celery_ping.items()))
                if (
                    isinstance(first_worker_ping, dict)
                    and first_worker_ping.get("ok") == "pong"
                ):
                    celery_active = "OK"
                else:
                    celery_active = "WARNING"
                    celery_error = "Celery worker responded unexpectedly."
        except Exception as e:
            celery_active = "ERROR"
            logger.exception(
                f"System status detected a possible problem while connecting to celery: {e}",
            )
            celery_error = "Error connecting to celery, check logs for more detail."

        index_error = None
        try:
            from documents.search import get_backend

            get_backend()  # triggers open/rebuild; raises on error
            index_status = "OK"
            # Use the most-recently modified file in the index directory as a proxy
            # for last index write time (Tantivy has no single last_modified() call).
            index_dir = settings.INDEX_DIR
            mtimes = [p.stat().st_mtime for p in index_dir.iterdir() if p.is_file()]
            index_last_modified = (
                make_aware(datetime.fromtimestamp(max(mtimes))) if mtimes else None
            )
        except Exception as e:
            index_status = "ERROR"
            index_error = "Error opening index, check logs for more detail."
            logger.exception(
                f"System status detected a possible problem while opening the index: {e}",
            )
            index_last_modified = None

        last_trained_task = (
            PaperlessTask.objects.filter(
                task_type=PaperlessTask.TaskType.TRAIN_CLASSIFIER,
                status__in=PaperlessTask.COMPLETE_STATUSES,  # ignore running tasks
            )
            .order_by("-date_done")
            .first()
        )
        classifier_status = "OK"
        classifier_error = None
        if last_trained_task is None:
            classifier_status = "WARNING"
            classifier_error = "No classifier training tasks found"
        elif last_trained_task.status != PaperlessTask.Status.SUCCESS:
            classifier_status = "ERROR"
            classifier_error = (
                last_trained_task.result_data.get("error_message")
                if last_trained_task.result_data
                else None
            )
        classifier_last_trained = (
            last_trained_task.date_done if last_trained_task else None
        )

        last_sanity_check = (
            PaperlessTask.objects.filter(
                task_type=PaperlessTask.TaskType.SANITY_CHECK,
                status__in=PaperlessTask.COMPLETE_STATUSES,  # ignore running tasks
            )
            .order_by("-date_done")
            .first()
        )
        sanity_check_status = "OK"
        sanity_check_error = None
        if last_sanity_check is None:
            sanity_check_status = "WARNING"
            sanity_check_error = "No sanity check tasks found"
        elif last_sanity_check.status != PaperlessTask.Status.SUCCESS:
            sanity_check_status = "ERROR"
            sanity_check_error = (
                last_sanity_check.result_data.get("error_message")
                if last_sanity_check.result_data
                else None
            )
        sanity_check_last_run = (
            last_sanity_check.date_done if last_sanity_check else None
        )

        ai_config = AIConfig()
        if not ai_config.llm_index_enabled:
            llmindex_status = "DISABLED"
            llmindex_error = None
            llmindex_last_modified = None
        else:
            last_llmindex_update = (
                PaperlessTask.objects.filter(
                    task_type=PaperlessTask.TaskType.LLM_INDEX,
                )
                .order_by("-date_done")
                .first()
            )
            llmindex_status = "OK"
            llmindex_error = None
            if last_llmindex_update is None:
                llmindex_status = "WARNING"
                llmindex_error = "No LLM index update tasks found"
            elif last_llmindex_update.status == PaperlessTask.Status.FAILURE:
                llmindex_status = "ERROR"
                llmindex_error = (
                    last_llmindex_update.result_data.get("error_message")
                    if last_llmindex_update.result_data
                    else None
                )
            llmindex_last_modified = (
                last_llmindex_update.date_done if last_llmindex_update else None
            )

        summary_cutoff = timezone.now() - timedelta(days=self.TASK_SUMMARY_DAYS)
        task_summary_agg = PaperlessTask.objects.filter(
            date_created__gte=summary_cutoff,
        ).aggregate(
            total_count=Count("id"),
            pending_count=Count(
                "id",
                filter=Q(status=PaperlessTask.Status.PENDING),
            ),
            success_count=Count(
                "id",
                filter=Q(status=PaperlessTask.Status.SUCCESS),
            ),
            failure_count=Count(
                "id",
                filter=Q(status=PaperlessTask.Status.FAILURE),
            ),
        )
        task_summary = {
            "days": self.TASK_SUMMARY_DAYS,
            **task_summary_agg,
        }

        return Response(
            {
                "pngx_version": current_version,
                "server_os": platform.platform(),
                "install_type": install_type,
                "storage": {
                    "total": media_stats.f_frsize * media_stats.f_blocks,
                    "available": media_stats.f_frsize * media_stats.f_bavail,
                },
                "database": {
                    "type": db_conn.vendor,
                    "url": db_url,
                    "status": db_status,
                    "error": db_error,
                    "migration_status": {
                        "latest_migration": applied_migrations[-1],
                        "unapplied_migrations": [
                            m for m in all_migrations if m not in applied_migrations
                        ],
                    },
                },
                "tasks": {
                    "redis_url": redis_constructed_url,
                    "redis_status": redis_status,
                    "redis_error": redis_error,
                    "celery_status": celery_active,
                    "celery_url": celery_url,
                    "celery_error": celery_error,
                    "index_status": index_status,
                    "index_last_modified": index_last_modified,
                    "index_error": index_error,
                    "classifier_status": classifier_status,
                    "classifier_last_trained": classifier_last_trained,
                    "classifier_error": classifier_error,
                    "sanity_check_status": sanity_check_status,
                    "sanity_check_last_run": sanity_check_last_run,
                    "sanity_check_error": sanity_check_error,
                    "llmindex_status": llmindex_status,
                    "llmindex_last_modified": llmindex_last_modified,
                    "llmindex_error": llmindex_error,
                    "summary": task_summary,
                },
            },
        )


class TrashView(ListModelMixin, PassUserMixin):
    permission_classes = (IsAuthenticated, TrashPermissions)
    serializer_class = TrashSerializer

    class _TrashPermittedObjectsFilter(PermittedObjectsFilter):
        include_granted = False

    filter_backends = (_TrashPermittedObjectsFilter,)
    pagination_class = StandardPagination

    model = Document

    # A version is listed separately only when its root is not in the trash.
    queryset = Document.deleted_objects.exclude(
        root_document_id__in=Document.deleted_objects.values("id"),
    )

    def get(self, request: Request, format: str | None = None) -> Response:
        self.serializer_class = DocumentSerializer
        return self.list(request, format)

    def post(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response | HttpResponse:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_ids = serializer.validated_data.get("documents")
        docs = (
            Document.global_objects.filter(id__in=doc_ids)
            if doc_ids is not None
            else self.filter_queryset(self.get_queryset()).all()
        )
        if docs.exclude(
            pk__in=permitted_document_ids(
                request.user,
                perm="delete_document",
                include_deleted=True,
            ),
        ).exists():
            return HttpResponseForbidden("Insufficient permissions")
        action = serializer.validated_data.get("action")
        if action == "restore":
            restored = list(self.get_queryset().filter(id__in=doc_ids))
            if len(restored) != len(doc_ids):
                raise ValidationError(
                    {
                        "documents": [
                            "Restore the root document instead of one of its versions.",
                        ],
                    },
                )
            for doc in restored:
                doc.restore(strict=False)
            if restored:
                from documents.search import get_backend

                with get_backend().batch_update() as batch:
                    batch.add_or_update_ids([doc.pk for doc in restored])
        elif action == "empty":
            if doc_ids is None:
                doc_ids = [doc.id for doc in docs]
            empty_trash(doc_ids=doc_ids)
        return Response({"result": "OK", "doc_ids": doc_ids})
