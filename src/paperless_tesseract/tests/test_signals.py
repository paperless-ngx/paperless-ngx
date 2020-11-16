from django.test import TestCase

from paperless_tesseract.signals import tesseract_consumer_test


class SignalsTestCase(TestCase):

    def test_test_handles_various_file_names_true(self):

        prefixes = (
            "doc", "My Document", "Μυ Γρεεκ Δοψθμεντ", "Doc -with - tags",
            "A document with a . in it", "Doc with -- in it"
        )
        suffixes = (
            "pdf", "jpg", "jpeg", "gif", "png", "tiff", "tif", "pnm", "bmp",
            "PDF", "JPG", "JPEG", "GIF", "PNG", "TIFF", "TIF", "PNM", "BMP",
            "pDf", "jPg", "jpEg", "gIf", "pNg", "tIff", "tIf", "pNm", "bMp",
        )

        for prefix in prefixes:
            for suffix in suffixes:
                name = "{}.{}".format(prefix, suffix)
                self.assertTrue(tesseract_consumer_test(name))

    def test_test_handles_various_file_names_false(self):

        prefixes = ("doc",)
        suffixes = ("txt", "markdown", "",)

        for prefix in prefixes:
            for suffix in suffixes:
                name = "{}.{}".format(prefix, suffix)
                self.assertFalse(tesseract_consumer_test(name))

        self.assertFalse(tesseract_consumer_test(""))
        self.assertFalse(tesseract_consumer_test("doc"))
