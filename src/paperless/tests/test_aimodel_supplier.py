from django.test import TestCase

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
    def test_default_is_both(self):
        cfg = ApplicationConfiguration.objects.first()
        self.assertEqual(cfg.video_content_mode, VideoContentModeChoices.BOTH)
