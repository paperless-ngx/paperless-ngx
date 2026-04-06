from __future__ import annotations

import importlib.resources
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Final
from typing import NoReturn
from typing import Self

from django.conf import settings
from PIL import Image

from documents.parsers import ParseError
from documents.parsers import make_thumbnail_from_pdf
from documents.utils import copy_file_with_basic_stats
from documents.utils import maybe_override_pixel_limit
from documents.utils import run_subprocess
from paperless.config import OcrConfig
from paperless.models import CleanChoices
from paperless.models import ModeChoices
from paperless.models import OutputTypeChoices
from paperless.parsers.utils import PDF_TEXT_MIN_LENGTH
from paperless.parsers.utils import extract_pdf_text
from paperless.parsers.utils import is_tagged_pdf
from paperless.parsers.utils import read_file_handle_unicode_errors
from paperless.version import __full_version_str__

if TYPE_CHECKING:
    import datetime
    from types import TracebackType

    from paperless.parsers import MetadataEntry
    from paperless.parsers import ParserContext

logger = logging.getLogger("paperless.parsing.tesseract")

_SRGB_ICC_DATA: Final[bytes] = (
    importlib.resources.files("ocrmypdf.data").joinpath("sRGB.icc").read_bytes()
)

_SUPPORTED_MIME_TYPES: Final[dict[str, str]] = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/tiff": ".tif",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
    "image/heic": ".heic",
}


class NoTextFoundException(Exception):
    pass


class RtlLanguageException(Exception):
    pass


