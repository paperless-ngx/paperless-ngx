import shutil
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings
from django.test import TestCase
from django.test import override_settings

from documents import tasks
from documents.barcodes import BarcodeReader
from documents.consumer import ConsumerError
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentSource
from documents.models import Document
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin

try:
    import zxingcpp  # noqa: F401

    HAS_ZXING_LIB = True
except ImportError:
    HAS_ZXING_LIB = False


@override_settings(CONSUMER_BARCODE_SCANNER="PYZBAR")
class TestBarcode(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    SAMPLE_DIR = Path(__file__).parent / "samples"

    BARCODE_SAMPLE_DIR = SAMPLE_DIR / "barcodes"

    def test_scan_file_for_separating_barcodes(self):
        """
        GIVEN:
            - PDF containing barcodes
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Correct page index located
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {0: False})

    def test_scan_file_for_separating_barcodes_none_present(self):
        """
        GIVEN:
            - File with no barcodes
        WHEN:
            - File is scanned
        THEN:
            - No barcodes detected
            - No pages to split on
        """
        test_file = self.SAMPLE_DIR / "simple.pdf"
        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {})

    def test_scan_file_for_separating_barcodes_middle_page(self):
        """
        GIVEN:
            - PDF file containing a separator on page 1 (zero indexed)
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Barcode is detected on page 1 (zero indexed)
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {1: False})

    def test_scan_file_for_separating_barcodes_multiple_pages(self):
        """
        GIVEN:
            - PDF file containing a separator on pages 2 and 5 (zero indexed)
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Barcode is detected on pages 2 and 5 (zero indexed)
        """
        test_file = self.BARCODE_SAMPLE_DIR / "several-patcht-codes.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {2: False, 5: False})

    def test_scan_file_for_separating_barcodes_hard_to_detect(self):
        """
        GIVEN:
            - PDF file containing a separator on page 1 (zero indexed)
            - The barcode is upside down, fuzzy or distorted
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Barcode is detected on page 1 (zero indexed)
        """

        for test_file in [
            "patch-code-t-middle-reverse.pdf",
            "patch-code-t-middle-distorted.pdf",
            "patch-code-t-middle-fuzzy.pdf",
        ]:
            test_file = self.BARCODE_SAMPLE_DIR / test_file

            with BarcodeReader(test_file, "application/pdf") as reader:
                reader.detect()
                separator_page_numbers = reader.get_separation_pages()

                self.assertEqual(reader.pdf_file, test_file)
                self.assertDictEqual(separator_page_numbers, {1: False})

    def test_scan_file_for_separating_barcodes_unreadable(self):
        """
        GIVEN:
            - PDF file containing a separator on page 1 (zero indexed)
            - The barcode is not readable
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Barcode is detected on page 1 (zero indexed)
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle-unreadable.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {})

    def test_scan_file_for_separating_barcodes_fax_decode(self):
        """
        GIVEN:
            - A PDF containing an image encoded as CCITT Group 4 encoding
        WHEN:
            - Barcode processing happens with the file
        THEN:
            - The barcode is still detected
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-fax-image.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {1: False})

    def test_scan_file_for_separating_qr_barcodes(self):
        """
        GIVEN:
            - PDF file containing a separator on page 0 (zero indexed)
            - The barcode is a QR code
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Barcode is detected on page 0 (zero indexed)
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-qr.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {0: False})

    @override_settings(CONSUMER_BARCODE_STRING="CUSTOM BARCODE")
    def test_scan_file_for_separating_custom_barcodes(self):
        """
        GIVEN:
            - PDF file containing a separator on page 0 (zero indexed)
            - The barcode separation value is customized
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Barcode is detected on page 0 (zero indexed)
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-custom.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {0: False})

    @override_settings(CONSUMER_BARCODE_STRING="CUSTOM BARCODE")
    def test_scan_file_for_separating_custom_qr_barcodes(self):
        """
        GIVEN:
            - PDF file containing a separator on page 0 (zero indexed)
            - The barcode separation value is customized
            - The barcode is a QR code
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Barcode is detected on page 0 (zero indexed)
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-qr-custom.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {0: False})

    @override_settings(CONSUMER_BARCODE_STRING="CUSTOM BARCODE")
    def test_scan_file_for_separating_custom_128_barcodes(self):
        """
        GIVEN:
            - PDF file containing a separator on page 0 (zero indexed)
            - The barcode separation value is customized
            - The barcode is a 128 code
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Barcode is detected on page 0 (zero indexed)
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-128-custom.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {0: False})

    def test_scan_file_for_separating_wrong_qr_barcodes(self):
        """
        GIVEN:
            - PDF file containing a separator on page 0 (zero indexed)
            - The barcode value is customized
            - The separation value is NOT customized
        WHEN:
            - File is scanned for barcodes
        THEN:
            - No split pages are detected
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-custom.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {})

    @override_settings(CONSUMER_BARCODE_STRING="ADAR-NEXTDOC")
    def test_scan_file_qr_barcodes_was_problem(self):
        """
        GIVEN:
            - Input PDF with certain QR codes that aren't detected at current size
        WHEN:
            - The input file is scanned for barcodes
        THEN:
            - QR codes are detected
        """
        test_file = self.BARCODE_SAMPLE_DIR / "many-qr-codes.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertGreater(len(reader.barcodes), 0)
            self.assertDictEqual(separator_page_numbers, {1: False})

    def test_separate_pages(self):
        """
        GIVEN:
            - Input PDF 2 pages after separation
        WHEN:
            - The input file separated at the barcode
        THEN:
            - Two new documents are produced
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            documents = reader.separate_pages({1: False})

            self.assertEqual(reader.pdf_file, test_file)
            self.assertEqual(len(documents), 2)

    def test_separate_pages_double_code(self):
        """
        GIVEN:
            - Input PDF with two patch code pages in a row
        WHEN:
            - The input file is split
        THEN:
            - Only two files are output
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-double.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            documents = reader.separate_pages({1: False, 2: False})

            self.assertEqual(len(documents), 2)

    def test_separate_pages_no_list(self):
        """
        GIVEN:
            - Input file to separate
        WHEN:
            - No separation pages are provided
        THEN:
            - No new documents are produced
            - A warning is logged
        """
        test_file = self.SAMPLE_DIR / "simple.pdf"

        with self.assertLogs("paperless.barcodes", level="WARNING") as cm:
            with BarcodeReader(test_file, "application/pdf") as reader:
                success = reader.separate(DocumentSource.ApiUpload)
                self.assertFalse(success)
                self.assertEqual(
                    cm.output,
                    [
                        "WARNING:paperless.barcodes:No pages to split on!",
                    ],
                )

    def test_save_to_dir_given_name(self):
        """
        GIVEN:
            - File to save to a directory
            - There is a name override
        WHEN:
            - The file is saved
        THEN:
            - The file exists
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle.pdf"
        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.separate(DocumentSource.ApiUpload, "newname.pdf")

            self.assertEqual(reader.pdf_file, test_file)
            target_file1 = settings.CONSUMPTION_DIR / "0_newname.pdf"
            target_file2 = settings.CONSUMPTION_DIR / "1_newname.pdf"
            self.assertIsFile(target_file1)
            self.assertIsFile(target_file2)

    def test_barcode_splitter_api_upload(self):
        """
        GIVEN:
            - Input file containing barcodes
        WHEN:
            - Input file is split on barcodes
        THEN:
            - Correct number of files produced
        """
        sample_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle.pdf"
        test_file = settings.SCRATCH_DIR / "patch-code-t-middle.pdf"
        shutil.copy(sample_file, test_file)

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.separate(DocumentSource.ApiUpload)

            self.assertEqual(reader.pdf_file, test_file)

            target_file1 = (
                settings.CONSUMPTION_DIR / "patch-code-t-middle_document_0.pdf"
            )

            target_file2 = (
                settings.CONSUMPTION_DIR / "patch-code-t-middle_document_1.pdf"
            )

            self.assertIsFile(target_file1)
            self.assertIsFile(target_file2)

    def test_barcode_splitter_consume_dir(self):
        """
        GIVEN:
            - Input file containing barcodes
        WHEN:
            - Input file is split on barcodes
        THEN:
            - Correct number of files produced
        """
        sample_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle.pdf"
        test_file = settings.CONSUMPTION_DIR / "patch-code-t-middle.pdf"
        shutil.copy(sample_file, test_file)

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            reader.separate(DocumentSource.ConsumeFolder)

            self.assertEqual(reader.pdf_file, test_file)

            target_file1 = (
                settings.CONSUMPTION_DIR / "patch-code-t-middle_document_0.pdf"
            )

            target_file2 = (
                settings.CONSUMPTION_DIR / "patch-code-t-middle_document_1.pdf"
            )

            self.assertIsFile(target_file1)
            self.assertIsFile(target_file2)

    def test_barcode_splitter_consume_dir_recursive(self):
        """
        GIVEN:
            - Input file containing barcodes
            - Input file is within a directory structure of the consume folder
        WHEN:
            - Input file is split on barcodes
        THEN:
            - Correct number of files produced
            - Output files are within the same directory structure
        """
        sample_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle.pdf"
        test_file = (
            settings.CONSUMPTION_DIR / "tag1" / "tag2" / "patch-code-t-middle.pdf"
        )
        test_file.parent.mkdir(parents=True)
        shutil.copy(sample_file, test_file)

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.separate(DocumentSource.ConsumeFolder)

            self.assertEqual(reader.pdf_file, test_file)

            target_file1 = (
                settings.CONSUMPTION_DIR
                / "tag1"
                / "tag2"
                / "patch-code-t-middle_document_0.pdf"
            )

            target_file2 = (
                settings.CONSUMPTION_DIR
                / "tag1"
                / "tag2"
                / "patch-code-t-middle_document_1.pdf"
            )

            self.assertIsFile(target_file1)
            self.assertIsFile(target_file2)

    @override_settings(CONSUMER_ENABLE_BARCODES=True)
    def test_consume_barcode_file(self):
        """
        GIVEN:
            - Input file with barcodes given to consume task
        WHEN:
            - Consume task returns
        THEN:
            - The file was split
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle.pdf"

        dst = settings.SCRATCH_DIR / "patch-code-t-middle.pdf"
        shutil.copy(test_file, dst)

        with mock.patch("documents.tasks.async_to_sync"):
            self.assertEqual(
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=dst,
                    ),
                    None,
                ),
                "File successfully split",
            )

    @override_settings(
        CONSUMER_ENABLE_BARCODES=True,
        CONSUMER_BARCODE_TIFF_SUPPORT=True,
    )
    def test_consume_barcode_tiff_file(self):
        """
        GIVEN:
            - TIFF image containing barcodes
        WHEN:
            - Consume task returns
        THEN:
            - The file was split
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle.tiff"

        dst = settings.SCRATCH_DIR / "patch-code-t-middle.tiff"
        shutil.copy(test_file, dst)

        with mock.patch("documents.tasks.async_to_sync"):
            self.assertEqual(
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=dst,
                    ),
                    None,
                ),
                "File successfully split",
            )
        self.assertIsNotFile(dst)

    @override_settings(
        CONSUMER_ENABLE_BARCODES=True,
        CONSUMER_BARCODE_TIFF_SUPPORT=True,
    )
    def test_consume_barcode_tiff_file_with_alpha(self):
        """
        GIVEN:
            - TIFF image containing barcodes
            - TIFF image has an alpha layer
        WHEN:
            - Consume task handles the alpha layer and returns
        THEN:
            - The file was split without issue
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle-alpha.tiff"

        dst = settings.SCRATCH_DIR / "patch-code-t-middle.tiff"
        shutil.copy(test_file, dst)

        with mock.patch("documents.tasks.async_to_sync"):
            self.assertEqual(
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=dst,
                    ),
                    None,
                ),
                "File successfully split",
            )
        self.assertIsNotFile(dst)

    @override_settings(
        CONSUMER_ENABLE_BARCODES=True,
        CONSUMER_BARCODE_TIFF_SUPPORT=True,
    )
    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_consume_barcode_unsupported_jpg_file(self, m):
        """
        GIVEN:
            - JPEG image as input
        WHEN:
            - Consume task returns
        THEN:
            - Barcode reader reported warning
            - Consumption continued with the file
        """
        test_file = self.SAMPLE_DIR / "simple.jpg"

        dst = settings.SCRATCH_DIR / "simple.jpg"
        shutil.copy(test_file, dst)

        with self.assertLogs("paperless.barcodes", level="WARNING") as cm:
            self.assertIn(
                "Success",
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=dst,
                    ),
                    None,
                ),
            )

        self.assertListEqual(
            cm.output,
            [
                "WARNING:paperless.barcodes:Unsupported file format for barcode reader: image/jpeg",
            ],
        )
        m.assert_called_once()

        args, kwargs = m.call_args
        self.assertIsNone(kwargs["override_filename"])
        self.assertIsNone(kwargs["override_title"])
        self.assertIsNone(kwargs["override_correspondent_id"])
        self.assertIsNone(kwargs["override_document_type_id"])
        self.assertIsNone(kwargs["override_tag_ids"])

    @override_settings(
        CONSUMER_ENABLE_BARCODES=True,
        CONSUMER_BARCODE_TIFF_SUPPORT=True,
    )
    def test_consume_barcode_supported_no_extension_file(self):
        """
        GIVEN:
            - TIFF image containing barcodes
            - TIFF file is given without extension
        WHEN:
            - Consume task returns
        THEN:
            - The file was split
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle.tiff"

        dst = settings.SCRATCH_DIR / "patch-code-t-middle"
        shutil.copy(test_file, dst)

        with mock.patch("documents.tasks.async_to_sync"):
            self.assertEqual(
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=dst,
                    ),
                    None,
                ),
                "File successfully split",
            )
        self.assertIsNotFile(dst)

    def test_scan_file_for_separating_barcodes_password(self):
        """
        GIVEN:
            - Password protected PDF
        WHEN:
            - File is scanned for barcode
        THEN:
            - Scanning handles the exception without crashing
        """
        test_file = self.SAMPLE_DIR / "password-is-test.pdf"
        with self.assertLogs("paperless.barcodes", level="WARNING") as cm:
            with BarcodeReader(test_file, "application/pdf") as reader:
                reader.detect()
                warning = cm.output[0]
                expected_str = "WARNING:paperless.barcodes:File is likely password protected, not checking for barcodes"
                self.assertTrue(warning.startswith(expected_str))

                separator_page_numbers = reader.get_separation_pages()

                self.assertEqual(reader.pdf_file, test_file)
                self.assertDictEqual(separator_page_numbers, {})

    @override_settings(
        CONSUMER_ENABLE_BARCODES=True,
        CONSUMER_ENABLE_ASN_BARCODE=True,
    )
    def test_separate_pages_by_asn_barcodes_and_patcht(self):
        """
        GIVEN:
            - Input PDF with a patch code on page 3 and ASN barcodes on pages 1,5,6,9,11
        WHEN:
            - Input file is split on barcodes
        THEN:
            - Correct number of files produced, split correctly by correct pages
        """
        test_file = self.BARCODE_SAMPLE_DIR / "split-by-asn-2.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(
                reader.pdf_file,
                test_file,
            )
            self.assertDictEqual(
                separator_page_numbers,
                {
                    2: False,
                    4: True,
                    5: True,
                    8: True,
                    10: True,
                },
            )

            document_list = reader.separate_pages(separator_page_numbers)
            self.assertEqual(len(document_list), 6)

    @override_settings(
        CONSUMER_ENABLE_BARCODES=True,
        CONSUMER_ENABLE_ASN_BARCODE=True,
    )
    def test_separate_pages_by_asn_barcodes(self):
        """
        GIVEN:
            - Input PDF with ASN barcodes on pages 1,3,4,7,9
        WHEN:
            - Input file is split on barcodes
        THEN:
            - Correct number of files produced, split correctly by correct pages
        """
        test_file = self.BARCODE_SAMPLE_DIR / "split-by-asn-1.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(
                separator_page_numbers,
                {
                    2: True,
                    3: True,
                    6: True,
                    8: True,
                },
            )

            document_list = reader.separate_pages(separator_page_numbers)
            self.assertEqual(len(document_list), 5)


