import tempfile
import uuid
from pathlib import Path
from unittest import mock

from django.test import TestCase

from documents.parsers import ParseError
from documents.parsers import is_mime_type_supported
from paperless.models import AIModel
from paperless.models import ApplicationConfiguration
from paperless.models import VideoContentModeChoices
from paperless_video.parsers import VideoDocumentParser


class TestVideoDocumentParser(TestCase):
    def setUp(self):
        self.asr_model = AIModel.objects.create(
            name="default-asr",
            supplier="siliconflow",
            model_type="asr",
            base_model="FunAudioLLM/SenseVoiceSmall",
            api_domain="https://api.siliconflow.cn/v1",
            api_key="sk-test",
            is_default=True,
        )
        self.video_path = Path(tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name)
        self.video_path.write_bytes(b"\x00" * 64)
        self.addCleanup(lambda: self.video_path.unlink(missing_ok=True))

    def _parser(self) -> VideoDocumentParser:
        return VideoDocumentParser(uuid.uuid4())

    @mock.patch("paperless_video.summary.summarize_transcript")
    @mock.patch("paperless.asr.AsrClient")
    @mock.patch("paperless_video.ffmpeg_utils.extract_audio_mp3")
    def test_parse_transcript_mode(
        self,
        mock_extract,
        mock_asr_cls,
        mock_summarize,
    ):
        cfg = ApplicationConfiguration.objects.first()
        cfg.video_content_mode = VideoContentModeChoices.TRANSCRIPT
        cfg.save()

        audio_path = Path(self._parser().tempdir) / "audio.mp3"
        mock_extract.return_value = audio_path
        mock_asr_cls.return_value.transcribe.return_value = "全转写"

        parser = self._parser()
        parser.parse(self.video_path, "video/mp4")

        self.assertEqual(parser.text, "全转写")
        self.assertIsNone(parser.archive_path)
        mock_summarize.assert_not_called()
        mock_extract.assert_called_once()
        mock_asr_cls.return_value.transcribe.assert_called_once_with(
            audio_path,
            self.asr_model,
        )

    @mock.patch("paperless_video.summary.summarize_transcript")
    @mock.patch("paperless.asr.AsrClient")
    @mock.patch("paperless_video.ffmpeg_utils.extract_audio_mp3")
    def test_parse_summary_mode(
        self,
        mock_extract,
        mock_asr_cls,
        mock_summarize,
    ):
        cfg = ApplicationConfiguration.objects.first()
        cfg.video_content_mode = VideoContentModeChoices.SUMMARY
        cfg.save()

        mock_extract.return_value = Path(self._parser().tempdir) / "audio.mp3"
        mock_asr_cls.return_value.transcribe.return_value = "全转写"
        mock_summarize.return_value = "短摘要"

        parser = self._parser()
        parser.parse(self.video_path, "video/mp4")

        self.assertEqual(parser.text, "短摘要")
        mock_summarize.assert_called_once_with("全转写")

    @mock.patch("paperless_video.summary.summarize_transcript")
    @mock.patch("paperless.asr.AsrClient")
    @mock.patch("paperless_video.ffmpeg_utils.extract_audio_mp3")
    def test_parse_both_mode(
        self,
        mock_extract,
        mock_asr_cls,
        mock_summarize,
    ):
        cfg = ApplicationConfiguration.objects.first()
        cfg.video_content_mode = VideoContentModeChoices.BOTH
        cfg.save()

        mock_extract.return_value = Path(self._parser().tempdir) / "audio.mp3"
        mock_asr_cls.return_value.transcribe.return_value = "全转写"
        mock_summarize.return_value = "短摘要"

        parser = self._parser()
        parser.parse(self.video_path, "video/mp4")

        self.assertIn("【摘要】", parser.text)
        self.assertIn("短摘要", parser.text)
        self.assertIn("【转写】", parser.text)
        self.assertIn("全转写", parser.text)
        mock_summarize.assert_called_once_with("全转写")

    @mock.patch("paperless_video.ffmpeg_utils.extract_audio_mp3")
    def test_parse_raises_without_default_asr(self, mock_extract):
        self.asr_model.delete()
        mock_extract.return_value = Path(self._parser().tempdir) / "audio.mp3"

        parser = self._parser()
        with self.assertRaises(ParseError) as ctx:
            parser.parse(self.video_path, "video/mp4")
        self.assertIn("No default ASR model", str(ctx.exception))

    @mock.patch("paperless.asr.AsrClient")
    @mock.patch("paperless_video.ffmpeg_utils.extract_audio_mp3")
    def test_parse_raises_on_asr_error(self, mock_extract, mock_asr_cls):
        from paperless.asr import AsrError

        mock_extract.return_value = Path(self._parser().tempdir) / "audio.mp3"
        mock_asr_cls.return_value.transcribe.side_effect = AsrError("ASR failed")

        parser = self._parser()
        with self.assertRaises(ParseError) as ctx:
            parser.parse(self.video_path, "video/mp4")
        self.assertIn("ASR failed", str(ctx.exception))

    def test_get_settings_returns_none(self):
        parser = self._parser()
        self.assertIsNone(parser.get_settings())

    @mock.patch("paperless_video.ffmpeg_utils.extract_thumbnail_webp")
    def test_get_thumbnail(self, mock_extract_thumb):
        thumb_path = Path(self._parser().tempdir) / "thumb.webp"
        mock_extract_thumb.return_value = thumb_path

        parser = self._parser()
        result = parser.get_thumbnail(self.video_path, "video/mp4")

        self.assertEqual(result, thumb_path)
        mock_extract_thumb.assert_called_once()


class TestVideoMimeRegistration(TestCase):
    def test_video_mp4_mime_supported(self):
        is_mime_type_supported.cache_clear()
        self.assertTrue(is_mime_type_supported("video/mp4"))