class RasterisedDocumentParser:
    """
    This parser uses Tesseract to try and get some text out of a rasterised
    image, whether it's a PDF, or other graphical format (JPEG, TIFF, etc.)
    """

    name: str = "Paperless-ngx Tesseract OCR Parser"
    version: str = __full_version_str__
    author: str = "Paperless-ngx Contributors"
    url: str = "https://github.com/paperless-ngx/paperless-ngx"

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def supported_mime_types(cls) -> dict[str, str]:
        return _SUPPORTED_MIME_TYPES

    @classmethod
    def score(
        cls,
        mime_type: str,
        filename: str,
        path: Path | None = None,
    ) -> int | None:
        if mime_type in _SUPPORTED_MIME_TYPES:
            return 10
        return None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def can_produce_archive(self) -> bool:
        return True

    @property
    def requires_pdf_rendition(self) -> bool:
        return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, logging_group: object | None = None) -> None:
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        self.tempdir = Path(
            tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR),
        )
        self.settings = OcrConfig()
        self.archive_path: Path | None = None
        self.text: str | None = None
        self.date: datetime.datetime | None = None
        self.log = logger

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        logger.debug("Cleaning up temporary directory %s", self.tempdir)
        shutil.rmtree(self.tempdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Core parsing interface
    # ------------------------------------------------------------------

    def configure(self, context: ParserContext) -> None:
        pass

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def get_text(self) -> str | None:
        return self.text

    def get_date(self) -> datetime.datetime | None:
        return self.date

    def get_archive_path(self) -> Path | None:
        return self.archive_path

    # ------------------------------------------------------------------
    # Thumbnail, page count, and metadata
    # ------------------------------------------------------------------

    def get_thumbnail(self, document_path: Path, mime_type: str) -> Path:
        return make_thumbnail_from_pdf(
            self.archive_path or Path(document_path),
            self.tempdir,
        )

    def get_page_count(self, document_path: Path, mime_type: str) -> int | None:
        if mime_type == "application/pdf":
            from paperless.parsers.utils import get_page_count_for_pdf

            return get_page_count_for_pdf(Path(document_path), log=self.log)
        return None

    def extract_metadata(
        self,
        document_path: Path,
        mime_type: str,
    ) -> list[MetadataEntry]:
        if mime_type != "application/pdf":
            return []

        from paperless.parsers.utils import extract_pdf_metadata

        return extract_pdf_metadata(Path(document_path), log=self.log)

    def is_image(self, mime_type: str) -> bool:
        return mime_type in [
            "image/png",
            "image/jpeg",
            "image/tiff",
            "image/bmp",
            "image/gif",
            "image/webp",
            "image/heic",
        ]

    def has_alpha(self, image: Path) -> bool:
        with Image.open(image) as im:
            return im.mode in ("RGBA", "LA")

    def remove_alpha(self, image_path: Path) -> Path:
        no_alpha_image = Path(self.tempdir) / "image-no-alpha"
        run_subprocess(
            [
                settings.CONVERT_BINARY,
                "-alpha",
                "off",
                str(image_path),
                str(no_alpha_image),
            ],
            logger=self.log,
        )
        return no_alpha_image

    def get_dpi(self, image: Path) -> int | None:
        try:
            with Image.open(image) as im:
                x, _ = im.info["dpi"]
                return round(x)
        except Exception as e:
            self.log.warning(f"Error while getting DPI from image {image}: {e}")
            return None

    def calculate_a4_dpi(self, image: Path) -> int | None:
        try:
            with Image.open(image) as im:
                width, _ = im.size
                # divide image width by A4 width (210mm) in inches.
                dpi = int(width / (21 / 2.54))
                self.log.debug(f"Estimated DPI {dpi} based on image width {width}")
                return dpi

        except Exception as e:
            self.log.warning(f"Error while calculating DPI for image {image}: {e}")
            return None

    def extract_text(
        self,
        sidecar_file: Path | None,
        pdf_file: Path,
    ) -> str | None:
        text: str | None = None
        # When re-doing OCR, the sidecar contains ONLY the new text, not
        # the whole text, so do not utilize it in that case
        if (
            sidecar_file is not None
            and sidecar_file.is_file()
            and self.settings.mode != ModeChoices.REDO
        ):
            text = read_file_handle_unicode_errors(sidecar_file)

            if "[OCR skipped on page" not in text:
                # This happens when there's already text in the input file.
                # The sidecar file will only contain text for OCR'ed pages.
                self.log.debug("Using text from sidecar file")
                return post_process_text(text)
            else:
                self.log.debug("Incomplete sidecar file: discarding.")

        # no success with the sidecar file, try PDF

        if not Path(pdf_file).is_file():
            return None

        return post_process_text(extract_pdf_text(Path(pdf_file), log=self.log))

    def construct_ocrmypdf_parameters(
        self,
        input_file: Path,
        mime_type: str,
        output_file: Path,
        sidecar_file: Path,
        *,
        safe_fallback: bool = False,
        skip_text: bool = False,
    ) -> dict[str, Any]:
        ocrmypdf_args: dict[str, Any] = {
            "input_file_or_options": input_file,
            "output_file": output_file,
            # need to use threads, since this will be run in daemonized
            # processes via the task library.
            "use_threads": True,
            "jobs": settings.THREADS_PER_WORKER,
            "language": self.settings.language,
            "output_type": self.settings.output_type,
            "progress_bar": False,
        }

        if "pdfa" in ocrmypdf_args["output_type"]:
            ocrmypdf_args["color_conversion_strategy"] = (
                self.settings.color_conversion_strategy
            )

        if safe_fallback or self.settings.mode == ModeChoices.FORCE:
            ocrmypdf_args["force_ocr"] = True
        elif self.settings.mode == ModeChoices.REDO:
            ocrmypdf_args["redo_ocr"] = True
        elif skip_text or self.settings.mode == ModeChoices.OFF:
            ocrmypdf_args["skip_text"] = True
        elif self.settings.mode == ModeChoices.AUTO:
            pass  # no extra flag: normal OCR (text not found case)
        else:  # pragma: no cover
            raise ParseError(f"Invalid ocr mode: {self.settings.mode}")

        if self.settings.clean == CleanChoices.CLEAN:
            ocrmypdf_args["clean"] = True
        elif self.settings.clean == CleanChoices.FINAL:
            if self.settings.mode == ModeChoices.REDO:
                ocrmypdf_args["clean"] = True
            else:
                # --clean-final is not compatible with --redo-ocr
                ocrmypdf_args["clean_final"] = True

        if self.settings.deskew and self.settings.mode != ModeChoices.REDO:
            # --deskew is not compatible with --redo-ocr
            ocrmypdf_args["deskew"] = True

        if self.settings.rotate:
            ocrmypdf_args["rotate_pages"] = True
            ocrmypdf_args["rotate_pages_threshold"] = self.settings.rotate_threshold

        if self.settings.pages is not None and self.settings.pages > 0:
            ocrmypdf_args["pages"] = f"1-{self.settings.pages}"
        else:
            # sidecar is incompatible with pages
            ocrmypdf_args["sidecar"] = sidecar_file

        if self.is_image(mime_type):
            # This may be required, depending on the known information
            maybe_override_pixel_limit()

            dpi = self.get_dpi(input_file)
            a4_dpi = self.calculate_a4_dpi(input_file)

            if self.has_alpha(input_file):
                self.log.info(
                    f"Removing alpha layer from {input_file} "
                    "for compatibility with img2pdf",
                )
                # Replace the input file with the non-alpha
                ocrmypdf_args["input_file_or_options"] = self.remove_alpha(input_file)

            if dpi:
                self.log.debug(f"Detected DPI for image {input_file}: {dpi}")
                ocrmypdf_args["image_dpi"] = dpi
            elif self.settings.image_dpi is not None:
                ocrmypdf_args["image_dpi"] = self.settings.image_dpi
            elif a4_dpi:
                ocrmypdf_args["image_dpi"] = a4_dpi
            else:
                raise ParseError(
                    f"Cannot produce archive PDF for image {input_file}, "
                    f"no DPI information is present in this image and "
                    f"OCR_IMAGE_DPI is not set.",
                )
            if ocrmypdf_args["image_dpi"] < 70:  # pragma: no cover
                self.log.warning(
                    f"Image DPI of {ocrmypdf_args['image_dpi']} is low, OCR may fail",
                )

        if self.settings.user_args is not None:
            try:
                ocrmypdf_args = {**ocrmypdf_args, **self.settings.user_args}
            except Exception as e:
                self.log.warning(
                    f"There is an issue with PAPERLESS_OCR_USER_ARGS, so "
                    f"they will not be used. Error: {e}",
                )

        if (
            self.settings.max_image_pixel is not None
            and self.settings.max_image_pixel >= 0
        ):
            # Convert pixels to mega-pixels and provide to ocrmypdf
            max_pixels_mpixels = self.settings.max_image_pixel / 1_000_000.0
            msg = (
                "OCR pixel limit is disabled!"
                if max_pixels_mpixels == 0
                else f"Calculated {max_pixels_mpixels} megapixels for OCR"
            )
            self.log.debug(msg)
            ocrmypdf_args["max_image_mpixels"] = max_pixels_mpixels

        return ocrmypdf_args

    def _convert_image_to_pdfa(self, document_path: Path) -> Path:
        """Convert an image to a PDF/A-2b file without invoking the OCR engine.

        Uses img2pdf for the initial image->PDF wrapping, then pikepdf to stamp
        PDF/A-2b conformance metadata.

        No Tesseract and no Ghostscript are invoked.
        """
        import img2pdf
        import pikepdf

        plain_pdf_path = Path(self.tempdir) / "image_plain.pdf"
        try:
            convert_kwargs: dict = {}
            if self.settings.image_dpi is not None:
                convert_kwargs["layout_fun"] = img2pdf.get_fixed_dpi_layout_fun(
                    (self.settings.image_dpi, self.settings.image_dpi),
                )
            plain_pdf_path.write_bytes(
                img2pdf.convert(str(document_path), **convert_kwargs),
            )
        except Exception as e:
            raise ParseError(
                f"img2pdf conversion failed for {document_path}: {e!s}",
            ) from e

        pdfa_path = Path(self.tempdir) / "archive.pdf"
        try:
            with pikepdf.open(plain_pdf_path) as pdf:
                cs = pdf.make_stream(_SRGB_ICC_DATA)
                cs["/N"] = 3
                output_intent = pikepdf.Dictionary(
                    Type=pikepdf.Name("/OutputIntent"),
                    S=pikepdf.Name("/GTS_PDFA1"),
                    OutputConditionIdentifier=pikepdf.String("sRGB"),
                    DestOutputProfile=cs,
                )
                pdf.Root["/OutputIntents"] = pdf.make_indirect(
                    pikepdf.Array([output_intent]),
                )
                meta = pdf.open_metadata(set_pikepdf_as_editor=False)
                meta["pdfaid:part"] = "2"
                meta["pdfaid:conformance"] = "B"
                pdf.save(pdfa_path)
        except Exception as e:
            self.log.warning(
                f"PDF/A metadata stamping failed ({e!s}); falling back to plain PDF.",
            )
            pdfa_path.write_bytes(plain_pdf_path.read_bytes())

        return pdfa_path

    def _convert_pdf_to_pdfa(
        self,
        input_path: Path,
        output_path: Path,
    ) -> None:
        """Convert a PDF to PDF/A using Ghostscript directly, without OCR.

        Respects the user's output_type, color_conversion_strategy, and
        continue_on_soft_render_error settings.
        """
        from ocrmypdf._exec.ghostscript import generate_pdfa
        from ocrmypdf.pdfa import generate_pdfa_ps

        output_type = self.settings.output_type
        if output_type == OutputTypeChoices.PDF:
            # No PDF/A requested — just copy the original
            copy_file_with_basic_stats(input_path, output_path)
            return

        # Map output_type to pdfa_part: pdfa→2, pdfa-1→1, pdfa-2→2, pdfa-3→3
        pdfa_part = "2" if output_type == "pdfa" else output_type.split("-")[-1]

        pdfmark = Path(self.tempdir) / "pdfa.ps"
        generate_pdfa_ps(pdfmark)

        color_strategy = self.settings.color_conversion_strategy or "RGB"

        self.log.debug(
            "Converting PDF to PDF/A-%s via Ghostscript (no OCR): %s",
            pdfa_part,
            input_path,
        )

        generate_pdfa(
            pdf_pages=[pdfmark, input_path],
            output_file=output_path,
            compression="auto",
            color_conversion_strategy=color_strategy,
            pdfa_part=pdfa_part,
        )

    def _handle_subprocess_output_error(self, e: Exception) -> NoReturn:
        """Log context for Ghostscript failures and raise ParseError.

        Called from the SubprocessOutputError handlers in parse() to avoid
        duplicating the Ghostscript hint and re-raise logic.
        """
        if "Ghostscript PDF/A rendering" in str(e):
            self.log.warning(
                "Ghostscript PDF/A rendering failed, consider setting "
                "PAPERLESS_OCR_USER_ARGS: "
                "'{\"continue_on_soft_render_error\": true}'",
            )
        raise ParseError(
            f"SubprocessOutputError: {e!s}. See logs for more information.",
        ) from e

    def parse(
        self,
        document_path: Path,
        mime_type: str,
        *,
        produce_archive: bool = True,
    ) -> None:
        # This forces tesseract to use one core per page.
        os.environ["OMP_THREAD_LIMIT"] = "1"

        import ocrmypdf
        from ocrmypdf import EncryptedPdfError
        from ocrmypdf import InputFileError
        from ocrmypdf import SubprocessOutputError
        from ocrmypdf.exceptions import DigitalSignatureError
        from ocrmypdf.exceptions import PriorOcrFoundError

        if mime_type == "application/pdf":
            text_original = self.extract_text(None, document_path)
            original_has_text = is_tagged_pdf(document_path, log=self.log) or (
                text_original is not None and len(text_original) > PDF_TEXT_MIN_LENGTH
            )
        else:
            text_original = None
            original_has_text = False

        self.log.debug(
            "Text detection: original_has_text=%s (text_length=%d, mode=%s, produce_archive=%s)",
            original_has_text,
            len(text_original) if text_original else 0,
            self.settings.mode,
            produce_archive,
        )

        # --- OCR_MODE=off: never invoke OCR engine ---
        if self.settings.mode == ModeChoices.OFF:
            if not produce_archive:
                self.log.debug(
                    "OCR: skipped — OCR_MODE=off, no archive requested;"
                    " returning pdftotext content only",
                )
                self.text = text_original or ""
                return
            if self.is_image(mime_type):
                self.log.debug(
                    "OCR: skipped — OCR_MODE=off, image input;"
                    " converting to PDF/A without OCR",
                )
                try:
                    self.archive_path = self._convert_image_to_pdfa(
                        document_path,
                    )
                    self.text = ""
                except Exception as e:
                    raise ParseError(
                        f"Image to PDF/A conversion failed: {e!s}",
                    ) from e
                return
            # PDFs in off mode: PDF/A conversion via Ghostscript, no OCR
            archive_path = Path(self.tempdir) / "archive.pdf"
            try:
                self._convert_pdf_to_pdfa(document_path, archive_path)
                self.archive_path = archive_path
                self.text = text_original or ""
            except SubprocessOutputError as e:
                self._handle_subprocess_output_error(e)
            except Exception as e:
                raise ParseError(f"{e.__class__.__name__}: {e!s}") from e
            return

        # --- OCR_MODE=auto: skip ocrmypdf entirely if text exists and no archive needed ---
        if (
            self.settings.mode == ModeChoices.AUTO
            and original_has_text
            and not produce_archive
        ):
            self.log.debug(
                "Document has text and no archive requested; skipping OCRmyPDF entirely.",
            )
            self.text = text_original
            return

        # --- All other paths: run ocrmypdf ---
        archive_path = Path(self.tempdir) / "archive.pdf"
        sidecar_file = Path(self.tempdir) / "sidecar.txt"

        # auto mode with existing text: PDF/A conversion only (no OCR).
        skip_text = self.settings.mode == ModeChoices.AUTO and original_has_text

        if skip_text:
            self.log.debug(
                "OCR strategy: PDF/A conversion only (skip_text)"
                " — OCR_MODE=auto, document already has text",
            )
        else:
            self.log.debug("OCR strategy: full OCR — OCR_MODE=%s", self.settings.mode)

        args = self.construct_ocrmypdf_parameters(
            document_path,
            mime_type,
            archive_path,
            sidecar_file,
            skip_text=skip_text,
        )

        try:
            self.log.debug(f"Calling OCRmyPDF with args: {args}")
            ocrmypdf.ocr(**args)

            if produce_archive:
                self.archive_path = archive_path

            self.text = self.extract_text(sidecar_file, archive_path)

            if not self.text:
                raise NoTextFoundException("No text was found in the original document")
        except (DigitalSignatureError, EncryptedPdfError):
            self.log.warning(
                "This file is encrypted and/or signed, OCR is impossible. Using "
                "any text present in the original file.",
            )
            if original_has_text:
                self.text = text_original
        except SubprocessOutputError as e:
            self._handle_subprocess_output_error(e)
        except (NoTextFoundException, InputFileError, PriorOcrFoundError) as e:
            self.log.warning(
                f"Encountered an error while running OCR: {e!s}. "
                f"Attempting force OCR to get the text.",
            )

            archive_path_fallback = Path(self.tempdir) / "archive-fallback.pdf"
            sidecar_file_fallback = Path(self.tempdir) / "sidecar-fallback.txt"

            args = self.construct_ocrmypdf_parameters(
                document_path,
                mime_type,
                archive_path_fallback,
                sidecar_file_fallback,
                safe_fallback=True,
            )

            try:
                self.log.debug(f"Fallback: Calling OCRmyPDF with args: {args}")
                ocrmypdf.ocr(**args)
                self.text = self.extract_text(
                    sidecar_file_fallback,
                    archive_path_fallback,
                )
                if produce_archive:
                    self.archive_path = archive_path_fallback
            except Exception as e:
                raise ParseError(f"{e.__class__.__name__}: {e!s}") from e

        except Exception as e:
            raise ParseError(f"{e.__class__.__name__}: {e!s}") from e

        if not self.text:
            if original_has_text:
                self.text = text_original
            else:
                self.log.warning(
                    f"No text was found in {document_path}, the content will be empty.",
                )
                self.text = ""


def post_process_text(text: str | None) -> str | None:
    if not text:
        return None

    collapsed_spaces = re.sub(r"([^\S\r\n]+)", " ", text)
    no_leading_whitespace = re.sub(r"([\n\r]+)([^\S\n\r]+)", "\\1", collapsed_spaces)
    no_trailing_whitespace = re.sub(r"([^\S\n\r]+)$", "", no_leading_whitespace)

    # TODO: this needs a rework
    # replace \0 prevents issues with saving to postgres.
    # text may contain \0 when this character is present in PDF files.
    return no_trailing_whitespace.strip().replace("\0", " ")
