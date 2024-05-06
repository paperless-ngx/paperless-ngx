import logging
import uuid


class LoggingMixin:
    def renew_logging_group(self):
        """
        Creates a new UUID to group subsequent log calls together with
        the extra data named group
        """
        self.logging_group = uuid.uuid4()
        self.log = logging.LoggerAdapter(
            logging.getLogger(self.logging_name),
            extra={"group": self.logging_group},
        )
