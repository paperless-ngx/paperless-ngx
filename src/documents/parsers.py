from __future__ import annotations

import logging
import math
import mimetypes
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings

from documents.loggers import LoggingMixin
from documents.utils import copy_file_with_basic_stats
from documents.utils import run_subprocess
from paperless.parsers.registry import get_parser_registry

if TYPE_CHECKING:
    import datetime

logger = logging.getLogger("paperless.parsing")


def is_mime_type_supported(mime_type: str) -> bool:
    """
    Returns True if the mime type is supported, False otherwise
    """
    return get_parser_registry().get_parser_for_file(mime_type, "") is not None


def get_default_file_extension(mime_type: str) -> str:
    """
    Returns the default file extension for a mimetype, or
    an empty string if it could not be determined
    """
    parser_class = get_parser_registry().get_parser_for_file(mime_type, "")
    if parser_class is not None:
        supported = parser_class.supported_mime_types()
        if mime_type in supported:
            return supported[mime_type]

    ext = mimetypes.guess_extension(mime_type)
    return ext if ext else ""


def is_file_ext_supported(ext: str) -> bool:
    """
    Returns True if the file extension is supported, False otherwise
    TODO: Investigate why this really exists, why not use mimetype
    """
    if ext:
        return ext.lower() in get_supported_file_extensions()
    else:
        return False


def get_supported_file_extensions() -> set[str]:
    extensions = set()
    for parser_class in get_parser_registry().all_parsers():
        for mime_type, ext in parser_class.supported_mime_types().items():
            extensions.update(mimetypes.guess_all_extensions(mime_type))
            # Python's stdlib might be behind, so also add what the parser
            # says is the default extension
            # This makes image/webp supported on Python < 3.11
            extensions.add(ext)

    return extensions


def run_convert(
    input_file,
    output_file,
    *,
    density=None,
    scale=None,
    alpha=None,
    strip=False,
    trim=False,
    type=None,
    depth=None,
    auto_orient=False,
    use_cropbox=False,
    extra=None,
    logging_group=None,
) -> None:
    environment = os.environ.copy()
    if settings.CONVERT_MEMORY_LIMIT:
        # MAGICK_MEMORY_LIMIT sets the maximum amount of RAM the pixel cache can use.
        # MAGICK_MAP_LIMIT sets the maximum amount of memory-mapped I/O allowed.
        #
        # For large-format documents  ImageMagick will hit the RAM limit and
        # immediately try to "map" the remaining data. If MAGICK_MAP_LIMIT isn't
        # also set, the process may trigger an OOM kill because the default
        # system/policy map limit is often too restrictive for these massive bitmaps.
        environment["MAGICK_MEMORY_LIMIT"] = settings.CONVERT_MEMORY_LIMIT
        environment["MAGICK_MAP_LIMIT"] = settings.CONVERT_MEMORY_LIMIT
    if settings.CONVERT_TMPDIR:
        environment["MAGICK_TMPDIR"] = settings.CONVERT_TMPDIR

    args = [settings.CONVERT_BINARY]
    args += ["-density", str(density)] if density else []
    args += ["-scale", str(scale)] if scale else []
    args += ["-alpha", str(alpha)] if alpha else []
    args += ["-strip"] if strip else []
    args += ["-trim"] if trim else []
    args += ["-type", str(type)] if type else []
    args += ["-depth", str(depth)] if depth else []
    args += ["-auto-orient"] if auto_orient else []
    args += ["-define", "pdf:use-cropbox=true"] if use_cropbox else []
    args += [str(input_file), str(output_file)]

    logger.debug("Execute: " + " ".join(args), extra={"group": logging_group})

    try:
        run_subprocess(args, environment, logger)
    except subprocess.CalledProcessError as e:
        raise ParseError(f"Convert failed at {args}") from e
    except Exception as e:  # pragma: no cover
        raise ParseError("Unknown error running convert") from e


def get_default_thumbnail() -> Path:
    """
    Returns the path to a generic thumbnail
    """
    return (Path(__file__).parent / "resources" / "document.webp").resolve()


