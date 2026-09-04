from django.test import TestCase
from django.test import override_settings

from paperless.config import AIConfig
from paperless.config import BarcodeConfig
from paperless.models import ApplicationConfiguration


class TestBooleanConfigPrecedence(TestCase):
    @override_settings(CONSUMER_ENABLE_BARCODES=True)
    def test_database_false_overrides_barcode_environment_setting(self) -> None:
        config = ApplicationConfiguration.objects.first()
        assert config is not None
        config.barcodes_enabled = False
        config.save()

        self.assertFalse(BarcodeConfig().barcodes_enabled)

    @override_settings(AI_ENABLED=True)
    def test_database_false_overrides_ai_environment_setting(self) -> None:
        config = ApplicationConfiguration.objects.first()
        assert config is not None
        config.ai_enabled = False
        config.save()

        self.assertFalse(AIConfig().ai_enabled)

    @override_settings(AI_ENABLED=True)
    def test_null_ai_setting_uses_environment_setting(self) -> None:
        config = ApplicationConfiguration.objects.first()
        assert config is not None
        config.ai_enabled = None
        config.save()

        self.assertTrue(AIConfig().ai_enabled)
