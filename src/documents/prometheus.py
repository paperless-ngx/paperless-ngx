"""Prometheus metrics collector and view for paperless-ngx."""

from __future__ import annotations

import logging

from django.http import HttpResponse
from django.http import HttpResponseForbidden
from prometheus_client import generate_latest
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from prometheus_client.registry import CollectorRegistry
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from documents.status import get_system_status

logger = logging.getLogger("paperless.prometheus")

# Custom registry - no default process/platform collectors
registry = CollectorRegistry(auto_describe=True)

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


class PaperlessStatusCollector(Collector):
    """Collects paperless-ngx system status metrics on each Prometheus scrape."""

    def collect(self):
        try:
            status = get_system_status()
        except Exception:
            logger.exception("Failed to collect system status for Prometheus")
            return

        def _status_to_gauge(value: str) -> float:
            return 1.0 if value == "OK" else 0.0

        def _dt_to_epoch(dt) -> float | None:
            if dt is None:
                return None
            return dt.timestamp()

        # Database
        yield GaugeMetricFamily(
            "paperless_status_database_status",
            "Status of the database. 1 is OK, 0 is not OK.",
            value=_status_to_gauge(status.database.status),
        )
        yield GaugeMetricFamily(
            "paperless_status_database_unapplied_migrations",
            "Number of unapplied database migrations.",
            value=float(len(status.database.unapplied_migrations)),
        )

        # Storage
        yield GaugeMetricFamily(
            "paperless_status_storage_total_bytes",
            "Total storage of Paperless in bytes.",
            value=float(status.storage.total_bytes),
        )
        yield GaugeMetricFamily(
            "paperless_status_storage_available_bytes",
            "Available storage of Paperless in bytes.",
            value=float(status.storage.available_bytes),
        )

        # Redis
        yield GaugeMetricFamily(
            "paperless_status_redis_status",
            "Status of redis. 1 is OK, 0 is not OK.",
            value=_status_to_gauge(status.redis.status),
        )

        # Celery
        yield GaugeMetricFamily(
            "paperless_status_celery_status",
            "Status of celery. 1 is OK, 0 is not OK.",
            value=_status_to_gauge(status.celery.status),
        )

        # Index
        yield GaugeMetricFamily(
            "paperless_status_index_status",
            "Status of the index. 1 is OK, 0 is not OK.",
            value=_status_to_gauge(status.index.status),
        )
        ts = _dt_to_epoch(status.index.last_modified)
        if ts is not None:
            yield GaugeMetricFamily(
                "paperless_status_index_last_modified_timestamp_seconds",
                "Number of seconds since 1970-01-01 since the last time the index has been modified.",
                value=ts,
            )

        # Classifier
        yield GaugeMetricFamily(
            "paperless_status_classifier_status",
            "Status of the classifier. 1 is OK, 0 is not OK.",
            value=_status_to_gauge(status.classifier.status),
        )
        ts = _dt_to_epoch(status.classifier.last_run)
        if ts is not None:
            yield GaugeMetricFamily(
                "paperless_status_classifier_last_trained_timestamp_seconds",
                "Number of seconds since 1970-01-01 since the last time the classifier has been trained.",
                value=ts,
            )

        # Sanity check
        yield GaugeMetricFamily(
            "paperless_status_sanity_check_status",
            "Status of the sanity check. 1 is OK, 0 is not OK.",
            value=_status_to_gauge(status.sanity_check.status),
        )
        ts = _dt_to_epoch(status.sanity_check.last_run)
        if ts is not None:
            yield GaugeMetricFamily(
                "paperless_status_sanity_check_last_run_timestamp_seconds",
                "Number of seconds since 1970-01-01 since the last time the sanity check has been run.",
                value=ts,
            )


registry.register(PaperlessStatusCollector())


class PrometheusMetricsView(APIView):
    """Serves Prometheus metrics at /metrics.

    Requires authentication and staff permissions, consistent with SystemStatusView.
    Must be enabled via PAPERLESS_PROMETHEUS_METRICS_ENABLED=true.
    """

    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        # if not settings.PROMETHEUS_METRICS_ENABLED:
        #    return HttpResponseNotFound("Metrics endpoint is disabled")

        if not request.user.is_staff:
            return HttpResponseForbidden("Insufficient permissions")

        metrics_output = generate_latest(registry)
        return HttpResponse(
            metrics_output,
            content_type=CONTENT_TYPE_LATEST,
        )
