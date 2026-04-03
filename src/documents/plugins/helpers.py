import enum
from typing import TYPE_CHECKING
from typing import Literal
from typing import Self
from typing import TypeAlias
from typing import TypedDict

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

if TYPE_CHECKING:
    from channels_redis.pubsub import RedisPubSubChannelLayer


class ProgressStatusOptions(enum.StrEnum):
    STARTED = "STARTED"
    WORKING = "WORKING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class PermissionsData(TypedDict, total=False):
    """Permission fields included in status messages for access control."""

    owner_id: int | None
    users_can_view: list[int]
    groups_can_view: list[int]


class ProgressUpdateData(TypedDict):
    filename: str | None
    task_id: str | None
    current_progress: int
    max_progress: int
    status: str
    message: str
    document_id: int | None
    owner_id: int | None
    users_can_view: list[int]
    groups_can_view: list[int]


class StatusUpdatePayload(TypedDict):
    type: Literal["status_update"]
    data: ProgressUpdateData


class DocumentsDeletedData(TypedDict):
    documents: list[int]


class DocumentsDeletedPayload(TypedDict):
    type: Literal["documents_deleted"]
    data: DocumentsDeletedData


class DocumentUpdatedData(TypedDict):
    document_id: int
    modified: str
    owner_id: int | None
    users_can_view: list[int]
    groups_can_view: list[int]


class DocumentUpdatedPayload(TypedDict):
    type: Literal["document_updated"]
    data: DocumentUpdatedData


WebsocketPayload: TypeAlias = (
    StatusUpdatePayload | DocumentsDeletedPayload | DocumentUpdatedPayload
)


class BaseStatusManager:
    """
    Handles sending of progress information via the channel layer, with proper management
    of the open/close of the layer to ensure messages go out and everything is cleaned up
    """

    def __init__(self) -> None:
        self._channel: RedisPubSubChannelLayer | None = None

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def open(self) -> None:
        """
        If not already opened, gets the default channel layer
        opened and ready to send messages
        """
        if self._channel is None:
            self._channel = get_channel_layer()

    def close(self) -> None:
        """
        If it was opened, flushes the channel layer
        """
        if self._channel is not None:
            async_to_sync(self._channel.flush)
            self._channel = None

    def send(self, payload: WebsocketPayload) -> None:
        # Ensure the layer is open
        self.open()

        # Just for IDEs
        if TYPE_CHECKING:
            assert self._channel is not None

        # Construct and send the update
        async_to_sync(self._channel.group_send)("status_updates", payload)


class ProgressManager(BaseStatusManager):
    def __init__(self, filename: str | None = None, task_id: str | None = None) -> None:
        super().__init__()
        self.filename = filename
        self.task_id = task_id

    def send_progress(
        self,
        status: ProgressStatusOptions,
        message: str,
        current_progress: int,
        max_progress: int,
        *,
        document_id: int | None = None,
        owner_id: int | None = None,
        users_can_view: list[int] | None = None,
        groups_can_view: list[int] | None = None,
    ) -> None:
        data: ProgressUpdateData = {
            "filename": self.filename,
            "task_id": self.task_id,
            "current_progress": current_progress,
            "max_progress": max_progress,
            "status": status,
            "message": message,
            "document_id": document_id,
            "owner_id": owner_id,
            "users_can_view": users_can_view or [],
            "groups_can_view": groups_can_view or [],
        }
        payload: StatusUpdatePayload = {"type": "status_update", "data": data}
        self.send(payload)


class DocumentsStatusManager(BaseStatusManager):
    def send_documents_deleted(self, documents: list[int]) -> None:
        payload: DocumentsDeletedPayload = {
            "type": "documents_deleted",
            "data": {
                "documents": documents,
            },
        }
        self.send(payload)

    def send_document_updated(
        self,
        *,
        document_id: int,
        modified: str,
        owner_id: int | None = None,
        users_can_view: list[int] | None = None,
        groups_can_view: list[int] | None = None,
    ) -> None:
        payload: DocumentUpdatedPayload = {
            "type": "document_updated",
            "data": {
                "document_id": document_id,
                "modified": modified,
                "owner_id": owner_id,
                "users_can_view": users_can_view or [],
                "groups_can_view": groups_can_view or [],
            },
        }
        self.send(payload)
