from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer

if TYPE_CHECKING:
    from documents.plugins.helpers import PermissionsData


class StatusConsumer(AsyncWebsocketConsumer):
    def _authenticated(self) -> bool:
        user: Any = self.scope.get("user")
        return user is not None and user.is_authenticated

    async def _can_view(self, data: PermissionsData) -> bool:
        user: Any = self.scope.get("user")
        if user is None:
            return False
        owner_id = data.get("owner_id")
        users_can_view = data.get("users_can_view", [])
        groups_can_view = data.get("groups_can_view", [])

        if user.is_superuser or user.id == owner_id or user.id in users_can_view:
            return True

        for group_id in groups_can_view:
            if await user.groups.filter(pk=group_id).aexists():
                return True

        return False

    async def connect(self) -> None:
        if not self._authenticated():
            await self.close()
            return
        await self.channel_layer.group_add("status_updates", self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard("status_updates", self.channel_name)

    async def status_update(self, event: dict[str, Any]) -> None:
        if not self._authenticated():
            await self.close()
        elif await self._can_view(event["data"]):
            await self.send(json.dumps(event))

    async def documents_deleted(self, event: dict[str, Any]) -> None:
        if not self._authenticated():
            await self.close()
        else:
            await self.send(json.dumps(event))

    async def document_updated(self, event: dict[str, Any]) -> None:
        if not self._authenticated():
            await self.close()
        elif await self._can_view(event["data"]):
            await self.send(json.dumps(event))
