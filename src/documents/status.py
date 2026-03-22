"""Shared system status-gathering functions.

Used by both the SystemStatusView (JSON API) and the Prometheus metrics collector.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from celery import states
from django.conf import settings
from django.db import connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.utils.timezone import make_aware
from redis import Redis

from documents import index
from documents.models import PaperlessTask
from paperless.celery import app as celery_app

logger = logging.getLogger("paperless.status")


@dataclass
class DatabaseStatus:
    status: str  # "OK" or "ERROR"
    error: str | None
    db_url: str
    db_vendor: str
    all_migrations: list[str] = field(default_factory=list)
    applied_migrations: list[str] = field(default_factory=list)

    @property
    def unapplied_migrations(self) -> list[str]:
        return [m for m in self.all_migrations if m not in self.applied_migrations]


@dataclass
class StorageStatus:
    total_bytes: int
    available_bytes: int


@dataclass
class RedisStatus:
    status: str  # "OK" or "ERROR"
    error: str | None


@dataclass
class CeleryStatus:
    status: str  # "OK" or "ERROR"
    error: str | None
    celery_url: str | None


@dataclass
class IndexStatus:
    status: str  # "OK" or "ERROR"
    error: str | None
    last_modified: datetime | None


@dataclass
class TaskCheckStatus:
    status: str  # "OK", "WARNING", or "ERROR"
    error: str | None
    last_run: datetime | None


@dataclass
class SystemStatus:
    database: DatabaseStatus
    storage: StorageStatus
    redis: RedisStatus
    celery: CeleryStatus
    index: IndexStatus
    classifier: TaskCheckStatus
    sanity_check: TaskCheckStatus


def get_database_status() -> DatabaseStatus:
    db_conn = connections["default"]
    db_url = str(db_conn.settings_dict["NAME"])
    db_vendor = db_conn.vendor
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
    except Exception as e:
        all_migrations = []
        applied_migrations = []
        db_status = "ERROR"
        logger.exception(
            f"System status detected a possible problem while connecting to the database: {e}",
        )
        db_error = "Error connecting to database, check logs for more detail."

    return DatabaseStatus(
        status=db_status,
        error=db_error,
        db_url=db_url,
        db_vendor=db_vendor,
        all_migrations=all_migrations,
        applied_migrations=applied_migrations,
    )


def get_storage_status() -> StorageStatus:
    media_stats = os.statvfs(settings.MEDIA_ROOT)
    return StorageStatus(
        total_bytes=media_stats.f_frsize * media_stats.f_blocks,
        available_bytes=media_stats.f_frsize * media_stats.f_bavail,
    )


def get_redis_status() -> RedisStatus:
    redis_url = settings._CHANNELS_REDIS_URL
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

    return RedisStatus(status=redis_status, error=redis_error)


def get_celery_status() -> CeleryStatus:
    celery_error = None
    celery_url = None
    try:
        celery_ping = celery_app.control.inspect().ping()
        celery_url = next(iter(celery_ping.keys()))
        first_worker_ping = celery_ping[celery_url]
        if first_worker_ping["ok"] == "pong":
            celery_active = "OK"
    except Exception as e:
        celery_active = "ERROR"
        logger.exception(
            f"System status detected a possible problem while connecting to celery: {e}",
        )
        celery_error = "Error connecting to celery, check logs for more detail."

    return CeleryStatus(status=celery_active, error=celery_error, celery_url=celery_url)


def get_index_status() -> IndexStatus:
    index_error = None
    try:
        ix = index.open_index()
        index_status = "OK"
        index_last_modified = make_aware(
            datetime.fromtimestamp(ix.last_modified()),
        )
    except Exception as e:
        index_status = "ERROR"
        index_error = "Error opening index, check logs for more detail."
        logger.exception(
            f"System status detected a possible problem while opening the index: {e}",
        )
        index_last_modified = None

    return IndexStatus(
        status=index_status,
        error=index_error,
        last_modified=index_last_modified,
    )


def get_classifier_status() -> TaskCheckStatus:
    last_trained_task = (
        PaperlessTask.objects.filter(
            task_name=PaperlessTask.TaskName.TRAIN_CLASSIFIER,
            status__in=[
                states.SUCCESS,
                states.FAILURE,
                states.REVOKED,
            ],
        )
        .order_by("-date_done")
        .first()
    )
    classifier_status = "OK"
    classifier_error = None
    if last_trained_task is None:
        classifier_status = "WARNING"
        classifier_error = "No classifier training tasks found"
    elif last_trained_task and last_trained_task.status != states.SUCCESS:
        classifier_status = "ERROR"
        classifier_error = last_trained_task.result
    classifier_last_trained = last_trained_task.date_done if last_trained_task else None

    return TaskCheckStatus(
        status=classifier_status,
        error=classifier_error,
        last_run=classifier_last_trained,
    )


def get_sanity_check_status() -> TaskCheckStatus:
    last_sanity_check = (
        PaperlessTask.objects.filter(
            task_name=PaperlessTask.TaskName.CHECK_SANITY,
            status__in=[
                states.SUCCESS,
                states.FAILURE,
                states.REVOKED,
            ],
        )
        .order_by("-date_done")
        .first()
    )
    sanity_check_status = "OK"
    sanity_check_error = None
    if last_sanity_check is None:
        sanity_check_status = "WARNING"
        sanity_check_error = "No sanity check tasks found"
    elif last_sanity_check and last_sanity_check.status != states.SUCCESS:
        sanity_check_status = "ERROR"
        sanity_check_error = last_sanity_check.result
    sanity_check_last_run = last_sanity_check.date_done if last_sanity_check else None

    return TaskCheckStatus(
        status=sanity_check_status,
        error=sanity_check_error,
        last_run=sanity_check_last_run,
    )


def get_system_status() -> SystemStatus:
    return SystemStatus(
        database=get_database_status(),
        storage=get_storage_status(),
        redis=get_redis_status(),
        celery=get_celery_status(),
        index=get_index_status(),
        classifier=get_classifier_status(),
        sanity_check=get_sanity_check_status(),
    )
