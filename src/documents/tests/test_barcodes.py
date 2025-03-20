import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings
from django.test import TestCase
from django.test import override_settings

from documents import tasks
from documents.barcodes import BarcodePlugin
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import Document
from documents.models import Tag
from documents.plugins.base import StopConsumeTaskError
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import DocumentConsumeDelayMixin
from documents.tests.utils import DummyProgressManager
from documents.tests.utils import FileSystemAssertsMixin
from documents.tests.utils import SampleDirMixin

try:
    import zxingcpp  # noqa: F401

    HAS_ZXING_LIB = True
except ImportError:
    HAS_ZXING_LIB = False


class GetReaderPluginMixin:
    @contextmanager
    def get_reader(self, filepath: Path) -> Generator[BarcodePlugin, None, None]:
        reader = BarcodePlugin(
            ConsumableDocument(DocumentSource.ConsumeFolder, original_file=filepath),
            DocumentMetadataOverrides(),
            DummyProgressManager(filepath.name, None),
            self.dirs.scratch_dir,
            "task-id",
        )
        reader.setup()
        yield reader
        reader.cleanup()


@override_settings(CONSUMER_BARCODE_SCANNER="PYZBAR")
class TestBarcode(
    DirectoriesMixin,
    FileSystemAssertsMixin,
    SampleDirMixin,
    GetReaderPluginMixin,
    TestCase,
):
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

        with self.get_reader(test_file) as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {0: False})

    @override_settings(
        CONSUMER_BARCODE_TIFF_SUPPORT=True,
    )
    def test_scan_tiff_for_separating_barcodes(self):
        """
        GIVEN:
            - TIFF image containing barcodes
        WHEN:
            - Consume task returns
        THEN:
            - The file was split
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle.tiff"

        with self.get_reader(test_file) as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertDictEqual(separator_page_numbers, {1: False})

    @override_settings(
        CONSUMER_BARCODE_TIFF_SUPPORT=True,
    )
    def test_scan_tiff_with_alpha_for_separating_barcodes(self):
        """
        GIVEN:
            - TIFF image containing barcodes
        WHEN:
            - Consume task returns
        THEN:
            - The file was split
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle-alpha.tiff"

        with self.get_reader(test_file) as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertDictEqual(separator_page_numbers, {1: False})

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
        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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

            with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertGreater(len(reader.barcodes), 0)
            self.assertDictEqual(separator_page_numbers, {1: False})

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
            with self.get_reader(test_file) as reader:
                reader.detect()
                warning = cm.output[0]
                expected_str = "WARNING:paperless.barcodes:File is likely password protected, not checking for barcodes"
                self.assertTrue(warning.startswith(expected_str))

                separator_page_numbers = reader.get_separation_pages()

                self.assertEqual(reader.pdf_file, test_file)
                self.assertDictEqual(separator_page_numbers, {})

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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
            documents = reader.separate_pages({1: False, 2: False})

            self.assertEqual(len(documents), 2)

    @override_settings(CONSUMER_ENABLE_BARCODES=True)
    def test_separate_pages_no_list(self):
        """
        GIVEN:
            - Input file to separate
        WHEN:
            - No separation pages are provided
        THEN:
            - Nothing happens
        """
        test_file = self.SAMPLE_DIR / "simple.pdf"

        with self.get_reader(test_file) as reader:
            try:
                reader.run()
            except StopConsumeTaskError:
                self.fail("Barcode reader split pages unexpectedly")

    @override_settings(
        CONSUMER_ENABLE_BARCODES=True,
        CONSUMER_BARCODE_TIFF_SUPPORT=True,
    )
    def test_consume_barcode_unsupported_jpg_file(self):
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

        with self.get_reader(test_file) as reader:
            self.assertFalse(reader.able_to_run)

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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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

    @override_settings(
        CONSUMER_ENABLE_BARCODES=True,
        CONSUMER_ENABLE_ASN_BARCODE=True,
        CONSUMER_BARCODE_RETAIN_SPLIT_PAGES=True,
    )
    def test_separate_pages_by_asn_barcodes_and_patcht_retain_pages(self):
        """
        GIVEN:
            - Input PDF with a patch code on page 3 and ASN barcodes on pages 1,5,6,9,11
            - Retain split pages is enabled
        WHEN:
            - Input file is split on barcodes
        THEN:
            - Correct number of files produced, split correctly by correct pages, and the split pages are retained
        """
        test_file = self.BARCODE_SAMPLE_DIR / "split-by-asn-2.pdf"

        with self.get_reader(test_file) as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(
                reader.pdf_file,
                test_file,
            )
            self.assertDictEqual(
                separator_page_numbers,
                {
                    2: True,
                    4: True,
                    5: True,
                    8: True,
                    10: True,
                },
            )


