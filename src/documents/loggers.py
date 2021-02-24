import logging
import uuid

from django.conf import settings


class LoggingMixin:

    logging_group = None

    logging_name = None

    def renew_logging_group(self):
        self.logging_group = uuid.uuid4()

    def log(self, level, message, **kwargs):
        if self.logging_name:
            logger = logging.getLogger(self.logging_name)
        else:
            name = ".".join([
                self.__class__.__module__,
                self.__class__.__name__
            ])
            logger = logging.getLogger(name)

        getattr(logger, level)(message, extra={
            "group": self.logging_group
        }, **kwargs)
