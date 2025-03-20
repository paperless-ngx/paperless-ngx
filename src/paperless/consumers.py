import json
import logging

from asgiref.sync import async_to_sync
from channels.exceptions import AcceptConnection
from channels.exceptions import DenyConnection
from channels.generic.websocket import WebsocketConsumer
from django.db import close_old_connections
from django.db import connections

logger = logging.getLogger("paperless.websockets")


class StatusConsumer(WebsocketConsumer):
    def _authenticated(self):
        return "user" in self.scope and self.scope["user"].is_authenticated

    def _is_owner_or_unowned(self, data):
        return (
            (
                self.scope["user"].is_superuser
                or self.scope["user"].id == data["owner_id"]
            )
            if "owner_id" in data and "user" in self.scope
            else True
        )

    def _discard_database_connections(self):
        logger.debug("Discarding %s database connections...", len(connections.all()))
        for conn in connections.all():
            conn.close()

    def connect(self):
        logger.debug("Connecting ws...")
        close_old_connections()
        if not self._authenticated():
            raise DenyConnection
        else:
            async_to_sync(self.channel_layer.group_add)(
                "status_updates",
                self.channel_name,
            )
            raise AcceptConnection

    def disconnect(self, close_code):
        logger.debug("Disconnecting ws...")
        self._discard_database_connections()
        async_to_sync(self.channel_layer.group_discard)(
            "status_updates",
            self.channel_name,
        )

    def close(self, code=None, reason=None):
        self._discard_database_connections()
        return super().close(code, reason)

    def status_update(self, event):
        if not self._authenticated():
            self.close()
        else:
            if self._is_owner_or_unowned(event["data"]):
                self.send(json.dumps(event))

    def documents_deleted(self, event):
        if not self._authenticated():
            self.close()
        else:
            self.send(json.dumps(event))
