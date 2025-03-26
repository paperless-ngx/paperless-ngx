import json

from asgiref.sync import async_to_sync
from channels.exceptions import AcceptConnection
from channels.exceptions import DenyConnection
from channels.generic.websocket import WebsocketConsumer


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

    def connect(self):
        if not self._authenticated():
            raise DenyConnection
        else:
            async_to_sync(self.channel_layer.group_add)(
                "status_updates",
                self.channel_name,
            )
            raise AcceptConnection

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            "status_updates",
            self.channel_name,
        )

    def status_update(self, event):
        if not self._authenticated():
            self.close()
        else:
            if self._is_owner_or_unowned(event["data"]):
                self.send(json.dumps(event["data"]))
