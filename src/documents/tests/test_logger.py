import logging
import uuid

from unittest import mock

from django.test import TestCase

from ..models import Log


class TestPaperlessLog(TestCase):

    def __init__(self, *args, **kwargs):
        TestCase.__init__(self, *args, **kwargs)
        self.logger = logging.getLogger(
            "documents.management.commands.document_consumer")

    def test_that_it_saves_at_all(self):

        kw = {"group": uuid.uuid4()}

        self.assertEqual(Log.objects.all().count(), 0)

        with mock.patch("logging.StreamHandler.emit") as __:

            # Debug messages are ignored by default
            self.logger.debug("This is a debugging message", extra=kw)
            self.assertEqual(Log.objects.all().count(), 0)

            self.logger.info("This is an informational message", extra=kw)
            self.assertEqual(Log.objects.all().count(), 1)

            self.logger.warning("This is an warning message", extra=kw)
            self.assertEqual(Log.objects.all().count(), 2)

            self.logger.error("This is an error message", extra=kw)
            self.assertEqual(Log.objects.all().count(), 3)

            self.logger.critical("This is a critical message", extra=kw)
            self.assertEqual(Log.objects.all().count(), 4)

    def test_groups(self):

        kw1 = {"group": uuid.uuid4()}
        kw2 = {"group": uuid.uuid4()}

        self.assertEqual(Log.objects.all().count(), 0)

        with mock.patch("logging.StreamHandler.emit") as __:

            # Debug messages are ignored by default
            self.logger.debug("This is a debugging message", extra=kw1)
            self.assertEqual(Log.objects.all().count(), 0)

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

    def test_groupped_query(self):

        kw = {"group": uuid.uuid4()}
        with mock.patch("logging.StreamHandler.emit") as __:
            self.logger.info("Message 0", extra=kw)
            self.logger.info("Message 1", extra=kw)
            self.logger.info("Message 2", extra=kw)
            self.logger.info("Message 3", extra=kw)

        self.assertEqual(Log.objects.all().by_group().count(), 1)
        self.assertEqual(
            Log.objects.all().by_group()[0]["messages"],
            "Message 0\nMessage 1\nMessage 2\nMessage 3"
        )
