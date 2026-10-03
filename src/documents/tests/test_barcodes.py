from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import zxingcpp
from django.conf import settings
from django.test import TestCase
from django.test import override_settings
from rest_framework import status

from documents import tasks
from documents.barcodes import BarcodePlugin
from documents.barcodes import read_barcode_values
from documents.consumer import ConsumerError
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import Document
from documents.models import DocumentBarcode
from documents.models import Tag
from documents.plugins.base import StopConsumeTaskError
from documents.tests.utils import ConsumeTaskMixin
from documents.tests.utils import SampleDirMixin
from paperless.config import BarcodeConfig
from paperless.models import ApplicationConfiguration
from paperless_testing.assertions import FileSystemAssertsMixin
from paperless_testing.dirs import DirectoriesMixin
from paperless_testing.fakes.progress import FakeProgressManager

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Generator

    from pytest_django.fixtures import Settings
    from pytest_mock import MockerFixture
    from rest_framework.test import APIClient

    from paperless_testing.dirs import PaperlessDirs


class GetReaderPluginMixin:
    @contextmanager
    def get_reader(self, filepath: Path) -> Generator[BarcodePlugin, None, None]:
        reader = BarcodePlugin(
            ConsumableDocument(DocumentSource.ConsumeFolder, original_file=filepath),
            DocumentMetadataOverrides(),
            FakeProgressManager(filepath.name, None),
            self.dirs.scratch_dir,
            "task-id",
        )
        reader.setup()
        yield reader
        reader.cleanup()


