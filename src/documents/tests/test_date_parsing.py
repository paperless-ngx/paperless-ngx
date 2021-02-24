import datetime
import os
import shutil
from uuid import uuid4

from dateutil import tz
from django.conf import settings
from django.test import TestCase, override_settings

from documents.parsers import parse_date


class TestDate(TestCase):

    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "../../paperless_tesseract/tests/samples")
    SCRATCH = "/tmp/paperless-tests-{}".format(str(uuid4())[:8])

    def setUp(self):
        os.makedirs(self.SCRATCH, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.SCRATCH)

    def test_date_format_1(self):
        text = "lorem ipsum 130218 lorem ipsum"
        self.assertEqual(parse_date("", text), None)

    def test_date_format_2(self):
        text = "lorem ipsum 2018 lorem ipsum"
        self.assertEqual(parse_date("", text), None)

    def test_date_format_3(self):
        text = "lorem ipsum 20180213 lorem ipsum"
        self.assertEqual(parse_date("", text), None)

    def test_date_format_4(self):
        text = "lorem ipsum 13.02.2018 lorem ipsum"
        date = parse_date("", text)
        self.assertEqual(
            date,
            datetime.datetime(
                2018, 2, 13, 0, 0,
                tzinfo=tz.gettz(settings.TIME_ZONE)
            )
        )

    def test_date_format_5(self):
        text = (
            "lorem ipsum 130218, 2018, 20180213 and lorem 13.02.2018 lorem "
            "ipsum"
        )
        date = parse_date("", text)
        self.assertEqual(
            date,
            datetime.datetime(
                2018, 2, 13, 0, 0,
                tzinfo=tz.gettz(settings.TIME_ZONE)
            )
        )

    def test_date_format_6(self):
        text = (
            "lorem ipsum\n"
            "Wohnort\n"
            "3100\n"
            "IBAN\n"
            "AT87 4534\n"
            "1234\n"
            "1234 5678\n"
            "BIC\n"
            "lorem ipsum"
        )
        self.assertEqual(parse_date("", text), None)

    def test_date_format_7(self):
        text = (
            "lorem ipsum\n"
            "März 2019\n"
            "lorem ipsum"
        )
        date = parse_date("", text)
        self.assertEqual(
            date,
            datetime.datetime(
                2019, 3, 1, 0, 0,
                tzinfo=tz.gettz(settings.TIME_ZONE)
            )
        )

    def test_date_format_8(self):
        text = (
            "lorem ipsum\n"
            "Wohnort\n"
            "3100\n"
            "IBAN\n"
            "AT87 4534\n"
            "1234\n"
            "1234 5678\n"
            "BIC\n"
            "lorem ipsum\n"
            "März 2020"
        )
        self.assertEqual(
            parse_date("", text),
            datetime.datetime(
                2020, 3, 1, 0, 0,
                tzinfo=tz.gettz(settings.TIME_ZONE)
            )
        )

    @override_settings(SCRATCH_DIR=SCRATCH)
    def test_date_format_9(self):
        text = (
            "lorem ipsum\n"
            "27. Nullmonth 2020\n"
            "März 2020\n"
            "lorem ipsum"
        )
        self.assertEqual(
            parse_date("", text),
            datetime.datetime(
                2020, 3, 1, 0, 0,
                tzinfo=tz.gettz(settings.TIME_ZONE)
            )
        )

    def test_crazy_date_past(self, *args):
        self.assertIsNone(parse_date("", "01-07-0590 00:00:00"))

    def test_crazy_date_future(self, *args):
        self.assertIsNone(parse_date("", "01-07-2350 00:00:00"))

    def test_crazy_date_with_spaces(self, *args):
        self.assertIsNone(parse_date("", "20 408000l 2475"))

    @override_settings(FILENAME_DATE_ORDER="YMD")
    def test_filename_date_parse_invalid(self, *args):
        self.assertIsNone(parse_date("/tmp/20 408000l 2475 - test.pdf", "No date in here"))

    @override_settings(IGNORE_DATES=(datetime.date(2019, 11, 3), datetime.date(2020, 1, 17)))
    def test_ignored_dates(self, *args):
        text = (
            "lorem ipsum 110319, 20200117 and lorem 13.02.2018 lorem "
            "ipsum"
        )
        date = parse_date("", text)
        self.assertEqual(
            date,
            datetime.datetime(
                2018, 2, 13, 0, 0,
                tzinfo=tz.gettz(settings.TIME_ZONE)
            )
        )
