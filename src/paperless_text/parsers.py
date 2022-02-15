import os

from PIL import ImageDraw, ImageFont, Image
from django.conf import settings

from documents.parsers import DocumentParser


class TextDocumentParser(DocumentParser):
    """
    This parser directly parses a text document (.txt, .md, or .csv)
    """

    logging_name = "paperless.parsing.text"

    def get_thumbnail(self, document_path, mime_type, file_name=None):

        def read_text():
            with open(document_path, 'r') as src:
                lines = [line.strip() for line in src.readlines()]
                text = "\n".join(lines[:50])
                return text

        img = Image.new("RGB", (500, 700), color="white")
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(
            font=settings.THUMBNAIL_FONT_NAME,
            size=20,
            layout_engine=ImageFont.LAYOUT_BASIC)
        draw.text((5, 5), read_text(), font=font, fill="black")

        out_path = os.path.join(self.tempdir, "thumb.png")
        img.save(out_path)

        return out_path

    def parse(self, document_path, mime_type, file_name=None):
        with open(document_path, 'r') as f:
            self.text = f.read()
