import logging
import os
import re
import shutil
import subprocess
import tempfile

import dateparser
from django.conf import settings
from django.utils import timezone

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
DATE_REGEX = re.compile(
    r'(\b|(?!=([_-])))([0-9]{1,2})[\.\/-]([0-9]{1,2})[\.\/-]([0-9]{4}|[0-9]{2})(\b|(?=([_-])))|' +  # NOQA: E501
    r'(\b|(?!=([_-])))([0-9]{4}|[0-9]{2})[\.\/-]([0-9]{1,2})[\.\/-]([0-9]{1,2})(\b|(?=([_-])))|' +  # NOQA: E501
    r'(\b|(?!=([_-])))([0-9]{1,2}[\. ]+[^ ]{3,9} ([0-9]{4}|[0-9]{2}))(\b|(?=([_-])))|' +  # NOQA: E501
    r'(\b|(?!=([_-])))([^\W\d_]{3,9} [0-9]{1,2}, ([0-9]{4}))(\b|(?=([_-])))|' +
    r'(\b|(?!=([_-])))([^\W\d_]{3,9} [0-9]{4})(\b|(?=([_-])))'
)


class ParseError(Exception):
    pass


class DocumentParser:
    """
    Subclass this to make your own parser.  Have a look at
    `paperless_tesseract.parsers` for inspiration.
    """

    SCRATCH = settings.SCRATCH_DIR
    DATE_ORDER = settings.DATE_ORDER
    FILENAME_DATE_ORDER = settings.FILENAME_DATE_ORDER
    OPTIPNG = settings.OPTIPNG_BINARY

    def __init__(self, path):
        self.document_path = path
        self.tempdir = tempfile.mkdtemp(prefix="paperless-", dir=self.SCRATCH)
        self.logger = logging.getLogger(__name__)
        self.logging_group = None

    def get_thumbnail(self):
        """
        Returns the path to a file we can use as a thumbnail for this document.
        """
        raise NotImplementedError()

    def optimise_thumbnail(self, in_path):

        out_path = os.path.join(self.tempdir, "optipng.png")

        args = (self.OPTIPNG, "-o5", in_path, "-out", out_path)
        if not subprocess.Popen(args).wait() == 0:
            raise ParseError("Optipng failed at {}".format(args))

        return out_path

    def get_optimised_thumbnail(self):
        return self.optimise_thumbnail(self.get_thumbnail())

    def get_text(self):
        """
        Returns the text from the document and only the text.
        """
        raise NotImplementedError()

    def get_date(self):
        """
        Returns the date of the document.
        """

        def __parser(ds, date_order):
            """
            Call dateparser.parse with a particular date ordering
            """
            return dateparser.parse(
                ds,
                settings={
                    "DATE_ORDER": date_order,
                    "PREFER_DAY_OF_MONTH": "first",
                    "RETURN_AS_TIMEZONE_AWARE":
                    True
                }
            )

        date = None
        date_string = None

        next_year = timezone.now().year + 5  # Arbitrary 5 year future limit
        title = os.path.basename(self.document_path)

        # if filename date parsing is enabled, search there first:
        if self.FILENAME_DATE_ORDER:
            self.log("info", "Checking document title for date")
            for m in re.finditer(DATE_REGEX, title):
                date_string = m.group(0)

                try:
                    date = __parser(date_string, self.FILENAME_DATE_ORDER)
                except (TypeError, ValueError):
                    # Skip all matches that do not parse to a proper date
                    continue

                if date is not None and next_year > date.year > 1900:
                    self.log(
                        "info",
                        "Detected document date {} based on string {} "
                        "from document title"
                        "".format(date.isoformat(), date_string)
                    )
                    return date

        try:
            # getting text after checking filename will save time if only
            # looking at the filename instead of the whole text
            text = self.get_text()
        except ParseError:
            return None

        # Iterate through all regex matches in text and try to parse the date
        for m in re.finditer(DATE_REGEX, text):
            date_string = m.group(0)

            try:
                date = __parser(date_string, self.DATE_ORDER)
            except (TypeError, ValueError):
                # Skip all matches that do not parse to a proper date
                continue

            if date is not None and next_year > date.year > 1900:
                break
            else:
                date = None

        if date is not None:
            self.log(
                "info",
                "Detected document date {} based on string {}".format(
                    date.isoformat(),
                    date_string
                )
            )
        else:
            self.log("info", "Unable to detect date for document")

        return date

    def log(self, level, message):
        getattr(self.logger, level)(message, extra={
            "group": self.logging_group
        })

    def cleanup(self):
        self.log("debug", "Deleting directory {}".format(self.tempdir))
        shutil.rmtree(self.tempdir)