_THUMBNAIL_MAX_WIDTH = 500
_THUMBNAIL_MAX_HEIGHT = 5000
# Used only when the page geometry cannot be read
_THUMBNAIL_FALLBACK_DPI = 150
# Matches the density the thumbnail was previously rendered at before scaling
_THUMBNAIL_MAX_DPI = 300


def rasterize_pdf_page_to_png(
    in_path: Path,
    out_path: Path,
    *,
    dpi: int,
    use_cropbox: bool = True,
    logging_group=None,
) -> None:
    """
    Rasterizes page 1 of a PDF to a PNG at out_path via pdftoppm (Poppler),
    at the given DPI. pdftoppm honors the page's /Rotate on its own.
    """
    # -singlefile stops pdftoppm appending a page number to the output name,
    # and with -png it appends ".png" itself, so it is given the path without
    # its suffix to write exactly out_path
    args = [
        "pdftoppm",
        "-f",
        "1",
        "-l",
        "1",
        "-r",
        str(dpi),
        "-png",
        "-singlefile",
    ]
    if use_cropbox:
        args.append("-cropbox")
    args += [str(in_path), str(out_path.with_suffix(""))]

    logger.debug("Execute: " + " ".join(args), extra={"group": logging_group})

    try:
        run_subprocess(args, logger=logger)
    except subprocess.CalledProcessError as e:
        raise ParseError(f"pdftoppm failed at {args}") from e
    except Exception as e:  # pragma: no cover
        raise ParseError("Unknown error running pdftoppm") from e


def encode_thumbnail_webp(
    png_path: Path,
    out_path: Path,
    *,
    max_width: int = _THUMBNAIL_MAX_WIDTH,
    max_height: int = _THUMBNAIL_MAX_HEIGHT,
) -> None:
    """
    Flattens any alpha onto white and saves the image as WebP.

    max_width/max_height trim the render to the exact thumbnail size, since
    the computed DPI is rounded up and lands at or slightly above it. The
    image is never enlarged, matching the previous "-scale WxH>" behavior.
    """
    from PIL import Image

    try:
        with Image.open(png_path) as im:
            if im.mode in ("RGBA", "LA"):
                flattened = Image.new("RGB", im.size, (255, 255, 255))
                flattened.paste(im, mask=im.split()[-1])
            else:
                flattened = im.convert("RGB")

        flattened.thumbnail((max_width, max_height))
        flattened.save(out_path, format="WEBP")
    except OSError as e:
        raise ParseError(f"Unable to encode thumbnail from {png_path}") from e


def _compute_thumbnail_dpi(in_path: Path, logging_group=None) -> int:
    """
    Computes the DPI which renders the first page of the PDF at or just above
    the thumbnail size in one pass, never above the 300 DPI the thumbnail was
    previously rendered at before being scaled down.
    """
    from paperless.parsers.utils import get_pdf_first_page_size_points

    size = get_pdf_first_page_size_points(in_path)
    if size is None:
        logger.debug(
            "Could not read PDF page size, using fallback DPI",
            extra={"group": logging_group},
        )
        return _THUMBNAIL_FALLBACK_DPI

    width_pts, height_pts = size
    dpi_for_width = _THUMBNAIL_MAX_WIDTH * 72 / width_pts
    dpi_for_height = _THUMBNAIL_MAX_HEIGHT * 72 / height_pts
    # The old pipeline rendered at 300 DPI and then shrank to fit, so only
    # pages too small to reach the thumbnail size even at 300 DPI end up
    # smaller than it. Rounding up keeps the render at or above the target,
    # so the shrink-only clamp in encode_thumbnail_webp trims it to exactly
    # the thumbnail size instead of leaving it a few pixels short.
    return max(
        1,
        math.ceil(min(_THUMBNAIL_MAX_DPI, dpi_for_width, dpi_for_height)),
    )


def _render_pdf_thumbnail(
    in_path: Path,
    png_path: Path,
    out_path: Path,
    logging_group=None,
) -> None:
    dpi = _compute_thumbnail_dpi(in_path, logging_group=logging_group)
    rasterize_pdf_page_to_png(
        in_path,
        png_path,
        dpi=dpi,
        use_cropbox=True,
        logging_group=logging_group,
    )
    encode_thumbnail_webp(png_path, out_path)


