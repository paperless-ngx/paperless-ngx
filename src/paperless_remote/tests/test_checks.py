from unittest import TestCase

from django.test import override_settings

from paperless_remote import check_remote_parser_configured


class TestChecks(TestCase):
    @override_settings(REMOTE_OCR_ENGINE=None)
    def test_no_engine(self) -> None:
        msgs = check_remote_parser_configured(None)
        self.assertEqual(len(msgs), 0)

    @override_settings(REMOTE_OCR_ENGINE="azureai")
    @override_settings(REMOTE_OCR_API_KEY="somekey")
    @override_settings(REMOTE_OCR_ENDPOINT=None)
    def test_azure_no_endpoint(self) -> None:
        msgs = check_remote_parser_configured(None)
        self.assertEqual(len(msgs), 1)
        self.assertTrue(
            msgs[0].msg.startswith(
                "Azure AI remote parser requires endpoint and API key to be configured.",
            ),
        )