@override_settings(CONSUMER_BARCODE_SCANNER="PYZBAR")
class TestBarcodeNewConsume(
    DirectoriesMixin,
    FileSystemAssertsMixin,
    SampleDirMixin,
    DocumentConsumeDelayMixin,
    TestCase,
):
    @override_settings(CONSUMER_ENABLE_BARCODES=True)
    def test_consume_barcode_file(self):
        """
        GIVEN:
            - Incoming file with at 1 barcode producing 2 documents
            - Document includes metadata override information
        WHEN:
            - The document is split
        THEN:
            - Two new consume tasks are created
            - Metadata overrides are preserved for the new consume
            - The document source is unchanged (for consume templates)
        """
        test_file = self.BARCODE_SAMPLE_DIR / "patch-code-t-middle.pdf"
        temp_copy = self.dirs.scratch_dir / test_file.name
        shutil.copy(test_file, temp_copy)

        overrides = DocumentMetadataOverrides(tag_ids=[1, 2, 9])

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            self.assertEqual(
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=temp_copy,
                    ),
                    overrides,
                ),
                "Barcode splitting complete!",
            )
            # 2 new document consume tasks created
            self.assertEqual(self.consume_file_mock.call_count, 2)

            self.assertIsNotFile(temp_copy)

            # Check the split files exist
            # Check the source is unchanged
            # Check the overrides are unchanged
            for (
                new_input_doc,
                new_doc_overrides,
            ) in self.get_all_consume_delay_call_args():
                self.assertEqual(new_input_doc.source, DocumentSource.ConsumeFolder)
                self.assertIsFile(new_input_doc.original_file)
                self.assertEqual(overrides, new_doc_overrides)


class TestAsnBarcode(DirectoriesMixin, SampleDirMixin, GetReaderPluginMixin, TestCase):
    @contextmanager
    def get_reader(self, filepath: Path) -> BarcodePlugin:
        reader = BarcodePlugin(
            ConsumableDocument(DocumentSource.ConsumeFolder, original_file=filepath),
            DocumentMetadataOverrides(),
            DummyProgressManager(filepath.name, None),
            self.dirs.scratch_dir,
            "task-id",
        )
        reader.setup()
        yield reader
        reader.cleanup()

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
        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
            asn = reader.asn

            self.assertEqual(reader.pdf_file, test_file)
            self.assertEqual(asn, None)

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

        with self.get_reader(test_file) as reader:
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

        with mock.patch("documents.tasks.ProgressManager", DummyProgressManager):
            tasks.consume_file(
                ConsumableDocument(
                    source=DocumentSource.ConsumeFolder,
                    original_file=dst,
                ),
                None,
            )

            document = Document.objects.first()

            self.assertEqual(document.archive_serial_number, 123)

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

        with self.get_reader(test_file) as reader:
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

        with self.get_reader(test_file) as reader:
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


