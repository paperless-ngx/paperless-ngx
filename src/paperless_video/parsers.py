from pathlib import Path

from documents.parsers import DocumentParser
from documents.parsers import ParseError


class VideoDocumentParser(DocumentParser):
    logging_name = "paperless.parsing.video"

    def get_settings(self):
        return None

    def parse(self, document_path: Path, mime_type, file_name=None):
        from paperless.asr import AsrClient
        from paperless.asr import AsrError
        from paperless.config import VideoConfig
        from paperless.models import AIModel
        from paperless.models import VideoContentModeChoices
        from paperless_video.content import assemble_video_content
        from paperless_video.ffmpeg_utils import extract_audio_mp3
        from paperless_video.summary import summarize_transcript

        mode = VideoConfig().video_content_mode or VideoContentModeChoices.BOTH

        asr_model = AIModel.objects.filter(model_type="asr", is_default=True).first()
        if not asr_model:
            raise ParseError("No default ASR model configured")

        audio = extract_audio_mp3(Path(document_path), Path(self.tempdir))
        try:
            transcript = AsrClient().transcribe(audio, asr_model)
        except AsrError as e:
            raise ParseError(str(e)) from e

        summary = None
        if mode in {
            VideoContentModeChoices.SUMMARY,
            VideoContentModeChoices.BOTH,
            "summary",
            "both",
        }:
            summary = summarize_transcript(transcript)

        self.text = assemble_video_content(mode, transcript, summary)

    def get_thumbnail(self, document_path, mime_type, file_name=None):
        from paperless_video.ffmpeg_utils import extract_thumbnail_webp

        return extract_thumbnail_webp(Path(document_path), Path(self.tempdir))
