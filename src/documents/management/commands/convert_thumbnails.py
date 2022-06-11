import logging
import multiprocessing.pool
import shutil
import tempfile
import time
from pathlib import Path

from django.core.management.base import BaseCommand
from documents.models import Document
from documents.parsers import run_convert

logger = logging.getLogger("paperless.management.convert_thumbnails")


def _do_convert(work_package):
    _, existing_thumbnail, converted_thumbnail = work_package
    try:

        logger.info(f"Converting thumbnail: {existing_thumbnail}")

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

        # Copy newly created thumbnail to thumbnail directory
        shutil.copy(converted_thumbnail, existing_thumbnail.parent)

        # Remove the PNG version
        existing_thumbnail.unlink()

        logger.info(
            "Conversion to WebP completed, "
            f"replaced {existing_thumbnail.name} with {converted_thumbnail.name}",
        )

    except Exception as e:
        logger.error(
            f"Error converting thumbnail" f" (existing file unchanged): {e}",
        )


class Command(BaseCommand):

    help = """
        Converts existing PNG thumbnails into
        WebP format.
    """.replace(
        "    ",
        "",
    )

    def handle(self, *args, **options):

        logger.info("Converting all PNG thumbnails to WebP")
        start = time.time()
        documents = Document.objects.all()

        with tempfile.TemporaryDirectory() as tempdir:

            work_packages = []

            for document in documents:
                existing_thumbnail = Path(document.thumbnail_path).resolve()

                if existing_thumbnail.suffix == ".png":

                    # Change the existing filename suffix from png to webp
                    converted_thumbnail_name = existing_thumbnail.with_suffix(
                        ".webp",
                    ).name

                    # Create the expected output filename in the tempdir
                    converted_thumbnail = (
                        Path(tempdir) / Path(converted_thumbnail_name)
                    ).resolve()

                    # Package up the necessary info
                    work_packages.append(
                        (document, existing_thumbnail, converted_thumbnail),
                    )

            if len(work_packages):
                with multiprocessing.pool.Pool(processes=4, maxtasksperchild=4) as pool:
                    pool.map(_do_convert, work_packages)

            end = time.time()
            duration = end - start

        logger.info(f"Conversion completed in {duration:.3f}s")
