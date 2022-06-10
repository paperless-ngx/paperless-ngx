import logging
import shutil
import tempfile
import time
from pathlib import Path

from django.core.management.base import BaseCommand
from documents.models import Document
from documents.parsers import run_convert


logger = logging.getLogger("paperless.management.convert_thumbnails")


class Command(BaseCommand):

    help = """
        Converts existing PNG thumbnails into
        WebP format.
    """.replace(
        "    ",
        "",
    )

    def handle(self, *args, **options):

        self.stdout.write("Converting all PNG thumbnails to WebP")

        start = time.time()

        documents = Document.objects.all()

        for document in documents:
            existing_thumbnail = Path(document.thumbnail_path)

            if existing_thumbnail.suffix == "png":

                self.stdout.write(f"Converting thumbnail: {existing_thumbnail}")

                converted_thumbnail = Path(tempfile.mkstemp(suffix=".webp"))

                try:
                    run_convert(
                        density=300,
                        scale="500x5000>",
                        alpha="remove",
                        strip=True,
                        trim=False,
                        auto_orient=True,
                        input_file=f"{existing_thumbnail}[0]",
                        output_file=str(converted_thumbnail),
                    )

                    self.stdout.write("Replacing existing thumbnail")

                    if converted_thumbnail.exists():
                        shutil.copy(converted_thumbnail, existing_thumbnail)

                    self.stdout.write(
                        self.style.SUCCESS("Conversion to WebP completed"),
                    )

                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Error converting thumbnail (existing will be kept): {e}",
                        ),
                    )
                finally:
                    if converted_thumbnail.exists():
                        converted_thumbnail.unlink()

        end = time.time()
        duration = end - start

        self.stdout.write(f"Conversion completed in {duration:.3f}s")
