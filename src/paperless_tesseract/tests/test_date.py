import datetime
import os
import shutil
from unittest import mock
from uuid import uuid4

from dateutil import tz
from django.test import TestCase

from ..parsers import RasterisedDocumentParser
from django.conf import settings


class TestDate(TestCase):

    SAMPLE_FILES = os.path.join(os.path.dirname(__file__), "samples")
    SCRATCH = "/tmp/paperless-tests-{}".format(str(uuid4())[:8])

    def setUp(self):
        os.makedirs(self.SCRATCH, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.SCRATCH)

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_date_format_1(self):
        input_file = os.path.join(self.SAMPLE_FILES, "")
        document = RasterisedDocumentParser(input_file)
        document._text = "lorem ipsum 130218 lorem ipsum"
        self.assertEqual(document.get_date(), None)

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_date_format_2(self):
        input_file = os.path.join(self.SAMPLE_FILES, "")
        document = RasterisedDocumentParser(input_file)
        document._text = "lorem ipsum 2018 lorem ipsum"
        self.assertEqual(document.get_date(), None)

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_date_format_3(self):
        input_file = os.path.join(self.SAMPLE_FILES, "")
        document = RasterisedDocumentParser(input_file)
        document._text = "lorem ipsum 20180213 lorem ipsum"
        self.assertEqual(document.get_date(), None)

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_date_format_4(self):
        input_file = os.path.join(self.SAMPLE_FILES, "")
        document = RasterisedDocumentParser(input_file)
        document._text = "lorem ipsum 13.02.2018 lorem ipsum"
        date = document.get_date()
        self.assertEqual(
            date,
            datetime.datetime(2018, 2, 13, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_date_format_5(self):
        input_file = os.path.join(self.SAMPLE_FILES, "")
        document = RasterisedDocumentParser(input_file)
        document._text = (
            "lorem ipsum 130218, 2018, 20180213 and lorem 13.02.2018 lorem "
            "ipsum")
        date = document.get_date()
        self.assertEqual(
            date,
            datetime.datetime(2018, 2, 13, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_date_format_6(self):
        input_file = os.path.join(self.SAMPLE_FILES, "")
        document = RasterisedDocumentParser(input_file)
        document._text = (
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
        self.assertEqual(document.get_date(), None)

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_date_format_7(self):
        input_file = os.path.join(self.SAMPLE_FILES, "")
        document = RasterisedDocumentParser(input_file)
        document._text = (
            "lorem ipsum\n"
            "März 2019\n"
            "lorem ipsum"
        )
        date = document.get_date()
        self.assertEqual(
            date,
            datetime.datetime(2019, 3, 1, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_date_format_8(self):
        input_file = os.path.join(self.SAMPLE_FILES, "")
        document = RasterisedDocumentParser(input_file)
        document._text = ("lorem ipsum\n"
                          "Wohnort\n"
                          "3100\n"
                          "IBAN\n"
                          "AT87 4534\n"
                          "1234\n"
                          "1234 5678\n"
                          "BIC\n"
                          "lorem ipsum\n"
                          "März 2020")
        self.assertEqual(document.get_date(),
                         datetime.datetime(2020, 3, 1, 0, 0,
                                           tzinfo=tz.gettz(
                                               settings.TIME_ZONE)))

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_date_format_9(self):
        input_file = os.path.join(self.SAMPLE_FILES, "")
        document = RasterisedDocumentParser(input_file)
        document._text = ("lorem ipsum\n"
                          "27. Nullmonth 2020\n"
                          "März 2020\n"
                          "lorem ipsum")
        self.assertEqual(document.get_date(),
                         datetime.datetime(2020, 3, 1, 0, 0,
                                           tzinfo=tz.gettz(
                                               settings.TIME_ZONE)))

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_1_pdf(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_1.pdf")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        date = document.get_date()
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(
            date,
            datetime.datetime(2018, 4, 1, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_1_png(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_1.png")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), False)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2018, 4, 1, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_2_pdf(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_2.pdf")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2013, 2, 1, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_2_png(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_2.png")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), False)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2013, 2, 1, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_3_pdf(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_3.pdf")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2018, 10, 5, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_3_png(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_3.png")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), False)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2018, 10, 5, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_4_pdf(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_4.pdf")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2018, 10, 5, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_4_png(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_4.png")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), False)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2018, 10, 5, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_5_pdf(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_5.pdf")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2018, 12, 17, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_5_png(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_5.png")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), False)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2018, 12, 17, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_6_pdf_us(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_6.pdf")
        document = RasterisedDocumentParser(input_file)
        document.get_text()
        document.DATE_ORDER = "MDY"
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2018, 12, 17, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_6_png_us(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_6.png")
        document = RasterisedDocumentParser(input_file)
        document.get_text()
        document.DATE_ORDER = "MDY"
        self.assertEqual(document._is_ocred(), False)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2018, 12, 17, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_6_pdf_eu(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_6.pdf")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(document.get_date(), None)

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_6_png_eu(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_6.png")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), False)
        self.assertEqual(document.get_date(), None)

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_7_pdf(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_7.pdf")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2018, 4, 1, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_8_pdf(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_8.pdf")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2017, 12, 31, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_get_text_9_pdf(self):
        input_file = os.path.join(self.SAMPLE_FILES, "tests_date_9.pdf")
        document = RasterisedDocumentParser(input_file)
        document.DATE_ORDER = 'DMY'
        document.get_text()
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(
            document.get_date(),
            datetime.datetime(2017, 12, 31, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_filename_date_1_pdf(self):
        input_file = os.path.join(self.SAMPLE_FILES,
                                  "tests_date_in_filename_2018-03-20_1.pdf")
        document = RasterisedDocumentParser(input_file)
        document.FILENAME_DATE_ORDER = 'YMD'
        document.get_text()
        date = document.get_date()
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(
            date,
            datetime.datetime(2018, 3, 20, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_filename_date_1_png(self):
        input_file = os.path.join(self.SAMPLE_FILES,
                                  "tests_date_in_filename_2018-03-20_1.png")
        document = RasterisedDocumentParser(input_file)
        document.FILENAME_DATE_ORDER = 'YMD'
        date = document.get_date()
        self.assertEqual(document._is_ocred(), False)
        self.assertEqual(
            date,
            datetime.datetime(2018, 3, 20, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_filename_date_2_pdf(self):
        input_file = os.path.join(self.SAMPLE_FILES,
                                  "2013-12-11_tests_date_in_filename_2.pdf")
        document = RasterisedDocumentParser(input_file)
        document.FILENAME_DATE_ORDER = 'YMD'
        date = document.get_date()
        self.assertEqual(document._is_ocred(), True)
        self.assertEqual(
            date,
            datetime.datetime(2013, 12, 11, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )

    @mock.patch(
        "paperless_tesseract.parsers.RasterisedDocumentParser.SCRATCH",
        SCRATCH
    )
    def test_filename_date_2_png(self):
        input_file = os.path.join(self.SAMPLE_FILES,
                                  "2013-12-11_tests_date_in_filename_2.png")
        document = RasterisedDocumentParser(input_file)
        document.FILENAME_DATE_ORDER = 'YMD'
        date = document.get_date()
        self.assertEqual(document._is_ocred(), False)
        self.assertEqual(
            date,
            datetime.datetime(2013, 12, 11, 0, 0,
                              tzinfo=tz.gettz(settings.TIME_ZONE))
        )
