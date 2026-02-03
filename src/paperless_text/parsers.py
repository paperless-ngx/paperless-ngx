from pathlib import Path

from django.conf import settings
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from documents.parsers import DocumentParser


class TextDocumentParser(DocumentParser):
    """
    This parser directly parses a text document (.txt, .md, or .csv)
    """

    logging_name = "paperless.parsing.text"

    def get_thumbnail(self, document_path: Path, mime_type, file_name=None) -> Path:
        # Avoid reading entire file into memory
        max_chars = 100_000
        file_size_limit = 50 * 1024 * 1024

        if document_path.stat().st_size > file_size_limit:
            text = "[File too large to preview]"
        else:
            with Path(document_path).open("r", encoding="utf-8", errors="replace") as f:
                text = f.read(max_chars)

        img = Image.new("RGB", (500, 700), color="white")
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(
            font=settings.THUMBNAIL_FONT_NAME,
            size=20,
            layout_engine=ImageFont.Layout.BASIC,
        )
        draw.multiline_text((5, 5), text, font=font, fill="black", spacing=4)

        out_path = self.tempdir / "thumb.webp"
        img.save(out_path, format="WEBP")

        return out_path

    def parse(self, document_path, mime_type, file_name=None) -> None:
        self.text = self.read_file_handle_unicode_errors(document_path)

    def get_settings(self) -> None:
        """
        This parser does not implement additional settings yet
        """
        return None
