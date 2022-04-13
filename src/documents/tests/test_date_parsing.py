import datetime
import os
import shutil
from uuid import uuid4

from dateutil import tz
from django.conf import settings
from django.test import override_settings
from django.test import TestCase
from documents.parsers import parse_date
from paperless.settings import DATE_ORDER


class TestDate(TestCase):

    SAMPLE_FILES = os.path.join(
        os.path.dirname(__file__),
        "../../paperless_tesseract/tests/samples",
    )
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
            datetime.datetime(2018, 2, 13, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    def test_date_format_5(self):
        text = "lorem ipsum 130218, 2018, 20180213 and lorem 13.02.2018 lorem " "ipsum"
        date = parse_date("", text)
        self.assertEqual(
            date,
            datetime.datetime(2018, 2, 13, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
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
        text = "lorem ipsum\n" "März 2019\n" "lorem ipsum"
        date = parse_date("", text)
        self.assertEqual(
            date,
            datetime.datetime(2019, 3, 1, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
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
            datetime.datetime(2020, 3, 1, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    @override_settings(SCRATCH_DIR=SCRATCH)
    def test_date_format_9(self):
        text = "lorem ipsum\n" "27. Nullmonth 2020\n" "März 2020\n" "lorem ipsum"
        self.assertEqual(
            parse_date("", text),
            datetime.datetime(2020, 3, 1, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    def test_date_format_10(self):
        text = "Customer Number Currency 22-MAR-2022 Credit Card 1934829304"
        self.assertEqual(
            parse_date("", text),
            datetime.datetime(2022, 3, 22, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    def test_date_format_11(self):
        text = "Customer Number Currency 22 MAR 2022 Credit Card 1934829304"
        self.assertEqual(
            parse_date("", text),
            datetime.datetime(2022, 3, 22, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    def test_date_format_12(self):
        text = "Customer Number Currency 22/MAR/2022 Credit Card 1934829304"
        self.assertEqual(
            parse_date("", text),
            datetime.datetime(2022, 3, 22, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    def test_date_format_13(self):
        text = "Customer Number Currency 22.MAR.2022 Credit Card 1934829304"
        self.assertEqual(
            parse_date("", text),
            datetime.datetime(2022, 3, 22, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    def test_date_format_14(self):
        text = "Customer Number Currency 22.MAR 2022 Credit Card 1934829304"
        self.assertEqual(
            parse_date("", text),
            datetime.datetime(2022, 3, 22, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    def test_date_format_15(self):
        text = "Customer Number Currency 22.MAR.22 Credit Card 1934829304"
        self.assertIsNone(parse_date("", text), None)

    def test_date_format_16(self):
        text = "Customer Number Currency 22.MAR,22 Credit Card 1934829304"
        self.assertIsNone(parse_date("", text), None)

    def test_date_format_17(self):
        text = "Customer Number Currency 22,MAR,2022 Credit Card 1934829304"
        self.assertIsNone(parse_date("", text), None)

    def test_date_format_18(self):
        text = "Customer Number Currency 22 MAR,2022 Credit Card 1934829304"
        self.assertIsNone(parse_date("", text), None)

    def test_crazy_date_past(self, *args):
        self.assertIsNone(parse_date("", "01-07-0590 00:00:00"))

    def test_crazy_date_future(self, *args):
        self.assertIsNone(parse_date("", "01-07-2350 00:00:00"))

    def test_crazy_date_with_spaces(self, *args):
        self.assertIsNone(parse_date("", "20 408000l 2475"))

    @override_settings(FILENAME_DATE_ORDER="YMD")
    def test_filename_date_parse_valid_ymd(self, *args):
        """
        GIVEN:
            - Date parsing from the filename is enabled
            - Filename date format is with Year Month Day (YMD)
            - Filename contains date matching the format

        THEN:
            - Should parse the date from the filename
        """
        self.assertEqual(
            parse_date("/tmp/Scan-2022-04-01.pdf", "No date in here"),
            datetime.datetime(2022, 4, 1, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    @override_settings(FILENAME_DATE_ORDER="DMY")
    def test_filename_date_parse_valid_dmy(self, *args):
        """
        GIVEN:
            - Date parsing from the filename is enabled
            - Filename date format is with Day Month Year (DMY)
            - Filename contains date matching the format

        THEN:
            - Should parse the date from the filename
        """
        self.assertEqual(
            parse_date("/tmp/Scan-10.01.2021.pdf", "No date in here"),
            datetime.datetime(2021, 1, 10, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    @override_settings(FILENAME_DATE_ORDER="YMD")
    def test_filename_date_parse_invalid(self, *args):
        """
        GIVEN:
            - Date parsing from the filename is enabled
            - Filename includes no date
            - File content includes no date

        THEN:
            - No date is parsed
        """
        self.assertIsNone(
            parse_date("/tmp/20 408000l 2475 - test.pdf", "No date in here"),
        )

    @override_settings(
        FILENAME_DATE_ORDER="YMD",
        IGNORE_DATES=(datetime.date(2022, 4, 1),),
    )
    def test_filename_date_ignored_use_content(self, *args):
        """
        GIVEN:
            - Date parsing from the filename is enabled
            - Filename date format is with Day Month Year (YMD)
            - Date order is Day Month Year (DMY, the default)
            - Filename contains date matching the format
            - Filename date is an ignored date
            - File content includes a date

        THEN:
            - Should parse the date from the content not filename
        """
        self.assertEqual(
            parse_date("/tmp/Scan-2022-04-01.pdf", "The matching date is 24.03.2022"),
            datetime.datetime(2022, 3, 24, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    @override_settings(
        IGNORE_DATES=(datetime.date(2019, 11, 3), datetime.date(2020, 1, 17)),
    )
    def test_ignored_dates_default_order(self, *args):
        """
        GIVEN:
            - Ignore dates have been set
            - File content includes ignored dates
            - File content includes 1 non-ignored date

        THEN:
            - Should parse the date non-ignored date from content
        """
        text = "lorem ipsum 110319, 20200117 and lorem 13.02.2018 lorem " "ipsum"
        self.assertEqual(
            parse_date("", text),
            datetime.datetime(2018, 2, 13, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )

    @override_settings(
        IGNORE_DATES=(datetime.date(2019, 11, 3), datetime.date(2020, 1, 17)),
        DATE_ORDER="YMD",
    )
    def test_ignored_dates_order_ymd(self, *args):
        """
        GIVEN:
            - Ignore dates have been set
            - Date order is Year Month Date (YMD)
            - File content includes ignored dates
            - File content includes 1 non-ignored date

        THEN:
            - Should parse the date non-ignored date from content
        """
        text = "lorem ipsum 190311, 20200117 and lorem 13.02.2018 lorem " "ipsum"

        self.assertEqual(
            parse_date("", text),
            datetime.datetime(2018, 2, 13, 0, 0, tzinfo=tz.gettz(settings.TIME_ZONE)),
        )
