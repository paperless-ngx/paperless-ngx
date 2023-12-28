import json

from django.test import TestCase
from django.test import override_settings

from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from paperless.models import ApplicationConfiguration
from paperless.models import CleanChoices
from paperless.models import ColorConvertChoices
from paperless.models import ModeChoices
from paperless.models import OutputTypeChoices
from paperless_tesseract.parsers import RasterisedDocumentParser


class TestParserSettingsFromDb(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    @staticmethod
    def get_params():
        """
        Helper to get just the OCRMyPDF parameters from the parser
        """
        return RasterisedDocumentParser(None).construct_ocrmypdf_parameters(
            input_file="input.pdf",
            output_file="output.pdf",
            sidecar_file="sidecar.txt",
            mime_type="application/pdf",
            safe_fallback=False,
        )

    def test_db_settings_ocr_pages(self):
        """
        GIVEN:
            - Django settings defines different value for OCR_PAGES than
              configuration object
        WHEN:
            - OCR parameters are constructed
        THEN:
            - Configuration from database is utilized
        """
        with override_settings(OCR_PAGES=10):
            instance = ApplicationConfiguration.objects.all().first()
            instance.pages = 5
            instance.save()

            params = self.get_params()
        self.assertEqual(params["pages"], "1-5")

    def test_db_settings_ocr_language(self):
        """
        GIVEN:
            - Django settings defines different value for OCR_LANGUAGE than
              configuration object
        WHEN:
            - OCR parameters are constructed
        THEN:
            - Configuration from database is utilized
        """
        with override_settings(OCR_LANGUAGE="eng+deu"):
            instance = ApplicationConfiguration.objects.all().first()
            instance.language = "fra+ita"
            instance.save()

            params = self.get_params()
        self.assertEqual(params["language"], "fra+ita")

    def test_db_settings_ocr_output_type(self):
        """
        GIVEN:
            - Django settings defines different value for OCR_OUTPUT_TYPE than
              configuration object
        WHEN:
            - OCR parameters are constructed
        THEN:
            - Configuration from database is utilized
        """
        with override_settings(OCR_OUTPUT_TYPE="pdfa-3"):
            instance = ApplicationConfiguration.objects.all().first()
            instance.output_type = OutputTypeChoices.PDF_A
            instance.save()

            params = self.get_params()
        self.assertEqual(params["output_type"], "pdfa")

    def test_db_settings_ocr_mode(self):
        """
        GIVEN:
            - Django settings defines different value for OCR_MODE than
              configuration object
        WHEN:
            - OCR parameters are constructed
        THEN:
            - Configuration from database is utilized
        """
        with override_settings(OCR_MODE="redo"):
            instance = ApplicationConfiguration.objects.all().first()
            instance.mode = ModeChoices.SKIP
            instance.save()

            params = self.get_params()
        self.assertTrue(params["skip_text"])
        self.assertNotIn("redo_ocr", params)
        self.assertNotIn("force_ocr", params)

    def test_db_settings_ocr_clean(self):
        """
        GIVEN:
            - Django settings defines different value for OCR_CLEAN than
              configuration object
        WHEN:
            - OCR parameters are constructed
        THEN:
            - Configuration from database is utilized
        """
        with override_settings(OCR_CLEAN="clean-final"):
            instance = ApplicationConfiguration.objects.all().first()
            instance.unpaper_clean = CleanChoices.CLEAN
            instance.save()

            params = self.get_params()
        self.assertTrue(params["clean"])
        self.assertNotIn("clean_final", params)

        with override_settings(OCR_CLEAN="clean-final"):
            instance = ApplicationConfiguration.objects.all().first()
            instance.unpaper_clean = CleanChoices.FINAL
            instance.save()

            params = self.get_params()
        self.assertTrue(params["clean_final"])
        self.assertNotIn("clean", params)

    def test_db_settings_ocr_deskew(self):
        """
        GIVEN:
            - Django settings defines different value for OCR_DESKEW than
              configuration object
        WHEN:
            - OCR parameters are constructed
        THEN:
            - Configuration from database is utilized
        """
        with override_settings(OCR_DESKEW=False):
            instance = ApplicationConfiguration.objects.all().first()
            instance.deskew = True
            instance.save()

            params = self.get_params()
        self.assertTrue(params["deskew"])

    def test_db_settings_ocr_rotate(self):
        """
        GIVEN:
            - Django settings defines different value for OCR_ROTATE_PAGES
              and OCR_ROTATE_PAGES_THRESHOLD than configuration object
        WHEN:
            - OCR parameters are constructed
        THEN:
            - Configuration from database is utilized
        """
        with override_settings(OCR_ROTATE_PAGES=False, OCR_ROTATE_PAGES_THRESHOLD=30.0):
            instance = ApplicationConfiguration.objects.all().first()
            instance.rotate_pages = True
            instance.rotate_pages_threshold = 15.0
            instance.save()

            params = self.get_params()
        self.assertTrue(params["rotate_pages"])
        self.assertAlmostEqual(params["rotate_pages_threshold"], 15.0)

    def test_db_settings_ocr_max_pixels(self):
        """
        GIVEN:
            - Django settings defines different value for OCR_MAX_IMAGE_PIXELS than
              configuration object
        WHEN:
            - OCR parameters are constructed
        THEN:
            - Configuration from database is utilized
        """
        with override_settings(OCR_MAX_IMAGE_PIXELS=2_000_000.0):
            instance = ApplicationConfiguration.objects.all().first()
            instance.max_image_pixels = 1_000_000.0
            instance.save()

            params = self.get_params()
        self.assertAlmostEqual(params["max_image_mpixels"], 1.0)

    def test_db_settings_ocr_color_convert(self):
        """
        GIVEN:
            - Django settings defines different value for OCR_COLOR_CONVERSION_STRATEGY than
              configuration object
        WHEN:
            - OCR parameters are constructed
        THEN:
            - Configuration from database is utilized
        """
        with override_settings(OCR_COLOR_CONVERSION_STRATEGY="LeaveColorUnchanged"):
            instance = ApplicationConfiguration.objects.all().first()
            instance.color_conversion_strategy = ColorConvertChoices.INDEPENDENT
            instance.save()

            params = self.get_params()
        self.assertEqual(
            params["color_conversion_strategy"],
            "UseDeviceIndependentColor",
        )

    def test_ocr_user_args(self):
        """
        GIVEN:
            - Django settings defines different value for OCR_USER_ARGS than
              configuration object
        WHEN:
            - OCR parameters are constructed
        THEN:
            - Configuration from database is utilized
        """
        with override_settings(
            OCR_USER_ARGS=json.dumps({"continue_on_soft_render_error": True}),
        ):
            instance = ApplicationConfiguration.objects.all().first()
            instance.user_args = {"unpaper_args": "--pre-rotate 90"}
            instance.save()

            params = self.get_params()

        self.assertIn("unpaper_args", params)
        self.assertEqual(
            params["unpaper_args"],
            "--pre-rotate 90",
        )
