from pathlib import Path

import img2pdf
from django.conf import settings
from PIL import Image

from documents.utils import copy_basic_file_stats
from documents.utils import maybe_override_pixel_limit
from documents.utils import run_subprocess


def convert_from_tiff_to_pdf(tiff_path: Path, target_directory: Path) -> Path:
    """
    Converts a TIFF file into a PDF file.

    The PDF will be created in the given target_directory and share the name of
    the original TIFF file, as well as its stats (mtime etc.).

    Returns the path of the PDF created.
    """
    # override pixel setting if needed
    maybe_override_pixel_limit()

    with Image.open(tiff_path) as im:
        has_alpha_layer = im.mode in ("RGBA", "LA")
    if has_alpha_layer:
        # Note the save into the temp folder, so as not to trigger a new
        # consume
        scratch_image = target_directory / tiff_path.name
        run_subprocess(
            [
                settings.CONVERT_BINARY,
                "-alpha",
                "off",
                tiff_path,
                scratch_image,
            ],
        )
    else:
        # Not modifying the original, safe to use in place
        scratch_image = tiff_path

    pdf_path = (target_directory / tiff_path.name).with_suffix(".pdf")

    with scratch_image.open("rb") as img_file, pdf_path.open("wb") as pdf_file:
        pdf_file.write(img2pdf.convert(img_file))

    # Copy what file stat is possible
    copy_basic_file_stats(tiff_path, pdf_path)
    return pdf_path
