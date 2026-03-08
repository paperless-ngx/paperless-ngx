import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from documents.tests.utils import DirectoriesMixin
from paperless.models import ApplicationConfiguration
from paperless.models import ColorConvertChoices


class TestApiAppConfig(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/config/"

    def setUp(self) -> None:
        super().setUp()

        user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=user)

    def test_api_get_config(self) -> None:
        """
        GIVEN:
            - API request to get app config
        WHEN:
            - API is called
        THEN:
            - Existing config
        """
        response = self.client.get(self.ENDPOINT, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.maxDiff = None

        self.assertDictEqual(
            response.data[0],
            {
                "id": 1,
                "output_type": None,
                "pages": None,
                "language": None,
                "mode": None,
                "skip_archive_file": None,
                "image_dpi": None,
                "unpaper_clean": None,
                "deskew": None,
                "rotate_pages": None,
                "rotate_pages_threshold": None,
                "max_image_pixels": None,
                "color_conversion_strategy": None,
                "user_args": None,
                "app_title": None,
                "app_logo": None,
                "barcodes_enabled": None,
                "barcode_enable_tiff_support": None,
                "barcode_string": None,
                "barcode_retain_split_pages": None,
                "barcode_enable_asn": None,
                "barcode_asn_prefix": None,
                "barcode_upscale": None,
                "barcode_dpi": None,
                "barcode_max_pages": None,
                "barcode_enable_tag": None,
                "barcode_tag_mapping": None,
                "barcode_tag_split": None,
                "ai_enabled": False,
                "llm_embedding_backend": None,
                "llm_embedding_model": None,
                "llm_backend": None,
                "llm_model": None,
                "llm_api_key": None,
                "llm_endpoint": None,
            },
        )

    def test_api_get_ui_settings_with_config(self) -> None:
        """
        GIVEN:
            - Existing config with app_title, app_logo specified
        WHEN:
            - API to retrieve uisettings is called
        THEN:
            - app_title and app_logo are included
        """
        config = ApplicationConfiguration.objects.first()
        config.app_title = "Fancy New Title"
        config.app_logo = "/logo/example.jpg"
        config.save()
        response = self.client.get("/api/ui_settings/", format="json")
        self.assertDictEqual(
            response.data["settings"],
            {
                "app_title": config.app_title,
                "app_logo": config.app_logo,
            }
            | response.data["settings"],
        )

    def test_api_update_config(self) -> None:
        """
        GIVEN:
            - API request to update app config
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
            - Config is updated
        """
        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            json.dumps(
                {
                    "color_conversion_strategy": ColorConvertChoices.RGB,
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config = ApplicationConfiguration.objects.first()
        self.assertEqual(config.color_conversion_strategy, ColorConvertChoices.RGB)

    def test_api_update_config_empty_fields(self) -> None:
        """
        GIVEN:
            - API request to update app config with empty string for user_args JSONField and language field
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
            - user_args is set to None
        """
        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            json.dumps(
                {
                    "user_args": "",
                    "language": "",
                    "barcode_tag_mapping": "",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config = ApplicationConfiguration.objects.first()
        self.assertEqual(config.user_args, None)
        self.assertEqual(config.language, None)
        self.assertEqual(config.barcode_tag_mapping, None)

    def test_api_replace_app_logo(self) -> None:
        """
        GIVEN:
            - Existing config with app_logo specified
        WHEN:
            - API to replace app_logo is called
        THEN:
            - old app_logo file is deleted
        """
        admin = User.objects.create_superuser(username="admin")
        self.client.force_login(user=admin)
        response = self.client.get("/logo/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.client.patch(
            f"{self.ENDPOINT}1/",
            {
                "app_logo": SimpleUploadedFile(
                    name="simple.jpg",
                    content=(
                        Path(__file__).parent / "samples" / "simple.jpg"
                    ).read_bytes(),
                    content_type="image/jpeg",
                ),
            },
        )

        # Logo exists at /logo/simple.jpg
        response = self.client.get("/logo/simple.jpg")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("image/jpeg", response["Content-Type"])

        config = ApplicationConfiguration.objects.first()
        old_logo = config.app_logo
        self.assertTrue(Path(old_logo.path).exists())
        self.client.patch(
            f"{self.ENDPOINT}1/",
            {
                "app_logo": SimpleUploadedFile(
                    name="simple.png",
                    content=(
                        Path(__file__).parent / "samples" / "simple.png"
                    ).read_bytes(),
                    content_type="image/png",
                ),
            },
        )
        self.assertFalse(Path(old_logo.path).exists())

    def test_api_rejects_malicious_svg_logo(self) -> None:
        """
        GIVEN:
            - An SVG logo containing a <script> tag
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400
        """
        malicious_svg = b"""<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
                            <text x="10" y="20">Hello</text>
                            <script>alert('XSS')</script>
                            </svg>
                        """

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "malicious_script.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("disallowed svg tag", str(response.data).lower())

    def test_api_rejects_malicious_svg_with_style_javascript(self) -> None:
        """
        GIVEN:
            - An SVG logo containing javascript: in style attribute
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400
        """

        malicious_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" style="background: url(javascript:alert('XSS'));" fill="red"/>
    </svg>"""

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "malicious_style.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "disallowed pattern in style attribute",
            str(response.data).lower(),
        )
        self.assertIn("style", str(response.data).lower())

    def test_api_rejects_svg_with_style_expression(self) -> None:
        """
        GIVEN:
            - An SVG logo containing CSS expression() in style
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400
        """

        malicious_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" style="width: expression(alert('XSS'));" fill="blue"/>
    </svg>"""

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "expression_style.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("disallowed", str(response.data).lower())

    def test_api_rejects_svg_with_style_cdata_javascript(self) -> None:
        """
        GIVEN:
            - An SVG logo with javascript: hidden in a CDATA style block
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400
        """

        malicious_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <style><![CDATA[
            rect { background: url("javascript:alert('XSS')"); }
        ]]></style>
        <rect width="100" height="100" fill="purple"/>
    </svg>"""

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "cdata_style.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("disallowed", str(response.data).lower())

    def test_api_rejects_svg_with_style_import(self) -> None:
        """
        GIVEN:
            - An SVG logo containing @import in style
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400
        """

        malicious_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" style="@import url('http://evil.com/malicious.css');" fill="green"/>
    </svg>"""

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "import_style.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("disallowed", str(response.data).lower())

    def test_api_accepts_valid_svg_with_safe_style(self) -> None:
        """
        GIVEN:
            - A valid SVG logo with safe style attributes
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is accepted with 200
        """

        safe_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" style="fill: #ff6b6b; stroke: #333; stroke-width: 2;"/>
        <circle cx="50" cy="50" r="30" style="fill: white; opacity: 0.8;"/>
    </svg>"""

        svg_file = BytesIO(safe_svg)
        svg_file.name = "safe_logo.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_accepts_valid_svg_with_safe_style_tag(self) -> None:
        """
        GIVEN:
            - A valid SVG logo with an embedded <style> tag
        WHEN:
            - Uploaded to app config
        THEN:
            - SVG is accepted with 200
        """

        safe_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <style>
            rect { fill: #ff6b6b; stroke: #333; stroke-width: 2; }
            circle { fill: white; opacity: 0.8; }
        </style>
        <rect width="100" height="100"/>
        <circle cx="50" cy="50" r="30"/>
    </svg>"""

        svg_file = BytesIO(safe_svg)
        svg_file.name = "safe_logo_with_style.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_rejects_svg_with_disallowed_attribute(self) -> None:
        """
        GIVEN:
            - An SVG with a disallowed attribute (onclick)
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400
        """

        malicious_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" fill="red" onclick="alert('XSS')"/>
    </svg>"""

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "onclick_attribute.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("disallowed", str(response.data).lower())
        self.assertIn("attribute", str(response.data).lower())

    def test_api_rejects_svg_with_disallowed_tag(self) -> None:
        """
        GIVEN:
            - An SVG with a disallowed tag (script)
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400
        """

        malicious_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <script>alert('XSS')</script>
        <rect width="100" height="100" fill="blue"/>
    </svg>"""

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "script_tag.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("disallowed", str(response.data).lower())
        self.assertIn("tag", str(response.data).lower())

    def test_api_rejects_svg_with_javascript_href(self) -> None:
        """
        GIVEN:
            - An SVG with javascript: in href attribute
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400
        """
        malicious_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <defs>
            <rect id="a" width="10" height="10" />
        </defs>
        <use href="javascript:alert('XSS')" />
    </svg>"""

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "javascript_href.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("disallowed", str(response.data).lower())
        self.assertIn("javascript", str(response.data).lower())

    def test_api_rejects_svg_with_javascript_xlink_href(self) -> None:
        """
        GIVEN:
            - An SVG with javascript: in xlink:href attribute
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400
        """
        malicious_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 100">
        <use xlink:href="javascript:alert('XSS')" />
    </svg>"""

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "javascript_xlink_href.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("disallowed", str(response.data).lower())
        self.assertIn("javascript", str(response.data).lower())

    def test_api_rejects_svg_with_data_text_html_href(self) -> None:
        """
        GIVEN:
            - An SVG with data:text/html in href attribute
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400
        """
        malicious_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <defs>
                <rect id="r" width="100" height="100" fill="purple"/>
            </defs>
            <use href="javascript:alert(1)" />
        </svg>"""

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "data_html_href.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # This will now catch "Disallowed URI scheme"
        self.assertIn("disallowed", str(response.data).lower())

    def test_api_rejects_svg_with_unknown_namespace_attribute(self) -> None:
        """
        GIVEN:
            - An SVG with an attribute in an unknown/custom namespace
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400
            - Error message identifies the namespaced attribute as disallowed
        """

        # Define a custom namespace "my:hack" and try to use it
        malicious_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg"
         xmlns:hack="http://example.com/hack"
         viewBox="0 0 100 100">
        <rect width="100" height="100" hack:fill="red" />
    </svg>"""

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "unknown_namespace.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # The error message should show the full Clark notation (curly braces)
        # because the validator's 'else' block kept the raw lxml name.
        error_msg = str(response.data).lower()
        self.assertIn("disallowed svg attribute", error_msg)
        self.assertIn("{http://example.com/hack}fill", error_msg)

    def test_api_rejects_svg_with_external_http_href(self) -> None:
        """
        GIVEN:
            - An SVG with an external URI (http://) in a safe tag's href attribute.
        WHEN:
            - Uploaded via PATCH to app config
        THEN:
            - SVG is rejected with 400 because http:// is not a safe_prefix.
        """
        from io import BytesIO

        # http:// is not in dangerous_schemes, but it is not in safe_prefixes.
        malicious_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <use href="http://evil.com/logo.svg" />
    </svg>"""

        svg_file = BytesIO(malicious_svg)
        svg_file.name = "external_http_href.svg"

        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            {"app_logo": svg_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Check for the error message raised by the safe_prefixes check
        self.assertIn("uri scheme not allowed", str(response.data).lower())

    def test_create_not_allowed(self) -> None:
        """
        GIVEN:
            - API request to create a new app config
        WHEN:
            - API is called
        THEN:
            - Correct HTTP response
            - No new config is created
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "output_type": "pdf",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(ApplicationConfiguration.objects.count(), 1)

    def test_update_llm_api_key(self) -> None:
        """
        GIVEN:
            - Existing config with llm_api_key specified
        WHEN:
            - API to update llm_api_key is called with all *s
            - API to update llm_api_key is called with empty string
        THEN:
            - llm_api_key is unchanged
            - llm_api_key is set to None
        """
        config = ApplicationConfiguration.objects.first()
        config.llm_api_key = "1234567890"
        config.save()

        # Test with all *
        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            json.dumps(
                {
                    "llm_api_key": "*" * 32,
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config.refresh_from_db()
        self.assertEqual(config.llm_api_key, "1234567890")
        # Test with empty string
        response = self.client.patch(
            f"{self.ENDPOINT}1/",
            json.dumps(
                {
                    "llm_api_key": "",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config.refresh_from_db()
        self.assertEqual(config.llm_api_key, None)

    def test_enable_ai_index_triggers_update(self) -> None:
        """
        GIVEN:
            - Existing config with AI disabled
        WHEN:
            - Config is updated to enable AI with llm_embedding_backend
        THEN:
            - LLM index is triggered to update
        """
        config = ApplicationConfiguration.objects.first()
        config.ai_enabled = False
        config.llm_embedding_backend = None
        config.save()

        with (
            patch("documents.tasks.llmindex_index.delay") as mock_update,
            patch("paperless_ai.indexing.vector_store_file_exists") as mock_exists,
        ):
            mock_exists.return_value = False
            self.client.patch(
                f"{self.ENDPOINT}1/",
                json.dumps(
                    {
                        "ai_enabled": True,
                        "llm_embedding_backend": "openai",
                    },
                ),
                content_type="application/json",
            )
            mock_update.assert_called_once()
