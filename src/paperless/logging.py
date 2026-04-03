from __future__ import annotations

import logging
from contextvars import ContextVar

consume_task_id: ContextVar[str] = ContextVar("consume_task_id", default="")


class ConsumeTaskFormatter(logging.Formatter):
    """
    Logging formatter that prepends a short task correlation ID to messages
    emitted during document consumption.

    The ID is the first 8 characters of the Celery task UUID, set via the
    ``consume_task_id`` ContextVar at the entry of ``consume_file``.  When
    the ContextVar is empty (any log outside a consume task) no prefix is
    added and the output is identical to the standard verbose format.
    """

    def __init__(self) -> None:
        super().__init__(
            fmt="[{asctime}] [{levelname}] [{name}] {task_prefix}{message}",
            style="{",
            validate=False,  # {task_prefix} is not a standard LogRecord attribute, so Python's
            # init-time format-string validation would raise ValueError without
            # this. Runtime safety comes from format() always setting
            # record.task_prefix before calling super().format().
        )

    def format(self, record: logging.LogRecord) -> str:
        task_id = consume_task_id.get()
        record.task_prefix = f"[{task_id}] " if task_id else ""
        return super().format(record)