class TestAsnBarcode(DirectoriesMixin, TestCase):
    SAMPLE_DIR = Path(__file__).parent / "samples"

    BARCODE_SAMPLE_DIR = SAMPLE_DIR / "barcodes"

    @override_settings(CONSUMER_ASN_BARCODE_PREFIX="CUSTOM-PREFIX-")
    def test_scan_file_for_asn_custom_prefix(self):
        """
        GIVEN:
            - PDF containing an ASN barcode with custom prefix
            - The ASN value is 123
        WHEN:
            - File is scanned for barcodes
        THEN:
            - The ASN is located
            - The ASN integer value is correct
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-asn-custom-prefix.pdf"
        with BarcodeReader(test_file, "application/pdf") as reader:
            asn = reader.asn

            self.assertEqual(reader.pdf_file, test_file)
            self.assertEqual(asn, 123)

    def test_scan_file_for_asn_barcode(self):
        """
        GIVEN:
            - PDF containing an ASN barcode
            - The ASN value is 123
        WHEN:
            - File is scanned for barcodes
        THEN:
            - The ASN is located
            - The ASN integer value is correct
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-asn-123.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            asn = reader.asn

            self.assertEqual(reader.pdf_file, test_file)
            self.assertEqual(asn, 123)

    def test_scan_file_for_asn_not_found(self):
        """
        GIVEN:
            - PDF without an ASN barcode
        WHEN:
            - File is scanned for barcodes
        THEN:
            - No ASN is retrieved from the document
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            asn = reader.asn

            self.assertEqual(reader.pdf_file, test_file)
            self.assertEqual(asn, None)

    @override_settings(CONSUMER_ENABLE_ASN_BARCODE=True)
    def test_scan_file_for_asn_already_exists(self):
        """
        GIVEN:
            - PDF with an ASN barcode
            - ASN value already exists
        WHEN:
            - File is scanned for barcodes
        THEN:
            - ASN is retrieved from the document
            - Consumption fails
        """

        Document.objects.create(
            title="WOW",
            content="the content",
            archive_serial_number=123,
            checksum="456",
            mime_type="application/pdf",
        )

        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-asn-123.pdf"

        dst = settings.SCRATCH_DIR / "barcode-39-asn-123.pdf"
        shutil.copy(test_file, dst)

        with mock.patch("documents.consumer.Consumer._send_progress"):
            with self.assertRaises(ConsumerError) as cm, self.assertLogs(
                "paperless.consumer",
                level="ERROR",
            ) as logs_cm:
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=dst,
                    ),
                    None,
                )
            self.assertIn("Not consuming barcode-39-asn-123.pdf", str(cm.exception))
            error_str = logs_cm.output[0]
            expected_str = "ERROR:paperless.consumer:Not consuming barcode-39-asn-123.pdf: Given ASN already exists!"
            self.assertEqual(expected_str, error_str)

    def test_scan_file_for_asn_barcode_invalid(self):
        """
        GIVEN:
            - PDF containing an ASN barcode
            - The ASN value is XYZXYZ
        WHEN:
            - File is scanned for barcodes
        THEN:
            - The ASN is located
            - The ASN value is not used
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-asn-invalid.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            asn = reader.asn

            self.assertEqual(reader.pdf_file, test_file)

            self.assertEqual(reader.pdf_file, test_file)
            self.assertEqual(asn, None)

    @override_settings(CONSUMER_ENABLE_ASN_BARCODE=True)
    def test_consume_barcode_file_asn_assignment(self):
        """
        GIVEN:
            - PDF containing an ASN barcode
            - The ASN value is 123
        WHEN:
            - File is scanned for barcodes
        THEN:
            - The ASN is located
            - The ASN integer value is correct
            - The ASN is provided as the override value to the consumer
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-asn-123.pdf"

        dst = settings.SCRATCH_DIR / "barcode-39-asn-123.pdf"
        shutil.copy(test_file, dst)

        with mock.patch("documents.consumer.Consumer.try_consume_file") as mocked_call:
            tasks.consume_file(
                ConsumableDocument(
                    source=DocumentSource.ConsumeFolder,
                    original_file=dst,
                ),
                None,
            )

            args, kwargs = mocked_call.call_args

            self.assertEqual(kwargs["override_asn"], 123)

    @override_settings(CONSUMER_ENABLE_ASN_BARCODE=True)
    def test_asn_too_large(self):
        """
        GIVEN:
            - ASN from barcode enabled
            - Barcode contains too large an ASN value
        WHEN:
            - ASN from barcode checked for correctness
        THEN:
            - Exception is raised regarding size limits
        """
        src = self.BARCODE_SAMPLE_DIR / "barcode-128-asn-too-large.pdf"

        dst = self.dirs.scratch_dir / "barcode-128-asn-too-large.pdf"
        shutil.copy(src, dst)

        input_doc = ConsumableDocument(
            source=DocumentSource.ConsumeFolder,
            original_file=dst,
        )

        with mock.patch("documents.consumer.Consumer._send_progress"):
            self.assertRaisesMessage(
                ConsumerError,
                "Given ASN 4294967296 is out of range [0, 4,294,967,295]",
                tasks.consume_file,
                input_doc,
            )

    @override_settings(CONSUMER_BARCODE_SCANNER="PYZBAR")
    def test_scan_file_for_qrcode_without_upscale(self):
        """
        GIVEN:
            - A printed and scanned PDF document with a rather small QR code
        WHEN:
            - ASN barcode detection is run with default settings
            - pyzbar is used for detection, as zxing would behave differently, and detect the QR code
        THEN:
            - ASN is not detected
        """

        test_file = self.BARCODE_SAMPLE_DIR / "barcode-qr-asn-000123-upscale-dpi.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            self.assertEqual(len(reader.barcodes), 0)

    @override_settings(CONSUMER_BARCODE_SCANNER="PYZBAR")
    @override_settings(CONSUMER_BARCODE_DPI=600)
    @override_settings(CONSUMER_BARCODE_UPSCALE=1.5)
    def test_scan_file_for_qrcode_with_upscale(self):
        """
        GIVEN:
            - A printed and scanned PDF document with a rather small QR code
        WHEN:
            - ASN barcode detection is run with 600dpi and an upscale factor of 1.5 and pyzbar
            - pyzbar is used for detection, as zxing would behave differently.
              Upscaling is a workaround for detection problems with pyzbar,
              when you cannot switch to zxing (aarch64 build problems of zxing)
        THEN:
            - ASN 123 is detected
        """

        test_file = self.BARCODE_SAMPLE_DIR / "barcode-qr-asn-000123-upscale-dpi.pdf"

        with BarcodeReader(test_file, "application/pdf") as reader:
            reader.detect()
            self.assertEqual(len(reader.barcodes), 1)
            self.assertEqual(reader.asn, 123)


@pytest.mark.skipif(
    not HAS_ZXING_LIB,
    reason="No zxingcpp",
)
@override_settings(CONSUMER_BARCODE_SCANNER="ZXING")
class TestBarcodeZxing(TestBarcode):
    pass


@pytest.mark.skipif(
    not HAS_ZXING_LIB,
    reason="No zxingcpp",
)
@override_settings(CONSUMER_BARCODE_SCANNER="ZXING")
class TestAsnBarcodesZxing(TestAsnBarcode):
    pass
