from __future__ import annotations

import json
from typing import TYPE_CHECKING

from channels.generic.websocket import AsyncWebsocketConsumer

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser
    from django.contrib.auth.models import AnonymousUser

    from documents.plugins.helpers import DocumentsDeletedPayload
    from documents.plugins.helpers import DocumentUpdatedPayload
    from documents.plugins.helpers import PermissionsData
    from documents.plugins.helpers import StatusUpdatePayload


class StatusConsumer(AsyncWebsocketConsumer):
    def _authenticated(self) -> bool:
        user: AbstractBaseUser | AnonymousUser | None = self.scope.get("user")
        return user is not None and user.is_authenticated

    async def _can_view(self, data: PermissionsData) -> bool:
        user: AbstractBaseUser | AnonymousUser | None = self.scope.get("user")
        if user is None:
            return False
        owner_id = data.get("owner_id")
        users_can_view = data.get("users_can_view", [])
        groups_can_view = data.get("groups_can_view", [])

        if user.is_superuser or user.id == owner_id or user.id in users_can_view:
            return True

        return await user.groups.filter(pk__in=groups_can_view).aexists()

    async def connect(self) -> None:
        if not self._authenticated():
            await self.close()
            return
        await self.channel_layer.group_add("status_updates", self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard("status_updates", self.channel_name)

    async def status_update(self, event: StatusUpdatePayload) -> None:
        if not self._authenticated():
            await self.close()
        elif await self._can_view(event["data"]):
            await self.send(json.dumps(event))

    async def documents_deleted(self, event: DocumentsDeletedPayload) -> None:
        if not self._authenticated():
            await self.close()
        else:
            await self.send(json.dumps(event))

    async def document_updated(self, event: DocumentUpdatedPayload) -> None:
        if not self._authenticated():
            await self.close()
        elif await self._can_view(event["data"]):
            await self.send(json.dumps(event))
