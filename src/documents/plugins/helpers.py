import enum
from typing import TYPE_CHECKING

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

if TYPE_CHECKING:
    from channels_redis.pubsub import RedisPubSubChannelLayer


class ProgressStatusOptions(str, enum.Enum):
    STARTED = "STARTED"
    WORKING = "WORKING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class BaseStatusManager:
    """
    Handles sending of progress information via the channel layer, with proper management
    of the open/close of the layer to ensure messages go out and everything is cleaned up
    """

    def __init__(self) -> None:
        self._channel: RedisPubSubChannelLayer | None = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
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

    def send(self, payload: dict[str, str | int | None]) -> None:
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
        extra_args: dict[str, str | int | None] | None = None,
    ) -> None:
        payload = {
            "type": "status_update",
            "data": {
                "filename": self.filename,
                "task_id": self.task_id,
                "current_progress": current_progress,
                "max_progress": max_progress,
                "status": status,
                "message": message,
            },
        }
        if extra_args is not None:
            payload["data"].update(extra_args)

        self.send(payload)


class DocumentsStatusManager(BaseStatusManager):
    def send_documents_deleted(self, documents: list[int]) -> None:
        payload = {
            "type": "documents_deleted",
            "data": {
                "documents": documents,
            },
        }

        self.send(payload)
