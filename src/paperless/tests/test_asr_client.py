import tempfile
from pathlib import Path
from unittest import mock

import httpx
from django.test import TestCase

from paperless.asr import MAX_ASR_AUDIO_BYTES
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

    def test_transcribe_wraps_http_status_error(self):
        client = AsrClient()
        audio = Path(self._temp_audio())
        request = httpx.Request(
            "POST",
            "https://api.siliconflow.cn/v1/audio/transcriptions",
        )
        response = httpx.Response(502, text="upstream boom", request=request)
        mock_response = mock.Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "bad gateway",
            request=request,
            response=response,
        )

        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.return_value = mock_response
            with self.assertRaises(AsrError) as ctx:
                client.transcribe(audio, self.model)

        self.assertIn("502", str(ctx.exception))
        self.assertIn("upstream boom", str(ctx.exception))

    def test_transcribe_wraps_transport_error(self):
        client = AsrClient()
        audio = Path(self._temp_audio())

        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.side_effect = httpx.ConnectError("connection refused")
            with self.assertRaises(AsrError) as ctx:
                client.transcribe(audio, self.model)

        self.assertIn("connection refused", str(ctx.exception))

    def test_transcribe_rejects_audio_over_50mb(self):
        client = AsrClient()
        audio = Path(self._temp_audio())
        oversized = mock.Mock(st_size=MAX_ASR_AUDIO_BYTES + 1)

        with mock.patch.object(Path, "stat", return_value=oversized):
            with self.assertRaises(AsrError) as ctx:
                client.transcribe(audio, self.model)

        self.assertIn("50MB", str(ctx.exception))
