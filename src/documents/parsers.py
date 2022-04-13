import datetime
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional
from typing import Set

import magic
from django.conf import settings
from django.utils import timezone
from documents.loggers import LoggingMixin
from documents.signals import document_consumer_declaration

# This regular expression will try to find dates in the document at
# hand and will match the following formats:
# - XX.YY.ZZZZ with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
# - XX/YY/ZZZZ with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
# - XX-YY-ZZZZ with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
# - ZZZZ.XX.YY with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
# - ZZZZ/XX/YY with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
# - ZZZZ-XX-YY with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
# - XX. MONTH ZZZZ with XX being 1 or 2 and ZZZZ being 2 or 4 digits
# - MONTH ZZZZ, with ZZZZ being 4 digits
# - MONTH XX, ZZZZ with XX being 1 or 2 and ZZZZ being 4 digits
# - XX MON ZZZZ with XX being 1 or 2 and ZZZZ being 4 digits. MONTH is 3 letters

# TODO: isnt there a date parsing library for this?

DATE_REGEX = re.compile(
    r"(\b|(?!=([_-])))([0-9]{1,2})[\.\/-]([0-9]{1,2})[\.\/-]([0-9]{4}|[0-9]{2})(\b|(?=([_-])))|"  # noqa: E501
    r"(\b|(?!=([_-])))([0-9]{4}|[0-9]{2})[\.\/-]([0-9]{1,2})[\.\/-]([0-9]{1,2})(\b|(?=([_-])))|"  # noqa: E501
    r"(\b|(?!=([_-])))([0-9]{1,2}[\. ]+[^ ]{3,9} ([0-9]{4}|[0-9]{2}))(\b|(?=([_-])))|"  # noqa: E501
    r"(\b|(?!=([_-])))([^\W\d_]{3,9} [0-9]{1,2}, ([0-9]{4}))(\b|(?=([_-])))|"
    r"(\b|(?!=([_-])))([^\W\d_]{3,9} [0-9]{4})(\b|(?=([_-])))|"
    r"(\b|(?!=([_-])))(\b[0-9]{1,2}[ \.\/-][A-Z]{3}[ \.\/-][0-9]{4})(\b|(?=([_-])))",  # noqa: E501
)


logger = logging.getLogger("paperless.parsing")


def is_mime_type_supported(mime_type) -> bool:
    return get_parser_class_for_mime_type(mime_type) is not None


def get_default_file_extension(mime_type) -> str:
    for response in document_consumer_declaration.send(None):
        parser_declaration = response[1]
        supported_mime_types = parser_declaration["mime_types"]

        if mime_type in supported_mime_types:
            return supported_mime_types[mime_type]

    ext = mimetypes.guess_extension(mime_type)
    if ext:
        return ext
    else:
        return ""


def is_file_ext_supported(ext) -> bool:
    if ext:
        return ext.lower() in get_supported_file_extensions()
    else:
        return False


def get_supported_file_extensions() -> Set[str]:
    extensions = set()
    for response in document_consumer_declaration.send(None):
        parser_declaration = response[1]
        supported_mime_types = parser_declaration["mime_types"]

        for mime_type in supported_mime_types:
            extensions.update(mimetypes.guess_all_extensions(mime_type))

    return extensions


def get_parser_class_for_mime_type(mime_type):

    options = []

    # Sein letzter Befehl war: KOMMT! Und sie kamen. Alle. Sogar die Parser.

    for response in document_consumer_declaration.send(None):
        parser_declaration = response[1]
        supported_mime_types = parser_declaration["mime_types"]

        if mime_type in supported_mime_types:
            options.append(parser_declaration)

    if not options:
        return None

    # Return the parser with the highest weight.
    return sorted(options, key=lambda _: _["weight"], reverse=True)[0]["parser"]


def get_parser_class(path):
    """
    Determine the appropriate parser class based on the file
    """

    mime_type = magic.from_file(path, mime=True)

    return get_parser_class_for_mime_type(mime_type)


def run_convert(
    input_file,
    output_file,
    density=None,
    scale=None,
    alpha=None,
    strip=False,
    trim=False,
    type=None,
    depth=None,
    auto_orient=False,
    extra=None,
    logging_group=None,
) -> None:

    environment = os.environ.copy()
    if settings.CONVERT_MEMORY_LIMIT:
        environment["MAGICK_MEMORY_LIMIT"] = settings.CONVERT_MEMORY_LIMIT
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
    args += [input_file, output_file]

    logger.debug("Execute: " + " ".join(args), extra={"group": logging_group})

    if not subprocess.Popen(args, env=environment).wait() == 0:
        raise ParseError("Convert failed at {}".format(args))


def get_default_thumbnail() -> str:
    return os.path.join(os.path.dirname(__file__), "resources", "document.png")


