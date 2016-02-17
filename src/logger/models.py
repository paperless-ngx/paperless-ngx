from django.db import models


class Log(models.Model):

    LEVEL_ERROR = 1
    LEVEL_WARNING = 2
    LEVEL_INFO = 3
    LEVEL_DEBUG = 4
    LEVELS = (
        (LEVEL_ERROR, "Error"),
        (LEVEL_WARNING, "Warning"),
        (LEVEL_INFO, "Informational"),
        (LEVEL_DEBUG, "Debugging"),
    )

    COMPONENT_CONSUMER = 1
    COMPONENT_MAIL = 2
    COMPONENTS = (
        (COMPONENT_CONSUMER, "Consumer"),
        (COMPONENT_MAIL, "Mail Fetcher")
    )

    time = models.DateTimeField(auto_now_add=True)
    message = models.TextField()
    level = models.PositiveIntegerField(choices=LEVELS, default=LEVEL_INFO)
    component = models.PositiveIntegerField(choices=COMPONENTS)

    class Meta(object):
        ordering = ("-time",)

    def __str__(self):
        return self.message

    @classmethod
    def error(cls, message, component):
        cls.objects.create(
            message=message, level=cls.LEVEL_ERROR, component=component)

    @classmethod
    def warning(cls, message, component):
        cls.objects.create(
            message=message, level=cls.LEVEL_WARNING, component=component)

    @classmethod
    def info(cls, message, component):
        cls.objects.create(
            message=message, level=cls.LEVEL_INFO, component=component)

    @classmethod
    def debug(cls, message, component):
        cls.objects.create(
            message=message, level=cls.LEVEL_DEBUG, component=component)
