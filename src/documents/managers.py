from django.conf import settings

from django.db import models
from django.db.models.aggregates import Max


class GroupConcat(models.Aggregate):
    """
    Theoretically, this should work in Sqlite, PostgreSQL, and MySQL, but I've
    only ever tested it in Sqlite.
    """

    ENGINE_SQLITE = 1
    ENGINE_POSTGRESQL = 2
    ENGINE_MYSQL = 3
    ENGINES = {
        "django.db.backends.sqlite3": ENGINE_SQLITE,
        "django.db.backends.postgresql_psycopg2": ENGINE_POSTGRESQL,
        "django.db.backends.postgresql": ENGINE_POSTGRESQL,
        "django.db.backends.mysql": ENGINE_MYSQL
    }

    def __init__(self, expression, separator="\n", **extra):

        self.engine = self._get_engine()
        self.function = self._get_function()
        self.template = self._get_template(separator)

        models.Aggregate.__init__(
            self,
            expression,
            output_field=models.CharField(),
            **extra
        )

    def _get_engine(self):
        engine = settings.DATABASES["default"]["ENGINE"]
        try:
            return self.ENGINES[engine]
        except KeyError:
            raise NotImplementedError(
                "There's currently no support for {} when it comes to group "
                "concatenation in Paperless".format(engine)
            )

    def _get_function(self):
        if self.engine == self.ENGINE_POSTGRESQL:
            return "STRING_AGG"
        return "GROUP_CONCAT"

    def _get_template(self, separator):
        if self.engine == self.ENGINE_MYSQL:
            return "%(function)s(%(expressions)s SEPARATOR '{}')".format(
                separator)
        return "%(function)s(%(expressions)s, '{}')".format(separator)


class LogQuerySet(models.query.QuerySet):

    def by_group(self):
        return self.values("group").annotate(
            time=Max("modified"),
            messages=GroupConcat("message"),
        ).order_by("-time")


class LogManager(models.Manager):

    def get_queryset(self):
        return LogQuerySet(self.model, using=self._db)
