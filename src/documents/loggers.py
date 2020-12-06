import logging
import uuid

from django.conf import settings


class PaperlessHandler(logging.Handler):
    def emit(self, record):
        if settings.DISABLE_DBHANDLER:
            return

        # We have to do the import here or Django will barf when it tries to
        # load this because the apps aren't loaded at that point
        from .models import Log

        kwargs = {"message": record.msg, "level": record.levelno}

        if hasattr(record, "group"):
            kwargs["group"] = record.group

        Log.objects.create(**kwargs)


class LoggingMixin:

    logging_group = None

    def renew_logging_group(self):
        self.logging_group = uuid.uuid4()

    def log(self, level, message, **kwargs):
        target = ".".join([self.__class__.__module__, self.__class__.__name__])
        logger = logging.getLogger(target)

        getattr(logger, level)(message, extra={
            "group": self.logging_group
        }, **kwargs)
