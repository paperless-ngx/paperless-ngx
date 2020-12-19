import logging
import uuid
from unittest import mock

from django.test import TestCase, override_settings

from ..models import Log


class TestPaperlessLog(TestCase):

    def __init__(self, *args, **kwargs):
        TestCase.__init__(self, *args, **kwargs)
        self.logger = logging.getLogger(
            "documents.management.commands.document_consumer")

    @override_settings(DISABLE_DBHANDLER=False)
    def test_that_it_saves_at_all(self):

        kw = {"group": uuid.uuid4()}

        self.assertEqual(Log.objects.all().count(), 0)

        with mock.patch("logging.StreamHandler.emit") as __:

            # Debug messages are ignored by default
            self.logger.debug("This is a debugging message", extra=kw)
            self.assertEqual(Log.objects.all().count(), 1)

            self.logger.info("This is an informational message", extra=kw)
            self.assertEqual(Log.objects.all().count(), 2)

            self.logger.warning("This is an warning message", extra=kw)
            self.assertEqual(Log.objects.all().count(), 3)

            self.logger.error("This is an error message", extra=kw)
            self.assertEqual(Log.objects.all().count(), 4)

            self.logger.critical("This is a critical message", extra=kw)
            self.assertEqual(Log.objects.all().count(), 5)

    @override_settings(DISABLE_DBHANDLER=False)
    def test_groups(self):

        kw1 = {"group": uuid.uuid4()}
        kw2 = {"group": uuid.uuid4()}

        self.assertEqual(Log.objects.all().count(), 0)

        with mock.patch("logging.StreamHandler.emit") as __:

            self.logger.info("This is an informational message", extra=kw2)
            self.assertEqual(Log.objects.all().count(), 1)
            self.assertEqual(Log.objects.filter(group=kw2["group"]).count(), 1)

            self.logger.warning("This is an warning message", extra=kw1)
            self.assertEqual(Log.objects.all().count(), 2)
            self.assertEqual(Log.objects.filter(group=kw1["group"]).count(), 1)

            self.logger.error("This is an error message", extra=kw2)
            self.assertEqual(Log.objects.all().count(), 3)
            self.assertEqual(Log.objects.filter(group=kw2["group"]).count(), 2)

            self.logger.critical("This is a critical message", extra=kw1)
            self.assertEqual(Log.objects.all().count(), 4)
            self.assertEqual(Log.objects.filter(group=kw1["group"]).count(), 2)
