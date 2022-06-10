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

        with tempfile.TemporaryDirectory() as tempdir:

            for document in documents:
                existing_thumbnail = Path(document.thumbnail_path).resolve()

                if existing_thumbnail.suffix == ".png":

                    self.stdout.write(f"Converting thumbnail: {existing_thumbnail}")

                    # Change the existing filename suffix from png to webp
                    converted_thumbnail_name = existing_thumbnail.with_suffix(
                        ".webp",
                    ).name

                    # Create the expected output filename in the tempdir
                    converted_thumbnail = (
                        Path(tempdir) / Path(converted_thumbnail_name)
                    ).resolve()

                    try:
                        # Run actual conversion
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

                        if converted_thumbnail.exists():
                            # Copy newly created thumbnail to thumbnail directory
                            shutil.copy(converted_thumbnail, existing_thumbnail.parent)

                            # Remove the PNG version
                            existing_thumbnail.unlink()

                            self.stdout.write(
                                self.style.SUCCESS(
                                    "Conversion to WebP completed",
                                ),
                            )
                        else:
                            # Highly unlike to reach here
                            self.stderr.write(
                                self.style.WARNING("Converted thumbnail doesn't exist"),
                            )

                    except Exception as e:
                        self.stderr.write(
                            self.style.ERROR(
                                f"Error converting thumbnail"
                                f" (existing file unchanged): {e}",
                            ),
                        )

            end = time.time()
            duration = end - start

        self.stdout.write(f"Conversion completed in {duration:.3f}s")
