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

    def test_ignored(self):
        with mock.patch("logging.StreamHandler.emit") as __:
            self.assertEqual(Log.objects.all().count(), 0)
            self.logger.info("This is an informational message")
            self.logger.warning("This is an informational message")
            self.logger.error("This is an informational message")
            self.logger.critical("This is an informational message")
            self.assertEqual(Log.objects.all().count(), 0)

    def test_that_it_saves_at_all(self):

        kw = {
            "group": uuid.uuid4(),
            "component": Log.COMPONENT_MAIL
        }

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

        kw1 = {
            "group": uuid.uuid4(),
            "component": Log.COMPONENT_MAIL
        }
        kw2 = {
            "group": uuid.uuid4(),
            "component": Log.COMPONENT_MAIL
        }

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

    def test_components(self):

        c1 = Log.COMPONENT_CONSUMER
        c2 = Log.COMPONENT_MAIL
        kw1 = {
            "group": uuid.uuid4(),
            "component": c1
        }
        kw2 = {
            "group": kw1["group"],
            "component": c2
        }

        self.assertEqual(Log.objects.all().count(), 0)

        with mock.patch("logging.StreamHandler.emit") as __:

            # Debug messages are ignored by default
            self.logger.debug("This is a debugging message", extra=kw1)
            self.assertEqual(Log.objects.all().count(), 0)

            self.logger.info("This is an informational message", extra=kw2)
            self.assertEqual(Log.objects.all().count(), 1)
            self.assertEqual(Log.objects.filter(component=c2).count(), 1)

            self.logger.warning("This is an warning message", extra=kw1)
            self.assertEqual(Log.objects.all().count(), 2)
            self.assertEqual(Log.objects.filter(component=c1).count(), 1)

            self.logger.error("This is an error message", extra=kw2)
            self.assertEqual(Log.objects.all().count(), 3)
            self.assertEqual(Log.objects.filter(component=c2).count(), 2)

            self.logger.critical("This is a critical message", extra=kw1)
            self.assertEqual(Log.objects.all().count(), 4)
            self.assertEqual(Log.objects.filter(component=c1).count(), 2)
