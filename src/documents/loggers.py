import logging


class PaperlessHandler(logging.Handler):
    def emit(self, record):
        # We have to do the import here or Django will barf when it tries to
        # load this because the apps aren't loaded at that point
        from .models import Log

        kwargs = {"message": record.msg, "level": record.levelno}

        if hasattr(record, "group"):
            kwargs["group"] = record.group

        Log.objects.create(**kwargs)
