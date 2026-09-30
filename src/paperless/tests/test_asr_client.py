import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase

from paperless.asr import AsrClient
from paperless.asr import AsrError
from paperless.models import AIModel


class TestAsrClient(TestCase):
    def setUp(self):
        self.model = AIModel(
            name="asr",
            supplier="siliconflow",
            model_type="asr",
            base_model="FunAudioLLM/SenseVoiceSmall",
            api_domain="https://api.siliconflow.cn/v1",
            api_key="sk-test",
        )

    def _temp_audio(self) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(b"\x00" * 64)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    def test_transcribe_posts_multipart_and_returns_text(self):
        client = AsrClient()
        audio = Path(self._temp_audio())

        mock_response = mock.Mock()
        mock_response.raise_for_status = mock.Mock()
        mock_response.json.return_value = {"text": "你好世界"}

        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.return_value = mock_response
            text = client.transcribe(audio, self.model)

        self.assertEqual(text, "你好世界")
        args, kwargs = instance.post.call_args
        self.assertTrue(args[0].endswith("/audio/transcriptions"))
        self.assertIn("Authorization", kwargs["headers"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-test")
        self.assertIn("files", kwargs)

    def test_transcribe_raises_on_empty_text(self):
        client = AsrClient()
        audio = Path(self._temp_audio())

        mock_response = mock.Mock()
        mock_response.raise_for_status = mock.Mock()
        mock_response.json.return_value = {"text": ""}

        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.return_value = mock_response
            with self.assertRaises(AsrError):
                client.transcribe(audio, self.model)