class TestBarcode(
    DirectoriesMixin,
    FileSystemAssertsMixin,
    SampleDirMixin,
    GetReaderPluginMixin,
    TestCase,
):
    def test_scan_file_for_separating_barcodes(self) -> None:
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
    def test_scan_tiff_for_separating_barcodes(self) -> None:
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

    @override_settings(CONSUMER_ENABLE_ASN_BARCODE=True)
    @pytest.mark.usefixtures("fake_progress_manager")
    def test_asn_barcode_duplicate_in_trash_fails(self) -> None:
        """
        GIVEN:
            - A document with ASN barcode 123 is in the trash
        WHEN:
            - A file with the same barcode ASN is consumed
        THEN:
            - The ASN check is re-run and consumption fails
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-asn-123.pdf"

        first_doc = Document.objects.create(
            title="First ASN 123",
            content="",
            checksum="asn123first",
            mime_type="application/pdf",
            archive_serial_number=123,
        )

        first_doc.delete()

        dupe_asn = settings.SCRATCH_DIR / "barcode-39-asn-123-second.pdf"
        shutil.copy(test_file, dupe_asn)

        with self.assertRaisesRegex(ConsumerError, r"ASN 123.*trash"):
            tasks.consume_file(
                ConsumableDocument(
                    source=DocumentSource.ConsumeFolder,
                    original_file=dupe_asn,
                ),
                None,
            )

    @override_settings(
        CONSUMER_BARCODE_TIFF_SUPPORT=True,
    )
    def test_scan_tiff_with_alpha_for_separating_barcodes(self) -> None:
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

    def test_scan_file_for_separating_barcodes_none_present(self) -> None:
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

    def test_scan_file_for_separating_barcodes_middle_page(self) -> None:
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

    def test_scan_file_for_separating_barcodes_multiple_pages(self) -> None:
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

    def test_scan_file_for_separating_barcodes_hard_to_detect(self) -> None:
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

    def test_scan_file_for_separating_barcodes_unreadable(self) -> None:
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

    def test_scan_file_for_separating_barcodes_fax_decode(self) -> None:
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

    def test_scan_file_for_separating_qr_barcodes(self) -> None:
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
    def test_scan_file_for_separating_custom_barcodes(self) -> None:
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
    def test_scan_file_for_separating_custom_qr_barcodes(self) -> None:
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
    def test_scan_file_for_separating_custom_128_barcodes(self) -> None:
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

    def test_scan_file_for_separating_wrong_qr_barcodes(self) -> None:
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
    def test_scan_file_qr_barcodes_was_problem(self) -> None:
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

    def test_scan_file_for_separating_barcodes_password(self) -> None:
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

    def test_separate_pages(self) -> None:
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

    def test_separate_pages_double_code(self) -> None:
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
    def test_separate_pages_no_list(self) -> None:
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
    def test_consume_barcode_unsupported_jpg_file(self) -> None:
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
    def test_separate_pages_by_asn_barcodes_and_patcht(self) -> None:
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
    def test_separate_pages_by_asn_barcodes(self) -> None:
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
    def test_separate_pages_by_asn_barcodes_and_patcht_retain_pages(self) -> None:
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

    def test_barcode_config(self) -> None:
        """
        GIVEN:
            - Barcode app config is set (settings are not)
        WHEN:
            - Document with barcode is processed
        THEN:
            - The barcode config is used
        """
        app_config = ApplicationConfiguration.objects.first()
        assert app_config is not None
        app_config.barcodes_enabled = True
        app_config.barcode_string = "CUSTOM BARCODE"
        app_config.save()
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-custom.pdf"
        with self.get_reader(test_file) as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertEqual(reader.pdf_file, test_file)
            self.assertDictEqual(separator_page_numbers, {0: False})


class TestBarcodeNewConsume(
    DirectoriesMixin,
    FileSystemAssertsMixin,
    SampleDirMixin,
    ConsumeTaskMixin,
    TestCase,
):
    @override_settings(CONSUMER_ENABLE_BARCODES=True)
    @pytest.mark.usefixtures("fake_progress_manager")
    def test_consume_barcode_file(self) -> None:
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

        self.assertEqual(
            tasks.consume_file(
                ConsumableDocument(
                    source=DocumentSource.ConsumeFolder,
                    original_file=temp_copy,
                ),
                overrides,
            ),
            {"reason": "Barcode splitting complete!"},
        )
        # 2 new document consume tasks created
        self.assertEqual(self.consume_file_mock.call_count, 2)

        self.assertIsNotFile(temp_copy)

        # Check the split files exist
        # Check the original_path is set
        # Check the source is unchanged
        # Check the overrides are unchanged
        for (
            new_input_doc,
            new_doc_overrides,
        ) in self.get_all_consume_task_call_args():
            self.assertIsFile(new_input_doc.original_file)
            self.assertEqual(new_input_doc.original_path, temp_copy)
            self.assertEqual(new_input_doc.source, DocumentSource.ConsumeFolder)
            self.assertEqual(overrides, new_doc_overrides)


class TestAsnBarcode(DirectoriesMixin, SampleDirMixin, GetReaderPluginMixin, TestCase):
    @contextmanager
    def get_reader(self, filepath: Path) -> BarcodePlugin:
        reader = BarcodePlugin(
            ConsumableDocument(DocumentSource.ConsumeFolder, original_file=filepath),
            DocumentMetadataOverrides(),
            FakeProgressManager(filepath.name, None),
            self.dirs.scratch_dir,
            "task-id",
        )
        reader.setup()
        yield reader
        reader.cleanup()

    @override_settings(CONSUMER_ASN_BARCODE_PREFIX="CUSTOM-PREFIX-")
    def test_scan_file_for_asn_custom_prefix(self) -> None:
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

    def test_scan_file_for_asn_barcode(self) -> None:
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

    def test_scan_file_for_asn_not_found(self) -> None:
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

    def test_scan_file_for_asn_barcode_invalid(self) -> None:
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
    @pytest.mark.usefixtures("fake_progress_manager")
    def test_consume_barcode_file_asn_assignment(self) -> None:
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

        tasks.consume_file(
            ConsumableDocument(
                source=DocumentSource.ConsumeFolder,
                original_file=dst,
            ),
            None,
        )

        document = Document.objects.first()
        assert document is not None

        self.assertEqual(document.archive_serial_number, 123)

    def test_scan_file_for_qrcode_without_upscale(self) -> None:
        """
        GIVEN:
            - A printed and scanned PDF document with a rather small QR code
        WHEN:
            - ASN barcode detection is run with default settings
        THEN:
            - ASN 123 is detected
        """

        test_file = self.BARCODE_SAMPLE_DIR / "barcode-qr-asn-000123-upscale-dpi.pdf"

        with self.get_reader(test_file) as reader:
            reader.detect()
            self.assertEqual(len(reader.barcodes), 1)
            self.assertEqual(reader.asn, 123)

    @override_settings(CONSUMER_BARCODE_DPI=600)
    @override_settings(CONSUMER_BARCODE_UPSCALE=1.5)
    def test_scan_file_for_qrcode_with_upscale(self) -> None:
        """
        GIVEN:
            - A printed and scanned PDF document with a rather small QR code
        WHEN:
            - ASN barcode detection is run with 600dpi and an upscale factor of 1.5
        THEN:
            - ASN 123 is detected
        """

        test_file = self.BARCODE_SAMPLE_DIR / "barcode-qr-asn-000123-upscale-dpi.pdf"

        with self.get_reader(test_file) as reader:
            reader.detect()
            self.assertEqual(len(reader.barcodes), 1)
            self.assertEqual(reader.asn, 123)


class TestTagBarcode(DirectoriesMixin, SampleDirMixin, GetReaderPluginMixin, TestCase):
    @contextmanager
    def get_reader(self, filepath: Path) -> BarcodePlugin:
        reader = BarcodePlugin(
            ConsumableDocument(DocumentSource.ConsumeFolder, original_file=filepath),
            DocumentMetadataOverrides(),
            FakeProgressManager(filepath.name, None),
            self.dirs.scratch_dir,
            "task-id",
        )
        reader.setup()
        yield reader
        reader.cleanup()

    @override_settings(
        CONSUMER_ENABLE_TAG_BARCODE=True,
        CONSUMER_TAG_BARCODE_MAPPING={"TAG:(.*)": "\\g<1>"},
    )
    def test_barcode_without_tag_match(self) -> None:
        """
        GIVEN:
            - Barcode that does not match any TAG mapping pattern
            - TAG mapping configured for "TAG:" prefix only
        WHEN:
            - is_tag property is checked on an ASN barcode
        THEN:
            - Returns False
        """
        test_file = self.BARCODE_SAMPLE_DIR / "barcode-39-asn-123.pdf"
        with self.get_reader(test_file) as reader:
            reader.detect()

            self.assertGreater(
                len(reader.barcodes),
                0,
                "Should have detected at least one barcode",
            )
            asn_barcode = reader.barcodes[0]
            self.assertFalse(
                asn_barcode.is_tag,
                f"ASN barcode '{asn_barcode.value}' should not match TAG: pattern",
            )

    @override_settings(CONSUMER_ENABLE_TAG_BARCODE=True)
    def test_scan_file_without_matching_barcodes(self) -> None:
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
    def test_scan_file_with_matching_barcode_but_function_disabled(self) -> None:
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
    def test_scan_file_for_tag_custom_prefix(self) -> None:
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
        CONSUMER_ENABLE_ASN_BARCODE=False,
    )
    def test_scan_file_for_many_custom_tags(self) -> None:
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
    def test_scan_file_for_tag_raises_value_error(self) -> None:
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

    @override_settings(
        CONSUMER_ENABLE_TAG_BARCODE=True,
        CONSUMER_TAG_BARCODE_SPLIT=True,
        CONSUMER_TAG_BARCODE_MAPPING={"TAG:(.*)": "\\g<1>"},
    )
    def test_split_on_tag_barcodes(self) -> None:
        """
        GIVEN:
            - PDF containing barcodes with TAG: prefix
            - Tag barcode splitting is enabled with TAG: mapping
        WHEN:
            - File is processed
        THEN:
            - Splits should occur at pages with TAG barcodes
            - Tags should NOT be assigned when tag splitting is enabled (they're assigned during re-consumption)
        """
        test_file = self.BARCODE_SAMPLE_DIR / "split-by-tag-basic.pdf"
        with self.get_reader(test_file) as reader:
            reader.detect()
            separator_page_numbers = reader.get_separation_pages()

            self.assertDictEqual(separator_page_numbers, {1: True, 3: True})

            tags = reader.metadata.tag_ids
            self.assertIsNone(tags)

    @override_settings(
        CONSUMER_ENABLE_TAG_BARCODE=True,
        CONSUMER_TAG_BARCODE_SPLIT=False,
        CONSUMER_TAG_BARCODE_MAPPING={"TAG:(.*)": "\\g<1>"},
    )
    def test_no_split_when_tag_split_disabled(self) -> None:
        """
        GIVEN:
            - PDF containing TAG barcodes (TAG:invoice, TAG:receipt)
            - Tag barcode splitting is disabled
        WHEN:
            - File is processed
        THEN:
            - No separation pages are identified
            - Tags are still extracted and assigned
        """
        test_file = self.BARCODE_SAMPLE_DIR / "split-by-tag-basic.pdf"
        with self.get_reader(test_file) as reader:
            reader.run()
            separator_page_numbers = reader.get_separation_pages()

            self.assertDictEqual(separator_page_numbers, {})

            tags = reader.metadata.tag_ids
            self.assertEqual(len(tags), 2)

    @override_settings(
        CONSUMER_ENABLE_BARCODES=True,
        CONSUMER_ENABLE_TAG_BARCODE=True,
        CONSUMER_TAG_BARCODE_SPLIT=True,
        CONSUMER_TAG_BARCODE_MAPPING={"TAG:(.*)": "\\g<1>"},
        CELERY_TASK_ALWAYS_EAGER=True,
        OCR_MODE="auto",
    )
    @pytest.mark.usefixtures("fake_progress_manager")
    def test_consume_barcode_file_tag_split_and_assignment(self) -> None:
        """
        GIVEN:
            - PDF containing TAG barcodes on pages 2 and 4 (TAG:invoice, TAG:receipt)
            - Tag barcode splitting is enabled
        WHEN:
            - File is consumed
        THEN:
            - PDF is split into 3 documents at barcode pages
            - Each split document has the appropriate TAG barcodes extracted and assigned
            - Document 1: page 1 (no tags)
            - Document 2: pages 2-3 with TAG:invoice
            - Document 3: pages 4-5 with TAG:receipt
        """
        test_file = self.BARCODE_SAMPLE_DIR / "split-by-tag-basic.pdf"
        dst = settings.SCRATCH_DIR / "split-by-tag-basic.pdf"
        shutil.copy(test_file, dst)

        result = tasks.consume_file(
            ConsumableDocument(
                source=DocumentSource.ConsumeFolder,
                original_file=dst,
            ),
            None,
        )

        self.assertEqual(result, {"reason": "Barcode splitting complete!"})

        documents = Document.objects.all().order_by("id")
        self.assertEqual(documents.count(), 3)

        doc1 = documents[0]
        self.assertEqual(doc1.tags.count(), 0)

        doc2 = documents[1]
        self.assertEqual(doc2.tags.count(), 1)
        _tag_1 = doc2.tags.first()
        assert _tag_1 is not None
        self.assertEqual(_tag_1.name, "invoice")

        doc3 = documents[2]
        self.assertEqual(doc3.tags.count(), 1)
        _tag_2 = doc3.tags.first()
        assert _tag_2 is not None
        self.assertEqual(_tag_2.name, "receipt")

    @override_settings(
        CONSUMER_ENABLE_TAG_BARCODE=True,
        CONSUMER_TAG_BARCODE_SPLIT=True,
        CONSUMER_TAG_BARCODE_MAPPING={"ASN(.*)": "ASN_\\g<1>", "TAG:(.*)": "\\g<1>"},
    )
    def test_split_by_mixed_asn_tag_backwards_compat(self) -> None:
        """
        GIVEN:
            - PDF with mixed ASN and TAG barcodes
            - Mapping that treats ASN barcodes as tags (backwards compatibility)
            - ASN12345 on page 1, TAG:personal on page 3, ASN13456 on page 5, TAG:business on page 7
        WHEN:
            - File is consumed
        THEN:
            - Both ASN and TAG barcodes trigger splits
            - Split points are at pages 3, 5, and 7 (page 1 never splits)
            - 4 separate documents are produced
        """
        test_file = self.BARCODE_SAMPLE_DIR / "split-by-tag-mixed-asn.pdf"

        with self.get_reader(test_file) as reader:
            reader.detect()
            separator_pages = reader.get_separation_pages()

            self.assertDictEqual(separator_pages, {2: True, 4: True, 6: True})

            document_list = reader.separate_pages(separator_pages)
            self.assertEqual(len(document_list), 4)

    @override_settings(
        CONSUMER_ENABLE_TAG_BARCODE=True,
        CONSUMER_TAG_BARCODE_SPLIT=True,
        CONSUMER_TAG_BARCODE_MAPPING={"TAG:(.*)": "\\g<1>"},
    )
    def test_split_by_tag_multiple_per_page(self) -> None:
        """
        GIVEN:
            - PDF with multiple TAG barcodes on same page
            - TAG:invoice and TAG:expense on page 2, TAG:receipt on page 4
        WHEN:
            - File is processed
        THEN:
            - Pages with barcodes trigger splits
            - Split points at pages 2 and 4
            - 3 separate documents are produced
        """
        test_file = self.BARCODE_SAMPLE_DIR / "split-by-tag-multiple-per-page.pdf"

        with self.get_reader(test_file) as reader:
            reader.detect()
            separator_pages = reader.get_separation_pages()

            self.assertDictEqual(separator_pages, {1: True, 3: True})

            document_list = reader.separate_pages(separator_pages)
            self.assertEqual(len(document_list), 3)


SAMPLE_VALUES = [
    {"page": 1, "value": "javascript:alert(1)", "format": "QRCode"},
    {"page": 2, "value": "https://example.com/invoice/4711", "format": "QRCode"},
]


@pytest.fixture
def samples_dir() -> Path:
    return Path(__file__).parent / "samples"


@pytest.fixture
def barcode_samples_dir(samples_dir: Path) -> Path:
    return samples_dir / "barcodes"


@pytest.fixture
def store_barcodes(settings: Settings) -> None:
    settings.CONSUMER_STORE_BARCODE_VALUES = True


@pytest.fixture
def barcode_reader(
    paperless_dirs: PaperlessDirs,
) -> Generator[Callable[[Path], BarcodePlugin], None, None]:
    readers: list[BarcodePlugin] = []

    def make(path: Path) -> BarcodePlugin:
        reader = BarcodePlugin(
            ConsumableDocument(DocumentSource.ConsumeFolder, original_file=path),
            DocumentMetadataOverrides(),
            FakeProgressManager(path.name, None),
            paperless_dirs.scratch_dir,
            "task-id",
        )
        reader.setup()
        readers.append(reader)
        return reader

    yield make
    for reader in readers:
        reader.cleanup()


@pytest.fixture
def consume_sample(
    paperless_dirs: PaperlessDirs,
    barcode_samples_dir: Path,
    fake_progress_manager: type[FakeProgressManager],
    settings: Settings,
) -> Callable[..., Document]:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.OCR_MODE = "auto"

    def consume(name: str, *, root_document_id: int | None = None) -> Document:
        dst = paperless_dirs.scratch_dir / name
        shutil.copy(barcode_samples_dir / name, dst)
        tasks.consume_file(
            ConsumableDocument(
                source=DocumentSource.ApiUpload
                if root_document_id
                else DocumentSource.ConsumeFolder,
                original_file=dst,
                root_document_id=root_document_id,
            ),
            None,
        )
        return Document.objects.latest("id")

    return consume


def _stored(document: Document) -> list[dict]:
    return list(document.barcodes.values("page", "value", "format"))


def test_formats_cover_zxing() -> None:
    """
    DocumentBarcode.Format matches the concrete formats of zxing-cpp, so a
    zxing-cpp update that adds or removes one fails here
    """
    members = zxingcpp.BarcodeFormat.__members__
    # skip NONE and the groups like AllLinear, including their aliases
    seen = {int(m) for n, m in members.items() if n == "NONE" or n.startswith("All")}
    concrete = set()
    for name, member in members.items():
        # aliases such as DataBarExpanded come after the name zxing reports
        if int(member) not in seen:
            seen.add(int(member))
            concrete.add(name)
    assert set(DocumentBarcode.Format.values) == concrete


@pytest.mark.django_db
class TestBarcodeValues:
    @pytest.mark.parametrize(
        ("filename", "mime_type", "tiff_support", "expected"),
        [
            pytest.param("simple.jpg", "image/jpeg", True, None, id="jpeg"),
            pytest.param("simple.tiff", "image/tiff", False, None, id="tiff-off"),
            pytest.param("simple.tiff", "image/tiff", True, [], id="tiff-on"),
        ],
    )
    def test_read_values_file_types(
        self,
        paperless_dirs: PaperlessDirs,
        samples_dir: Path,
        settings: Settings,
        filename: str,
        mime_type: str,
        tiff_support: bool,  # noqa: FBT001
        expected: list | None,
    ) -> None:
        """
        Files the scan doesn't support return None, so stored barcodes are
        kept instead of being replaced with an empty list
        """
        settings.CONSUMER_BARCODE_TIFF_SUPPORT = tiff_support
        values = read_barcode_values(
            samples_dir / filename,
            mime_type,
            BarcodeConfig(),
            paperless_dirs.scratch_dir,
        )
        assert values == expected

    def test_values_detected(
        self,
        barcode_reader: Callable[[Path], BarcodePlugin],
        barcode_samples_dir: Path,
        store_barcodes: None,
    ) -> None:
        reader = barcode_reader(barcode_samples_dir / "barcode-qr-url.pdf")
        assert reader.able_to_run
        reader.run()
        assert reader.metadata.barcodes == SAMPLE_VALUES

    def test_values_disabled(
        self,
        barcode_reader: Callable[[Path], BarcodePlugin],
        barcode_samples_dir: Path,
        settings: Settings,
    ) -> None:
        settings.CONSUMER_ENABLE_ASN_BARCODE = True
        reader = barcode_reader(barcode_samples_dir / "barcode-qr-url.pdf")
        reader.run()
        assert reader.metadata.barcodes is None

    def test_consume_and_reprocess(
        self,
        consume_sample: Callable[..., Document],
        admin_client: APIClient,
        store_barcodes: None,
    ) -> None:
        """
        GIVEN:
            - PDF with a QR code on each of its two pages
        WHEN:
            - File is consumed, the values are lost, and the document is reprocessed
        THEN:
            - The barcodes are stored, shown in the API and searchable
            - Reprocessing reads them again
        """
        document = consume_sample("barcode-qr-url.pdf")
        assert _stored(document) == SAMPLE_VALUES

        response = admin_client.get(f"/api/documents/{document.pk}/metadata/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["barcodes"] == SAMPLE_VALUES
        response = admin_client.get(f"/api/documents/{document.pk}/")
        assert "barcodes" not in response.data
        response = admin_client.get("/api/documents/?query=barcodes:invoice")
        assert [x["id"] for x in response.data["results"]] == [document.pk]
        response = admin_client.get("/api/documents/?query=invoice")
        assert response.data["results"] == []

        document.barcodes.all().delete()
        modified = Document.objects.get(pk=document.pk).modified
        tasks.update_document_content_maybe_archive_file(document.pk)

        assert _stored(document) == SAMPLE_VALUES
        assert Document.objects.get(pk=document.pk).modified > modified

    @pytest.mark.parametrize(
        "read_values",
        [
            pytest.param({"side_effect": RuntimeError("broken")}, id="scan-fails"),
            pytest.param({"return_value": None}, id="not-scannable"),
        ],
    )
    def test_reprocess_keeps_values(
        self,
        consume_sample: Callable[..., Document],
        mocker: MockerFixture,
        store_barcodes: None,
        read_values: dict,
    ) -> None:
        """
        GIVEN:
            - A document with stored barcodes
        WHEN:
            - It is reprocessed, but the barcodes can't be read
        THEN:
            - The stored barcodes are kept
        """
        document = consume_sample("barcode-qr-url.pdf")
        mocker.patch("documents.tasks.read_barcode_values", **read_values)

        tasks.update_document_content_maybe_archive_file(document.pk)

        assert _stored(document) == SAMPLE_VALUES

    def test_reprocess_tiff_support_off_keeps_values(
        self,
        consume_sample: Callable[..., Document],
        settings: Settings,
        store_barcodes: None,
    ) -> None:
        """
        GIVEN:
            - A TIFF document with barcodes stored while TIFF support was on
        WHEN:
            - TIFF support is turned off and the document is reprocessed
        THEN:
            - The stored barcodes are kept
        """
        settings.CONSUMER_BARCODE_TIFF_SUPPORT = True
        document = consume_sample("patch-code-t-middle.tiff")
        stored = _stored(document)
        assert stored

        settings.CONSUMER_BARCODE_TIFF_SUPPORT = False
        tasks.update_document_content_maybe_archive_file(document.pk)

        assert _stored(document) == stored

    def test_reprocess_values_disabled(
        self,
        consume_sample: Callable[..., Document],
        settings: Settings,
        store_barcodes: None,
    ) -> None:
        document = consume_sample("barcode-qr-url.pdf")
        settings.CONSUMER_STORE_BARCODE_VALUES = False

        assert tasks._read_barcodes_for_reprocess(document) is None

    def test_consume_version_stores_own_values(
        self,
        consume_sample: Callable[..., Document],
        admin_client: APIClient,
        store_barcodes: None,
    ) -> None:
        """
        GIVEN:
            - A document with stored barcodes
        WHEN:
            - A new version with a different barcode is consumed, like after
              rotating or removing pages
        THEN:
            - The version keeps its own barcodes, the original ones are kept
            - The metadata and the search use those of the newest version
        """
        root = consume_sample("barcode-qr-url.pdf")
        version = consume_sample("barcode-128-custom.pdf", root_document_id=root.pk)
        assert version.root_document == root
        assert _stored(version) == [
            {"page": 1, "value": "CUSTOM BARCODE", "format": "Code128"},
        ]
        assert root.barcodes.count() == 2
        assert [x.value for x in root.get_effective_barcodes()] == ["CUSTOM BARCODE"]

        response = admin_client.get(f"/api/documents/{root.pk}/metadata/")
        assert [x["value"] for x in response.data["barcodes"]] == ["CUSTOM BARCODE"]
        response = admin_client.get('/api/documents/?query=barcodes:"custom barcode"')
        assert [x["id"] for x in response.data["results"]] == [root.pk]
        response = admin_client.get("/api/documents/?query=barcodes:invoice")
        assert response.data["results"] == []

    def test_consume_version_scan_fails(
        self,
        consume_sample: Callable[..., Document],
        mocker: MockerFixture,
        store_barcodes: None,
    ) -> None:
        """
        A failed scan of a new version is logged and doesn't stop consumption
        """
        root = consume_sample("barcode-qr-url.pdf")
        mocker.patch(
            "documents.consumer.read_barcode_values",
            side_effect=RuntimeError("broken"),
        )
        version = consume_sample("barcode-128-custom.pdf", root_document_id=root.pk)
        assert version.root_document == root
        assert not version.barcodes.exists()