def make_thumbnail_from_pdf_qpdf_fallback(
    in_path: Path,
    temp_dir: Path,
    logging_group=None,
) -> Path:
    png_path: Path = Path(temp_dir) / "page1_repaired.png"
    out_path: Path = Path(temp_dir) / "convert_qpdf.webp"
    repaired_path: Path = Path(temp_dir) / "repaired.pdf"

    logger.warning(
        "Thumbnail generation with pdftoppm failed, attempting qpdf repair and retry.",
        extra={"group": logging_group},
    )

    try:
        # qpdf rewrites in place, so work on a copy and leave the original alone.
        # qpdf exits 3 when it had to repair the file, which is the expected
        # outcome here, so warnings must not count as failure.
        try:
            shutil.copy(in_path, repaired_path)
            run_subprocess(
                [
                    "qpdf",
                    "--warning-exit-0",
                    "--replace-input",
                    str(repaired_path),
                ],
                logger=logger,
            )
        except (subprocess.CalledProcessError, OSError) as e:
            raise ParseError(f"qpdf repair failed for {in_path}") from e

        _render_pdf_thumbnail(repaired_path, png_path, out_path, logging_group)

        return out_path

    except ParseError as e:
        logger.error(f"Unable to make thumbnail after qpdf repair: {e}")
        # The caller might expect a generated thumbnail that can be moved,
        # so we need to copy it before it gets moved.
        # https://github.com/paperless-ngx/paperless-ngx/issues/3631
        default_thumbnail_path: Path = Path(temp_dir) / "document.webp"
        copy_file_with_basic_stats(get_default_thumbnail(), default_thumbnail_path)
        return default_thumbnail_path


def make_thumbnail_from_pdf(in_path: Path, temp_dir: Path, logging_group=None) -> Path:
    """
    The thumbnail of a PDF is just a 500px wide image of the first page.
    """
    png_path: Path = temp_dir / "page1.png"
    out_path: Path = temp_dir / "convert.webp"

    try:
        _render_pdf_thumbnail(in_path, png_path, out_path, logging_group)
    except ParseError as e:
        logger.error(f"Unable to make thumbnail with pdftoppm: {e}")
        out_path = make_thumbnail_from_pdf_qpdf_fallback(
            in_path,
            temp_dir,
            logging_group,
        )

    return out_path


class ParseError(Exception):
    pass


class DocumentParser(LoggingMixin):
    """
    Subclass this to make your own parser.  Have a look at
    `paperless_tesseract.parsers` for inspiration.
    """

    logging_name = "paperless.parsing"

    def __init__(self, logging_group, progress_callback=None) -> None:
        super().__init__()
        self.renew_logging_group()
        self.logging_group = logging_group
        self.settings = self.get_settings()
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        self.tempdir = Path(
            tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR),
        )

        self.archive_path = None
        self.text = None
        self.date: datetime.datetime | None = None
        self.progress_callback = progress_callback

    def progress(self, current_progress, max_progress) -> None:
        if self.progress_callback:
            self.progress_callback(current_progress, max_progress)

    def get_settings(self):  # pragma: no cover
        """
        A parser must implement this
        """
        raise NotImplementedError

    def read_file_handle_unicode_errors(self, filepath: Path) -> str:
        """
        Helper utility for reading from a file, and handling a problem with its
        unicode, falling back to ignoring the error to remove the invalid bytes
        """
        try:
            text = filepath.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            self.log.warning(f"Unicode error during text reading, continuing: {e}")
            text = filepath.read_bytes().decode("utf-8", errors="replace")
        return text

    def extract_metadata(self, document_path, mime_type):
        return []

    def get_page_count(self, document_path, mime_type) -> None:
        return None

    def parse(self, document_path, mime_type, file_name=None):
        raise NotImplementedError

    def get_archive_path(self):
        return self.archive_path

    def get_thumbnail(self, document_path, mime_type, file_name=None):
        """
        Returns the path to a file we can use as a thumbnail for this document.
        """
        raise NotImplementedError

    def get_text(self):
        return self.text

    def get_date(self) -> datetime.datetime | None:
        return self.date

    def cleanup(self) -> None:
        self.log.debug(f"Deleting directory {self.tempdir}")
        shutil.rmtree(self.tempdir)