def make_thumbnail_from_pdf_gs_fallback(in_path, temp_dir, logging_group=None) -> str:
    out_path = os.path.join(temp_dir, "convert_gs.png")

    # if convert fails, fall back to extracting
    # the first PDF page as a PNG using Ghostscript
    logger.warning(
        "Thumbnail generation with ImageMagick failed, falling back "
        "to ghostscript. Check your /etc/ImageMagick-x/policy.xml!",
        extra={"group": logging_group},
    )
    gs_out_path = os.path.join(temp_dir, "gs_out.png")
    cmd = [settings.GS_BINARY, "-q", "-sDEVICE=pngalpha", "-o", gs_out_path, in_path]
    try:
        if not subprocess.Popen(cmd).wait() == 0:
            raise ParseError("Thumbnail (gs) failed at {}".format(cmd))
        # then run convert on the output from gs
        run_convert(
            density=300,
            scale="500x5000>",
            alpha="remove",
            strip=True,
            trim=False,
            auto_orient=True,
            input_file=gs_out_path,
            output_file=out_path,
            logging_group=logging_group,
        )

        return out_path

    except ParseError:
        return get_default_thumbnail()


def make_thumbnail_from_pdf(in_path, temp_dir, logging_group=None) -> str:
    """
    The thumbnail of a PDF is just a 500px wide image of the first page.
    """
    out_path = os.path.join(temp_dir, "convert.png")

    # Run convert to get a decent thumbnail
    try:
        run_convert(
            density=300,
            scale="500x5000>",
            alpha="remove",
            strip=True,
            trim=False,
            auto_orient=True,
            input_file="{}[0]".format(in_path),
            output_file=out_path,
            logging_group=logging_group,
        )
    except ParseError:
        out_path = make_thumbnail_from_pdf_gs_fallback(in_path, temp_dir, logging_group)

    return out_path


def parse_date(filename, text) -> Optional[datetime.datetime]:
    """
    Returns the date of the document.
    """

    def __parser(ds: str, date_order: str) -> datetime.datetime:
        """
        Call dateparser.parse with a particular date ordering
        """
        import dateparser

        return dateparser.parse(
            ds,
            settings={
                "DATE_ORDER": date_order,
                "PREFER_DAY_OF_MONTH": "first",
                "RETURN_AS_TIMEZONE_AWARE": True,
                "TIMEZONE": settings.TIME_ZONE,
            },
        )

    def __filter(date: datetime.datetime) -> Optional[datetime.datetime]:
        if (
            date is not None
            and date.year > 1900
            and date <= timezone.now()
            and date.date() not in settings.IGNORE_DATES
        ):
            return date
        return None

    date = None

    # if filename date parsing is enabled, search there first:
    if settings.FILENAME_DATE_ORDER:
        logger.info("Attempting parsing from filename")
        for m in re.finditer(DATE_REGEX, filename):
            date_string = m.group(0)
            logger.info(f"Found potential date: {date_string}")

            try:
                date = __parser(date_string, settings.FILENAME_DATE_ORDER)
            except (TypeError, ValueError):
                # Skip all matches that do not parse to a proper date
                continue

            date = __filter(date)
            if date is not None:
                logger.info(f"Found date: {date}")
                return date
            else:
                logger.info("Filtered date out")

    logger.info("Attempting parsing from content")
    # Iterate through all regex matches in text and try to parse the date
    for m in re.finditer(DATE_REGEX, text):
        date_string = m.group(0)
        logger.info(f"Found potential date: {date_string}")

        try:
            date = __parser(date_string, settings.DATE_ORDER)
        except (TypeError, ValueError):
            # Skip all matches that do not parse to a proper date
            continue

        date = __filter(date)
        if date is not None:
            logger.info(f"Found date: {date}")
            return date
        else:
            logger.info("Filtered date out")

    return date


class ParseError(Exception):
    pass


class DocumentParser(LoggingMixin):
    """
    Subclass this to make your own parser.  Have a look at
    `paperless_tesseract.parsers` for inspiration.
    """

    logging_name = "paperless.parsing"

    def __init__(self, logging_group, progress_callback=None):
        super().__init__()
        self.logging_group = logging_group
        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)
        self.tempdir = tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)

        self.archive_path = None
        self.text = None
        self.date: Optional[datetime.datetime] = None
        self.progress_callback = progress_callback

    def progress(self, current_progress, max_progress):
        if self.progress_callback:
            self.progress_callback(current_progress, max_progress)

    def extract_metadata(self, document_path, mime_type):
        return []

    def parse(self, document_path, mime_type, file_name=None):
        raise NotImplementedError()

    def get_archive_path(self):
        return self.archive_path

    def get_thumbnail(self, document_path, mime_type, file_name=None):
        """
        Returns the path to a file we can use as a thumbnail for this document.
        """
        raise NotImplementedError()

    def get_optimised_thumbnail(self, document_path, mime_type, file_name=None):
        thumbnail = self.get_thumbnail(document_path, mime_type, file_name)
        if settings.OPTIMIZE_THUMBNAILS:
            out_path = os.path.join(self.tempdir, "thumb_optipng.png")

            args = (
                settings.OPTIPNG_BINARY,
                "-silent",
                "-o5",
                thumbnail,
                "-out",
                out_path,
            )

            self.log("debug", f"Execute: {' '.join(args)}")

            if not subprocess.Popen(args).wait() == 0:
                raise ParseError("Optipng failed at {}".format(args))

            return out_path
        else:
            return thumbnail

    def get_text(self):
        return self.text

    def get_date(self) -> Optional[datetime.datetime]:
        return self.date

    def cleanup(self):
        self.log("debug", f"Deleting directory {self.tempdir}")
        shutil.rmtree(self.tempdir)
