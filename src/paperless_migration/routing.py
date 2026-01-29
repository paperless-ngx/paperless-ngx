"""WebSocket URL routing for migration operations."""

from __future__ import annotations

from django.urls import path

from paperless_migration.consumers import ImportConsumer
from paperless_migration.consumers import TransformConsumer

websocket_urlpatterns = [
    path("ws/migration/transform/", TransformConsumer.as_asgi()),
    path("ws/migration/import/", ImportConsumer.as_asgi()),
]
