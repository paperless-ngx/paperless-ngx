from django.test import TestCase
from django.test import override_settings

from paperless.config import AIConfig
from paperless.config import BarcodeConfig
from paperless.models import ApplicationConfiguration


class TestBooleanConfigPrecedence(TestCase):
    @override_settings(CONSUMER_ENABLE_BARCODES=True)
    def test_database_false_overrides_barcode_environment_setting(self) -> None:
        config, _ = ApplicationConfiguration.objects.get_or_create()
        config.barcodes_enabled = False
        config.save()

        self.assertFalse(BarcodeConfig().barcodes_enabled)

    @override_settings(AI_ENABLED=True)
    def test_database_false_overrides_ai_environment_setting(self) -> None:
        config, _ = ApplicationConfiguration.objects.get_or_create()
        config.ai_enabled = False
        config.save()

        self.assertFalse(AIConfig().ai_enabled)

    @override_settings(AI_ENABLED=True)
    def test_null_ai_setting_uses_environment_setting(self) -> None:
        config, _ = ApplicationConfiguration.objects.get_or_create()
        config.ai_enabled = None
        config.save()

        self.assertTrue(AIConfig().ai_enabled)


class TestAIConfigPrecedence(TestCase):
    @override_settings(LLM_EMBEDDING_API_KEY="environment-embedding-key")
    def test_database_embedding_api_key_overrides_environment_setting(self) -> None:
        config, _ = ApplicationConfiguration.objects.get_or_create()
        config.llm_embedding_api_key = "database-embedding-key"
        config.save()

        self.assertEqual(
            AIConfig().llm_embedding_api_key,
            "database-embedding-key",
        )

    @override_settings(LLM_EMBEDDING_API_KEY="environment-embedding-key")
    def test_null_embedding_api_key_uses_environment_setting(self) -> None:
        config, _ = ApplicationConfiguration.objects.get_or_create()
        config.llm_embedding_api_key = None
        config.save()

        self.assertEqual(
            AIConfig().llm_embedding_api_key,
            "environment-embedding-key",
        )
