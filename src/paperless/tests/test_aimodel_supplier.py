from django.test import TestCase
from django.test import override_settings

from paperless.models import AIModel
from paperless.models import ApplicationConfiguration
from paperless.models import VideoContentModeChoices


class TestAIModelSupplierFreeText(TestCase):
    def test_allows_siliconflow_supplier(self):
        m = AIModel.objects.create(
            name="sf-asr",
            supplier="siliconflow",
            model_type="asr",
            base_model="FunAudioLLM/SenseVoiceSmall",
            api_domain="https://api.siliconflow.cn/v1",
            api_key="test-key",
            is_default=True,
        )
        self.assertEqual(m.supplier, "siliconflow")


class TestVideoContentMode(TestCase):
    def test_default_is_unset(self):
        cfg = ApplicationConfiguration.objects.first()
        self.assertIsNone(cfg.video_content_mode)

    @override_settings(VIDEO_CONTENT_MODE=VideoContentModeChoices.TRANSCRIPT)
    def test_video_config_uses_settings_when_db_unset(self):
        from paperless.config import VideoConfig

        cfg = ApplicationConfiguration.objects.first()
        cfg.video_content_mode = None
        cfg.save()
        self.assertEqual(
            VideoConfig().video_content_mode,
            VideoContentModeChoices.TRANSCRIPT,
        )
