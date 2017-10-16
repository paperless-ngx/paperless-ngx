from django.test import TestCase

from ..signals import ConsumerDeclaration


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
                self.assertTrue(ConsumerDeclaration.test(name))

    def test_test_handles_various_file_names_false(self):

        prefixes = ("doc",)
        suffixes = ("txt", "markdown", "",)

        for prefix in prefixes:
            for suffix in suffixes:
                name = "{}.{}".format(prefix, suffix)
                self.assertFalse(ConsumerDeclaration.test(name))

        self.assertFalse(ConsumerDeclaration.test(""))
        self.assertFalse(ConsumerDeclaration.test("doc"))
