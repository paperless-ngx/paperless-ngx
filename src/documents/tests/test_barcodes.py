import os
import shutil
import tempfile
from unittest import mock

import pikepdf
from django.conf import settings
from django.test import override_settings
from django.test import TestCase
from documents import barcodes
from documents import tasks
from documents.tests.utils import DirectoriesMixin
from PIL import Image


class TestBarcode(DirectoriesMixin, TestCase):

    SAMPLE_DIR = os.path.join(
        os.path.dirname(__file__),
        "samples",
    )

    BARCODE_SAMPLE_DIR = os.path.join(SAMPLE_DIR, "barcodes")

    def test_barcode_reader(self):
        test_file = os.path.join(self.BARCODE_SAMPLE_DIR, "barcode-39-PATCHT.png")
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader2(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t.pbm",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_distorsion(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-PATCHT-distorsion.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_distorsion2(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-PATCHT-distorsion2.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_unreadable(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-PATCHT-unreadable.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), [])

    def test_barcode_reader_qr(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "qr-code-PATCHT.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_128(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-128-PATCHT.png",
        )
        img = Image.open(test_file)
        separator_barcode = str(settings.CONSUMER_BARCODE_STRING)
        self.assertEqual(barcodes.barcode_reader(img), [separator_barcode])

    def test_barcode_reader_no_barcode(self):
        test_file = os.path.join(self.SAMPLE_DIR, "simple.png")
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), [])

    def test_barcode_reader_custom_separator(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-custom.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["CUSTOM BARCODE"])

    def test_barcode_reader_custom_qr_separator(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-qr-custom.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["CUSTOM BARCODE"])

    def test_barcode_reader_custom_128_separator(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-128-custom.png",
        )
        img = Image.open(test_file)
        self.assertEqual(barcodes.barcode_reader(img), ["CUSTOM BARCODE"])

    def test_get_mime_type(self):
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
            self.SAMPLE_DIR,
            "simple.pdf",
        )
        dst = os.path.join(settings.SCRATCH_DIR, "simple.pdf")
        shutil.copy(test_file, dst)
        self.assertIsNone(barcodes.convert_from_tiff_to_pdf(dst))

    def test_scan_file_for_separating_barcodes(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t.pdf",
        )
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [0])

    def test_scan_file_for_separating_barcodes_none_present(self):
        test_file = os.path.join(self.SAMPLE_DIR, "simple.pdf")
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [])

    def test_scan_file_for_separating_barcodes3(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle.pdf",
        )
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [1])

    def test_scan_file_for_separating_barcodes4(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "several-patcht-codes.pdf",
        )
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [2, 5])

    def test_scan_file_for_separating_barcodes_upsidedown(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle_reverse.pdf",
        )
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [1])

    def test_scan_file_for_separating_barcodes_pillow_transcode_error(self):
        """
        GIVEN:
            - A PDF containing an image which cannot be transcoded to a PIL image
        WHEN:
            - The image tries to be transcoded to a PIL image, but fails
        THEN:
            - The barcode reader is still called
        """

        def _build_device_n_pdf(self, save_path: str):
            # Based on the pikepdf tests
            # https://github.com/pikepdf/pikepdf/blob/abb35ebe17d579d76abe08265e00cf8890a12a95/tests/test_image_access.py
            pdf = pikepdf.new()
            pdf.add_blank_page(page_size=(72, 72))
            imobj = pikepdf.Stream(
                pdf,
                bytes(range(0, 256)),
                BitsPerComponent=8,
                ColorSpace=pikepdf.Array(
                    [
                        pikepdf.Name.DeviceN,
                        pikepdf.Array([pikepdf.Name.Black]),
                        pikepdf.Name.DeviceCMYK,
                        pikepdf.Stream(
                            pdf,
                            b"{0 0 0 4 -1 roll}",  # Colorspace conversion function
                            FunctionType=4,
                            Domain=[0.0, 1.0],
                            Range=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
                        ),
                    ],
                ),
                Width=16,
                Height=16,
                Type=pikepdf.Name.XObject,
                Subtype=pikepdf.Name.Image,
            )
            pim = pikepdf.PdfImage(imobj)
            self.assertEqual(pim.mode, "DeviceN")
            self.assertTrue(pim.is_device_n)

            pdf.pages[0].Contents = pikepdf.Stream(pdf, b"72 0 0 72 0 0 cm /Im0 Do")
            pdf.pages[0].Resources = pikepdf.Dictionary(
                XObject=pikepdf.Dictionary(Im0=imobj),
            )
            pdf.save(save_path)

        with tempfile.NamedTemporaryFile(suffix="pdf") as device_n_pdf:
            # Build an offending file
            _build_device_n_pdf(self, str(device_n_pdf.name))
            with mock.patch("documents.barcodes.barcode_reader") as reader:
                reader.return_value = list()

                _, _ = barcodes.scan_file_for_separating_barcodes(
                    str(device_n_pdf.name),
                )

                reader.assert_called()

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
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [1])

    def test_scan_file_for_separating_qr_barcodes(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-qr.pdf",
        )
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [0])

    @override_settings(CONSUMER_BARCODE_STRING="CUSTOM BARCODE")
    def test_scan_file_for_separating_custom_barcodes(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-custom.pdf",
        )
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [0])

    @override_settings(CONSUMER_BARCODE_STRING="CUSTOM BARCODE")
    def test_scan_file_for_separating_custom_qr_barcodes(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-qr-custom.pdf",
        )
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [0])

    @override_settings(CONSUMER_BARCODE_STRING="CUSTOM BARCODE")
    def test_scan_file_for_separating_custom_128_barcodes(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-128-custom.pdf",
        )
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [0])

    def test_scan_file_for_separating_wrong_qr_barcodes(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "barcode-39-custom.pdf",
        )
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [])

    def test_separate_pages(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle.pdf",
        )
        pages = barcodes.separate_pages(test_file, [1])

        self.assertEqual(len(pages), 2)

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
            "samples",
            "barcodes",
            "patch-code-t-double.pdf",
        )
        pages = barcodes.separate_pages(test_file, [1, 2])

        self.assertEqual(len(pages), 2)

    def test_separate_pages_no_list(self):
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
                    f"WARNING:paperless.barcodes:No pages to split on!",
                ],
            )

    def test_save_to_dir(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t.pdf",
        )
        tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)
        barcodes.save_to_dir(test_file, target_dir=tempdir)
        target_file = os.path.join(tempdir, "patch-code-t.pdf")
        self.assertTrue(os.path.isfile(target_file))

    def test_save_to_dir2(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
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
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t.pdf",
        )
        tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)
        barcodes.save_to_dir(test_file, newname="newname.pdf", target_dir=tempdir)
        target_file = os.path.join(tempdir, "newname.pdf")
        self.assertTrue(os.path.isfile(target_file))

    def test_barcode_splitter(self):
        test_file = os.path.join(
            self.BARCODE_SAMPLE_DIR,
            "patch-code-t-middle.pdf",
        )
        tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)

        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(test_file, pdf_file)
        self.assertTrue(len(separator_page_numbers) > 0)

        document_list = barcodes.separate_pages(test_file, separator_page_numbers)
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
        This test assumes barcode and TIFF support are enabled and
        the user uploads an unsupported image file (e.g. jpg)

        The function shouldn't try to scan for separating barcodes
        and continue archiving the file as is.
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
        This test assumes barcode and TIFF support are enabled and
        the user uploads a supported image file, but without extension
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
            - pikepdf based scanning
        WHEN:
            - File is scanned for barcode
        THEN:
            - Scanning handle the exception without exception
        """
        test_file = os.path.join(self.SAMPLE_DIR, "password-is-test.pdf")
        pdf_file, separator_page_numbers = barcodes.scan_file_for_separating_barcodes(
            test_file,
        )

        self.assertEqual(pdf_file, test_file)
        self.assertListEqual(separator_page_numbers, [])
