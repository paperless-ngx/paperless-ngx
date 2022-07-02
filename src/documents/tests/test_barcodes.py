import os
import shutil
import tempfile
from unittest import mock

from django.conf import settings
from django.test import override_settings
from django.test import TestCase
from documents import barcodes
from documents import tasks
from documents.tests.utils import DirectoriesMixin
from PIL import Image


class TestBarcode(DirectoriesMixin, TestCase):
    def test_barcode_reader(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-39-PATCHT.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader2(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t.pbm",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_distorsion(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-39-PATCHT-distorsion.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_distorsion2(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-39-PATCHT-distorsion2.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_unreadable(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-39-PATCHT-unreadable.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), [])

    def test_barcode_reader_qr(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "qr-code-PATCHT.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_128(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-128-PATCHT.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_no_barcode(self):
        test_file = os.path.join(os.path.dirname(__file__), "samples", "simple.png")
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), [])

    def test_barcode_reader_custom_separator(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-39-custom.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["CUSTOM BARCODE"])

    def test_barcode_reader_custom_qr_separator(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-qr-custom.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["CUSTOM BARCODE"])

    def test_barcode_reader_custom_128_separator(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-128-custom.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["CUSTOM BARCODE"])

    def test_get_mime_type(self):
        tiff_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "simple.tiff",
        )
        pdf_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "simple.pdf",
        )
        png_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
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
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "simple.pdf",
        )
        dst = os.path.join(settings.SCRATCH_DIR, "simple.pdf")
        shutil.copy(test_file, dst)
        self.assertIsNone(barcodes.convert_from_tiff_to_pdf(dst))

    def test_scan_file_for_separating_barcodes(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t.pdf",
        )
        pages = barcodes.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [0])

    def test_scan_file_for_separating_barcodes2(self):
        test_file = os.path.join(os.path.dirname(__file__), "samples", "simple.pdf")
        pages = barcodes.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [])

    def test_scan_file_for_separating_barcodes3(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t-middle.pdf",
        )
        pages = barcodes.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [1])

    def test_scan_file_for_separating_barcodes4(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "several-patcht-codes.pdf",
        )
        pages = barcodes.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [2, 5])

    def test_scan_file_for_separating_barcodes_upsidedown(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t-middle_reverse.pdf",
        )
        pages = barcodes.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [1])

    def test_scan_file_for_separating_qr_barcodes(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t-qr.pdf",
        )
        pages = barcodes.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [0])

    @override_settings(CONSUMER_BARCODE_STRING="CUSTOM BARCODE")
    def test_scan_file_for_separating_custom_barcodes(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-39-custom.pdf",
        )
        pages = barcodes.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [0])

    @override_settings(CONSUMER_BARCODE_STRING="CUSTOM BARCODE")
    def test_scan_file_for_separating_custom_qr_barcodes(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-qr-custom.pdf",
        )
        pages = barcodes.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [0])

    @override_settings(CONSUMER_BARCODE_STRING="CUSTOM BARCODE")
    def test_scan_file_for_separating_custom_128_barcodes(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-128-custom.pdf",
        )
        pages = barcodes.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [0])

    def test_scan_file_for_separating_wrong_qr_barcodes(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "barcode-39-custom.pdf",
        )
        pages = barcodes.scan_file_for_separating_barcodes(test_file)
        self.assertEqual(pages, [])

    def test_separate_pages(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t-middle.pdf",
        )
        pages = barcodes.separate_pages(test_file, [1])
        self.assertEqual(len(pages), 2)

    def test_separate_pages_no_list(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t-middle.pdf",
        )
        with self.assertLogs("paperless.barcodes", level="WARNING") as cm:
            pages = barcodes.separate_pages(test_file, [])
            self.assertEqual(pages, [])
            self.assertEqual(
                cm.output,
                [
                    f"WARNING:paperless.barcodes:No pages to split on!",
                ],
            )

    def test_save_to_dir(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t.pdf",
        )
        tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)
        barcodes.save_to_dir(test_file, target_dir=tempdir)
        target_file = os.path.join(tempdir, "patch-code-t.pdf")
        self.assertTrue(os.path.isfile(target_file))

    def test_save_to_dir2(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t.pdf",
        )
        nonexistingdir = "/nowhere"
        if os.path.isdir(nonexistingdir):
            self.fail("non-existing dir exists")
        else:
            with self.assertLogs("paperless.barcodes", level="WARNING") as cm:
                barcodes.save_to_dir(test_file, target_dir=nonexistingdir)
            self.assertEqual(
                cm.output,
                [
                    f"WARNING:paperless.barcodes:{str(test_file)} or {str(nonexistingdir)} don't exist.",
                ],
            )

    def test_save_to_dir3(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t.pdf",
        )
        tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)
        barcodes.save_to_dir(test_file, newname="newname.pdf", target_dir=tempdir)
        target_file = os.path.join(tempdir, "newname.pdf")
        self.assertTrue(os.path.isfile(target_file))

    def test_barcode_splitter(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t-middle.pdf",
        )
        tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)
        separators = barcodes.scan_file_for_separating_barcodes(test_file)
        self.assertTrue(separators)
        document_list = barcodes.separate_pages(test_file, separators)
        self.assertTrue(document_list)
        for document in document_list:
            barcodes.save_to_dir(document, target_dir=tempdir)
        target_file1 = os.path.join(tempdir, "patch-code-t-middle_document_0.pdf")
        target_file2 = os.path.join(tempdir, "patch-code-t-middle_document_1.pdf")
        self.assertTrue(os.path.isfile(target_file1))
        self.assertTrue(os.path.isfile(target_file2))

    @override_settings(CONSUMER_ENABLE_BARCODES=True)
    def test_consume_barcode_file(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t-middle.pdf",
        )
        dst = os.path.join(settings.SCRATCH_DIR, "patch-code-t-middle.pdf")
        shutil.copy(test_file, dst)

        self.assertEqual(tasks.consume_file(dst), "File successfully split")

    @override_settings(
        CONSUMER_ENABLE_BARCODES=True,
        CONSUMER_BARCODE_TIFF_SUPPORT=True,
    )
    def test_consume_barcode_tiff_file(self):
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t-middle.tiff",
        )
        dst = os.path.join(settings.SCRATCH_DIR, "patch-code-t-middle.tiff")
        shutil.copy(test_file, dst)

        self.assertEqual(tasks.consume_file(dst), "File successfully split")

    @override_settings(
        CONSUMER_ENABLE_BARCODES=True,
        CONSUMER_BARCODE_TIFF_SUPPORT=True,
    )
    @mock.patch("documents.consumer.Consumer.try_consume_file")
    def test_consume_barcode_unsupported_jpg_file(self, m):
        """
        This test assumes barcode and TIFF support are enabled and
        the user uploads an unsupported image file (e.g. jpg)

        The function shouldn't try to scan for separating barcodes
        and continue archiving the file as is.
        """
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "simple.jpg",
        )
        dst = os.path.join(settings.SCRATCH_DIR, "simple.jpg")
        shutil.copy(test_file, dst)
        with self.assertLogs("paperless.tasks", level="WARNING") as cm:
            self.assertIn("Success", tasks.consume_file(dst))
        self.assertListEqual(
            cm.output,
            [
                "WARNING:paperless.tasks:Unsupported file format for barcode reader: image/jpeg",
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
        This test assumes barcode and TIFF support are enabled and
        the user uploads a supported image file, but without extension
        """
        test_file = os.path.join(
            os.path.dirname(__file__),
            "samples",
            "barcodes",
            "patch-code-t-middle.tiff",
        )
        dst = os.path.join(settings.SCRATCH_DIR, "patch-code-t-middle")
        shutil.copy(test_file, dst)

        self.assertEqual(tasks.consume_file(dst), "File successfully split")
