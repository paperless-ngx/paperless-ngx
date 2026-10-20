from __future__ import annotations

from typing import TYPE_CHECKING

from documents.plugins.helpers import ProgressManager

if TYPE_CHECKING:
    from documents.plugins.helpers import WebsocketPayload


class FakeProgressManager(ProgressManager):
    """
    The real ProgressManager with the channel layer cut out: send_progress still
    builds the payload, so it cannot drift, and the payloads are recorded instead
    of being sent to Redis.

    Use it through the `fake_progress_manager` fixture, or construct it directly.
    """

    def __init__(self, filename: str | None = None, task_id: str | None = None) -> None:
        super().__init__(filename, task_id)
        self.payloads: list[WebsocketPayload] = []

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def send(self, payload: WebsocketPayload) -> None:
        self.payloads.append(payload)