class TestTagBarcode(DirectoriesMixin, SampleDirMixin, GetReaderPluginMixin, TestCase):
    @contextmanager
    def get_reader(self, filepath: Path) -> BarcodePlugin:
        reader = BarcodePlugin(
            ConsumableDocument(DocumentSource.ConsumeFolder, original_file=filepath),
            DocumentMetadataOverrides(),
            DummyProgressManager(filepath.name, None),
            self.dirs.scratch_dir,
            "task-id",
        )
        reader.setup()
        yield reader
        reader.cleanup()

    @override_settings(CONSUMER_ENABLE_TAG_BARCODE=True)
    def test_scan_file_without_matching_barcodes(self):
        """
        GIVEN:
            - PDF containing tag barcodes but none with matching prefix (default "TAG:")
        WHEN:
            - File is scanned for barcodes
        THEN:
            - No TAG has been created
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-asn-custom-prefix.pdf"
        with self.get_reader(test_file) as reader:
            reader.run()
            tags = reader.metadata.tag_ids
            self.assertEqual(tags, None)

    @override_settings(
        CONSUMER_ENABLE_TAG_BARCODE=False,
        CONSUMER_TAG_BARCODE_MAPPING={"CUSTOM-PREFIX-(.*)": "\\g<1>"},
    )
    def test_scan_file_with_matching_barcode_but_function_disabled(self):
        """
        GIVEN:
            - PDF containing a tag barcode with matching custom prefix
            - The tag barcode functionality is disabled
        WHEN:
            - File is scanned for barcodes
        THEN:
            - No TAG has been created
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-asn-custom-prefix.pdf"
        with self.get_reader(test_file) as reader:
            reader.run()
            tags = reader.metadata.tag_ids
            self.assertEqual(tags, None)

    @override_settings(
        CONSUMER_ENABLE_TAG_BARCODE=True,
        CONSUMER_TAG_BARCODE_MAPPING={"CUSTOM-PREFIX-(.*)": "\\g<1>"},
    )
    def test_scan_file_for_tag_custom_prefix(self):
        """
        GIVEN:
            - PDF containing a tag barcode with custom prefix
            - The barcode mapping accepts this prefix and removes it from the mapped tag value
            - The created tag is the non-prefixed values
        WHEN:
            - File is scanned for barcodes
        THEN:
            - The TAG is located
            - One TAG has been created
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-asn-custom-prefix.pdf"
        with self.get_reader(test_file) as reader:
            reader.metadata.tag_ids = [99]
            reader.run()
            self.assertEqual(reader.pdf_file, test_file)
            tags = reader.metadata.tag_ids
            self.assertEqual(len(tags), 2)
            self.assertEqual(tags[0], 99)
            self.assertEqual(Tag.objects.get(name__iexact="00123").pk, tags[1])

    @override_settings(
        CONSUMER_ENABLE_TAG_BARCODE=True,
        CONSUMER_TAG_BARCODE_MAPPING={"ASN(.*)": "\\g<1>"},
    )
    def test_scan_file_for_many_custom_tags(self):
        """
        GIVEN:
            - PDF containing multiple tag barcode with custom prefix
            - The barcode mapping accepts this prefix and removes it from the mapped tag value
            - The created tags are the non-prefixed values
        WHEN:
            - File is scanned for barcodes
        THEN:
            - The TAG is located
            - File Tags have been created
        """
        test_file = self.BARCODE_SAMPLE_DIR / "split-by-asn-1.pdf"
        with self.get_reader(test_file) as reader:
            reader.run()
            tags = reader.metadata.tag_ids
            self.assertEqual(len(tags), 5)
            self.assertEqual(Tag.objects.get(name__iexact="00123").pk, tags[0])
            self.assertEqual(Tag.objects.get(name__iexact="00124").pk, tags[1])
            self.assertEqual(Tag.objects.get(name__iexact="00125").pk, tags[2])
            self.assertEqual(Tag.objects.get(name__iexact="00126").pk, tags[3])
            self.assertEqual(Tag.objects.get(name__iexact="00127").pk, tags[4])

    @override_settings(
        CONSUMER_ENABLE_TAG_BARCODE=True,
        CONSUMER_TAG_BARCODE_MAPPING={"CUSTOM-PREFIX-(.*)": "\\g<3>"},
    )
    def test_scan_file_for_tag_raises_value_error(self):
        """
        GIVEN:
            - Any error occurs during tag barcode processing
        THEN:
            - The processing should be skipped and not break the import
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-asn-custom-prefix.pdf"
        with self.get_reader(test_file) as reader:
            reader.run()
            # expect error to be caught and logged only
            tags = reader.metadata.tag_ids
            self.assertEqual(tags, None)
