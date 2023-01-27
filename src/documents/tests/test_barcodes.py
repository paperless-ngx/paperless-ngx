import os
import shutil
from unittest import mock

from django.conf import settings
from django.test import override_settings
from django.test import TestCase
from documents import barcodes
from documents import tasks
from documents.consumer import ConsumerError
from documents.tests.utils import DirectoriesMixin
from PIL import Image


class TestBarcode(DirectoriesMixin, TestCase):

    SAMPLE_DIR = os.path.join(
        os.path.dirname(__file__),
        "samples",
    )

    BARCODE_SAMPLE_DIR = os.path.join(SAMPLE_DIR, "barcodes")

    def test_barcode_reader_png(self):
        """
        GIVEN:
            - PNG file with separator barcode
        WHEN:
            - Image is scanned for codes
        THEN:
            - The barcode is detected
        """
        test_file = os.path.join(self.BARCODE_SAMPLE_DIR, "barcode-39-PATCHT.png")
        img = Image.open(test_file)
        separator_barcode = settings.CONSUMER_BARCODE_STRING
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_pbm(self):
        """
        GIVEN:
            - Netpbm bitmap file with separator barcode
        WHEN:
            - Image is scanned for codes
        THEN:
            - The barcode is detected
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t.pbm",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_distortion_scratchy(self):
        """
        GIVEN:
            - Image containing high noise
        WHEN:
            - Image is scanned for codes
        THEN:
            - The barcode is detected
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-PATCHT-distortion.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_distortion_stretched(self):
        """
        GIVEN:
            - Image with a stretched barcode
        WHEN:
            - Image is scanned for codes
        THEN:
            - The barcode is detected
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-PATCHT-distortion2.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_unreadable(self):
        """
        GIVEN:
            - Image with a truly unreadable barcode
        WHEN:
            - Image is scanned for codes
        THEN:
            - No barcode is detected
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-PATCHT-unreadable.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), [])

    def test_barcode_reader_qr(self):
        """
        GIVEN:
            - Image file with QR separator barcode
        WHEN:
            - Image is scanned for codes
        THEN:
            - The barcode is detected
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "qr-code-PATCHT.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_128(self):
        """
        GIVEN:
            - Image file with 128 style separator barcode
        WHEN:
            - Image is scanned for codes
        THEN:
            - The barcode is detected
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-128-PATCHT.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_no_barcode(self):
        """
        GIVEN:
            - Image file with no barcode
        WHEN:
            - Image is scanned for codes
        THEN:
            - No barcode is detected
        """
        test_file = os.path.join(self.SAMPLE_DIR, "simple.png")
        img = Image.open(test_file)
        self.assertListEqual(barcodes.barcode_reader(img), [])

    def test_barcode_reader_custom_separator(self):
        """
        GIVEN:
            - Image file with custom separator barcode value
        WHEN:
            - Image is scanned for codes
        THEN:
            - The barcode is detected
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-custom.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["CUSTOM BARCODE"])

    def test_barcode_reader_custom_qr_separator(self):
        """
        GIVEN:
            - Image file with custom separator barcode value as a QR code
        WHEN:
            - Image is scanned for codes
        THEN:
            - The barcode is detected
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-qr-custom.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["CUSTOM BARCODE"])

    def test_barcode_reader_custom_128_separator(self):
        """
        GIVEN:
            - Image file with custom separator 128 barcode value
        WHEN:
            - Image is scanned for codes
        THEN:
            - The barcode is detected
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-128-custom.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["CUSTOM BARCODE"])

    def test_get_mime_type(self):
        """
        GIVEN:
            -
        WHEN:
            -
        THEN:
            -
        """
        tiff_file = os.path.join(
            self.SAMPLE_DIR,
            "simple.tiff",
        )
        pdf_file = os.path.join(
            self.SAMPLE_DIR,
            "simple.pdf",
        )
        png_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-128-custom.png",
        )
        tiff_file_no_extension = os.path.join(settings.SCRATCH_DIR, "testfile1")
        pdf_file_no_extension = os.path.join(settings.SCRATCH_DIR, "testfile2")
        shutil.copy(tiff_file, tiff_file_no_extension)
        shutil.copy(pdf_file, pdf_file_no_extension)

        self.assertEqual(barcodes.get_file_mime_type(tiff_file), "image/tiff")
        self.assertEqual(barcodes.get_file_mime_type(pdf_file), "application/pdf")
        self.assertEqual(
            barcodes.get_file_mime_type(tiff_file_no_extension),
            "image/tiff",
        )
        self.assertEqual(
            barcodes.get_file_mime_type(pdf_file_no_extension),
            "application/pdf",
        )
        self.assertEqual(barcodes.get_file_mime_type(png_file), "image/png")

    def test_convert_from_tiff_to_pdf(self):
        """
        GIVEN:
            -
        WHEN:
            -
        THEN:
            -
        """
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "simple.tiff",
        )
        dst = os.path.join(settings.SCRATCH_DIR, "simple.tiff")
        shutil.copy(test_file, dst)
        target_file = barcodes.convert_from_tiff_to_pdf(dst)
        file_extension = os.path.splitext(os.path.basename(target_file))[1]
        self.assertTrue(os.path.isfile(target_file))
        self.assertEqual(file_extension, ".pdf")

    def test_convert_error_from_pdf_to_pdf(self):
        """
        GIVEN:
            -
        WHEN:
            -
        THEN:
            -
        """
        test_file = os.path.join(
            self.SAMPLE_DIR,
            "simple.pdf",
        )
        dst = os.path.join(settings.SCRATCH_DIR, "simple.pdf")
        shutil.copy(test_file, dst)
        self.assertIsNone(barcodes.convert_from_tiff_to_pdf(dst))

    def test_scan_file_for_separating_barcodes(self):
        """
        GIVEN:
            -
        WHEN:
            -
        THEN:
            -
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [0])

    def test_scan_file_for_separating_barcodes_none_present(self):
        """
        GIVEN:
            -
        WHEN:
            -
        THEN:
            -
        """
        test_file = os.path.join(self.SAMPLE_DIR, "simple.pdf")
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [])

    def test_scan_file_for_separating_barcodes_middle_page(self):
        """
        GIVEN:
            - PDF file containing a separator on page 1 (zero indexed)
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Barcode is detected on page 1 (zero indexed)
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [1])

    def test_scan_file_for_separating_barcodes_multiple_pages(self):
        """
        GIVEN:
            - PDF file containing a separator on pages 2 and 5 (zero indexed)
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Barcode is detected on pages 2 and 5 (zero indexed)
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "several-patcht-codes.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [2, 5])

    def test_scan_file_for_separating_barcodes_upside_down(self):
        """
        GIVEN:
            - PDF file containing a separator on page 1 (zero indexed)
            - The barcode is upside down
        WHEN:
            - File is scanned for barcodes
        THEN:
            - Barcode is detected on page 1 (zero indexed)
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle_reverse.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [1])

    def test_scan_file_for_separating_barcodes_fax_decode(self):
        """
        GIVEN:
            - A PDF containing an image encoded as CCITT Group 4 encoding
        WHEN:
            - Barcode processing happens with the file
        THEN:
            - The barcode is still detected
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-fax-image.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [1])

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-qr.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [0])

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-custom.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [0])

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-qr-custom.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [0])

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-128-custom.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [0])

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-custom.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [])

    @override_settings(CONSUMER_BARCODE_STRING="ADAR-NEXTDOC")
    def test_scan_file_for_separating_qr_barcodes(self):
        """
        GIVEN:
            - Input PDF with certain QR codes that aren't detected at current size
        WHEN:
            - The input file is scanned for barcodes
        THEN:
            - QR codes are detected
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "many-qr-codes.pdf",
        )

        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertGreater(len(doc_barcode_info.barcodes), 0)
        self.assertListEqual(separator_page_numbers, [1])

    def test_separate_pages(self):
        """
        GIVEN:
            - Input PDF 2 pages after separation
        WHEN:
            - The input file separated at the barcode
        THEN:
            - Two new documents are produced
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle.pdf",
        )
        documents = barcodes.separate_pages(test_file, [1])

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
        test_file = os.path.join(
            os.path.dirname(__file__),
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-double.pdf",
        )
        pages = barcodes.separate_pages(test_file, [1, 2])

        self.assertEqual(len(pages), 2)

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle.pdf",
        )
        with self.assertLogs("paperless.barcodes", level="WARNING") as cm:
            pages = barcodes.separate_pages(test_file, [])
            self.assertEqual(pages, [])
            self.assertEqual(
                cm.output,
                [
                    "WARNING:paperless.barcodes:No pages to split on!",
                ],
            )

    def test_save_to_dir(self):
        """
        GIVEN:
            - File to save to a directory
        WHEN:
            - The file is saved
        THEN:
            - The file exists
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t.pdf",
        )
        barcodes.save_to_dir(test_file, target_dir=settings.SCRATCH_DIR)
        target_file = os.path.join(settings.SCRATCH_DIR, "patch-code-t.pdf")
        self.assertTrue(os.path.isfile(target_file))

    def test_save_to_dir_not_existing(self):
        """
        GIVEN:
            - File to save to a directory
            - The directory doesn't exist
        WHEN:
            - The file is saved
        THEN:
            - The file exists
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t.pdf",
        )
        nonexistingdir = "/nowhere"
        if os.path.isdir(nonexistingdir):
            self.fail("non-existing dir exists")

        with self.assertLogs("paperless.barcodes", level="WARNING") as cm:
            barcodes.save_to_dir(test_file, target_dir=nonexistingdir)
        self.assertEqual(
            cm.output,
            [
                f"WARNING:paperless.barcodes:{str(test_file)} or {str(nonexistingdir)} don't exist.",
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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t.pdf",
        )
        barcodes.save_to_dir(
            test_file,
            newname="newname.pdf",
            target_dir=settings.SCRATCH_DIR,
        )
        target_file = os.path.join(settings.SCRATCH_DIR, "newname.pdf")
        self.assertTrue(os.path.isfile(target_file))

    def test_barcode_splitter(self):
        """
        GIVEN:
            - Input file containing barcodes
        WHEN:
            - Input file is split on barcodes
        THEN:
            - Correct number of files produced
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle.pdf",
        )

        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(test_file, doc_barcode_info.pdf_path)
        self.assertTrue(len(separator_page_numbers) > 0)

        document_list = barcodes.separate_pages(test_file, separator_page_numbers)
        self.assertGreater(len(document_list), 0)

        for document in document_list:
            barcodes.save_to_dir(document, target_dir=settings.SCRATCH_DIR)

        target_file1 = os.path.join(
            settings.SCRATCH_DIR,
            "patch-code-t-middle_document_0.pdf",
        )
        target_file2 = os.path.join(
            settings.SCRATCH_DIR,
            "patch-code-t-middle_document_1.pdf",
        )

        self.assertTrue(os.path.isfile(target_file1))
        self.assertTrue(os.path.isfile(target_file2))

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle.pdf",
        )

        dst = os.path.join(settings.SCRATCH_DIR, "patch-code-t-middle.pdf")
        shutil.copy(test_file, dst)

        with mock.patch("documents.tasks.async_to_sync"):
            self.assertEqual(tasks.consume_file(dst), "File successfully split")

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle.tiff",
        )
        dst = os.path.join(settings.SCRATCH_DIR, "patch-code-t-middle.tiff")
        shutil.copy(test_file, dst)

        with mock.patch("documents.tasks.async_to_sync"):
            self.assertEqual(tasks.consume_file(dst), "File successfully split")

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
        test_file = os.path.join(
            self.SAMPLE_DIR,
            "simple.jpg",
        )
        dst = os.path.join(settings.SCRATCH_DIR, "simple.jpg")
        shutil.copy(test_file, dst)

        with self.assertLogs("paperless.barcodes", level="WARNING") as cm:
            self.assertIn("Success", tasks.consume_file(dst))

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle.tiff",
        )
        dst = os.path.join(settings.SCRATCH_DIR, "patch-code-t-middle")
        shutil.copy(test_file, dst)

        with mock.patch("documents.tasks.async_to_sync"):
            self.assertEqual(tasks.consume_file(dst), "File successfully split")

    def test_scan_file_for_separating_barcodes_password(self):
        """
        GIVEN:
            - Password protected PDF
        WHEN:
            - File is scanned for barcode
        THEN:
            - Scanning handles the exception without crashing
        """
        test_file = os.path.join(self.SAMPLE_DIR, "password-is-test.pdf")
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        separator_page_numbers = barcodes.get_separating_barcodes(
            doc_barcode_info.barcodes,
        )

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertListEqual(separator_page_numbers, [])


class TestAsnBarcodes(DirectoriesMixin, TestCase):

    SAMPLE_DIR = os.path.join(
        os.path.dirname(__file__),
        "samples",
    )

    BARCODE_SAMPLE_DIR = os.path.join(SAMPLE_DIR, "barcodes")

    def test_barcode_reader_asn_normal(self):
        """
        GIVEN:
            - Image containing standard ASNxxxxx barcode
        WHEN:
            - Image is scanned for barcodes
        THEN:
            - The barcode is located
            - The barcode value is correct
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-asn-123.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["ASN00123"])

    def test_barcode_reader_asn_invalid(self):
        """
        GIVEN:
            - Image containing invalid ASNxxxxx barcode
            - The number portion of the ASN is not a number
        WHEN:
            - Image is scanned for barcodes
        THEN:
            - The barcode is located
            - The barcode value is correct
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-asn-invalid.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["ASNXYZXYZ"])

    def test_barcode_reader_asn_custom_prefix(self):
        """
        GIVEN:
            - Image containing custom prefix barcode
        WHEN:
            - Image is scanned for barcodes
        THEN:
            - The barcode is located
            - The barcode value is correct
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-asn-custom-prefix.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["CUSTOM-PREFIX-00123"])

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-asn-custom-prefix.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        asn = barcodes.get_asn_from_barcodes(doc_barcode_info.barcodes)

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertEqual(asn, 123)

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-asn-invalid.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )

        asn = barcodes.get_asn_from_barcodes(doc_barcode_info.barcodes)

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-asn-123.pdf",
        )

        dst = os.path.join(settings.SCRATCH_DIR, "barcode-39-asn-123.pdf")
        shutil.copy(test_file, dst)

        with mock.patch("documents.consumer.Consumer.try_consume_file") as mocked_call:
            tasks.consume_file(dst)

            args, kwargs = mocked_call.call_args

            self.assertEqual(kwargs["override_asn"], 123)

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
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-asn-123.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        asn = barcodes.get_asn_from_barcodes(doc_barcode_info.barcodes)

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertEqual(asn, 123)

    def test_scan_file_for_asn_not_existing(self):
        """
        GIVEN:
            - PDF without an ASN barcode
        WHEN:
            - File is scanned for barcodes
        THEN:
            - No ASN is retrieved from the document
        """
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t.pdf",
        )
        doc_barcode_info = barcodes.scan_file_for_barcodes(
            test_file,
        )
        asn = barcodes.get_asn_from_barcodes(doc_barcode_info.barcodes)

        self.assertEqual(doc_barcode_info.pdf_path, test_file)
        self.assertEqual(asn, None)

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
        src = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-128-asn-too-large.pdf",
        )
        dst = os.path.join(self.dirs.scratch_dir, "barcode-128-asn-too-large.pdf")
        shutil.copy(src, dst)

        with mock.patch("documents.consumer.Consumer._send_progress"):
            self.assertRaisesMessage(
                ConsumerError,
                "Given ASN 4294967296 is out of range [0, 4,294,967,295]",
                tasks.consume_file,
                dst,
            )
