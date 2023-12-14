from django.test import TestCase
from django.test import override_settings

from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from paperless.models import CommonSettings
from paperless.models import OcrSettings
from paperless_tesseract.parsers import RasterisedDocumentParser


class TestParserSettingsFromDb(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    @staticmethod
    def get_params():
        return RasterisedDocumentParser(None).construct_ocrmypdf_parameters(
            input_file="input.pdf",
            output_file="output.pdf",
            sidecar_file="sidecar.txt",
            mime_type="application/pdf",
            safe_fallback=False,
        )

    def test_db_settings_ocr_pages(self):
        with override_settings(OCR_PAGES=10):
            instance = OcrSettings.objects.all().first()
            instance.pages = 5
            instance.save()

            params = self.get_params()
        self.assertEqual(params["pages"], "1-5")

    def test_db_settings_ocr_language(self):
        with override_settings(OCR_LANGUAGE="eng+deu"):
            instance = OcrSettings.objects.all().first()
            instance.language = "fra+ita"
            instance.save()

            params = self.get_params()
        self.assertEqual(params["language"], "fra+ita")

    def test_db_settings_ocr_output_type(self):
        with override_settings(OCR_LANGUAGE="pdfa-3"):
            instance = OcrSettings.objects.all().first()
            instance.output_type = CommonSettings.OutputTypeChoices.PDF_A
            instance.save()

            params = self.get_params()
        self.assertEqual(params["output_type"], "pdfa")

    def test_db_settings_ocr_mode(self):
        with override_settings(OCR_MODE="redo"):
            instance = OcrSettings.objects.all().first()
            instance.mode = OcrSettings.ModeChoices.SKIP
            instance.save()

            params = self.get_params()
        self.assertTrue(params["skip_text"])
        self.assertNotIn("redo_ocr", params)
        self.assertNotIn("force_ocr", params)

    def test_db_settings_ocr_clean(self):
        with override_settings(OCR_CLEAN="clean-final"):
            instance = OcrSettings.objects.all().first()
            instance.unpaper_clean = OcrSettings.CleanChoices.CLEAN
            instance.save()

            params = self.get_params()
        self.assertTrue(params["clean"])
        self.assertNotIn("clean_final", params)

        with override_settings(OCR_CLEAN="clean-final"):
            instance = OcrSettings.objects.all().first()
            instance.unpaper_clean = OcrSettings.CleanChoices.FINAL
            instance.save()

            params = self.get_params()
        self.assertTrue(params["clean_final"])
        self.assertNotIn("clean", params)

    def test_db_settings_ocr_deskew(self):
        with override_settings(OCR_DESKEW=False):
            instance = OcrSettings.objects.all().first()
            instance.deskew = True
            instance.save()

            params = self.get_params()
        self.assertTrue(params["deskew"])

    def test_db_settings_ocr_rotate(self):
        with override_settings(OCR_ROTATE_PAGES=False, OCR_ROTATE_PAGES_THRESHOLD=30.0):
            instance = OcrSettings.objects.all().first()
            instance.rotate_pages = True
            instance.rotate_pages_threshold = 15.0
            instance.save()

            params = self.get_params()
        self.assertTrue(params["rotate_pages"])
        self.assertAlmostEqual(params["rotate_pages_threshold"], 15.0)

    def test_db_settings_ocr_max_pixels(self):
        with override_settings(OCR_MAX_IMAGE_PIXELS=2_000_000.0):
            instance = OcrSettings.objects.all().first()
            instance.max_image_pixels = 1_000_000.0
            instance.save()

            params = self.get_params()
        self.assertAlmostEqual(params["max_image_mpixels"], 1.0)

    def test_db_settings_ocr_color_convert(self):
        with override_settings(OCR_COLOR_CONVERSION_STRATEGY="LeaveColorUnchanged"):
            instance = OcrSettings.objects.all().first()
            instance.color_conversion_strategy = (
                OcrSettings.ColorConvertChoices.INDEPENDENT
            )
            instance.save()

            params = self.get_params()
        self.assertEqual(
            params["color_conversion_strategy"],
            "UseDeviceIndependentColor",
        )
