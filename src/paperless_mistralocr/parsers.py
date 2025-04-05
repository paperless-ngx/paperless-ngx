import base64
import re
from pathlib import Path

import magic
from django.conf import settings

try:
    from mistralai import Mistral
    from mistralai.models import DocumentURLChunk
    from mistralai.models import ImageURLChunk
    from mistralai.models import OCRResponse
    from mistralai.models import SDKError

    HAS_MISTRAL = True
except ImportError:
    HAS_MISTRAL = False


from documents.parsers import DocumentParser
from documents.parsers import ParseError
from documents.parsers import make_thumbnail_from_pdf
from documents.utils import run_subprocess
from paperless_mistralocr.config import MistralOcrConfig


class MistralOcrDocumentParser(DocumentParser):
    """
    This parser uses Mistral AI's OCR API to extract text and understand documents
    """

    logging_name = "paperless.parsing.mistral_ocr"
    settings: MistralOcrConfig
    ocr_images: list[str]  # base64 encoded images

    if not HAS_MISTRAL:
        raise ParseError(
            "mistralai package is not installed. Please install it with: pip install mistralai"
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ocr_image_paths = []

    def get_settings(self) -> MistralOcrConfig:
        """
        This parser uses the Mistral OCR configuration settings
        """
        return MistralOcrConfig()

    def get_page_count(self, document_path, mime_type):
        page_count = None
        if mime_type == "application/pdf":
            try:
                import pikepdf

                with pikepdf.Pdf.open(document_path) as pdf:
                    page_count = len(pdf.pages)
            except Exception as e:
                self.log.warning(
                    f"Unable to determine PDF page count {document_path}: {e}",
                )
        return page_count

    def extract_metadata(self, document_path, mime_type):
        result = []
        if mime_type == "application/pdf":
            import pikepdf

            namespace_pattern = re.compile(r"\{(.*)\}(.*)")

            pdf = pikepdf.open(document_path)
            meta = pdf.open_metadata()
            for key, value in meta.items():
                if isinstance(value, list):
                    value = " ".join([str(e) for e in value])
                value = str(value)
                try:
                    m = namespace_pattern.match(key)
                    if m is None:  # pragma: no cover
                        continue
                    namespace = m.group(1)
                    key_value = m.group(2)
                    try:
                        namespace.encode("utf-8")
                        key_value.encode("utf-8")
                    except UnicodeEncodeError as e:  # pragma: no cover
                        self.log.debug(f"Skipping metadata key {key}: {e}")
                        continue
                    result.append(
                        {
                            "namespace": namespace,
                            "prefix": meta.REVERSE_NS[namespace],
                            "key": key_value,
                            "value": value,
                        },
                    )
                except Exception as e:
                    self.log.warning(
                        f"Error while reading metadata {key}: {value}. Error: {e}",
                    )
        return result

    def get_thumbnail(self, document_path, mime_type, file_name=None):
        """
        Generate a thumbnail for the document.
        For PDFs, use the existing PDF thumbnail creation method.
        For images, create a thumbnail directly.
        """
        if mime_type == "application/pdf":
            return make_thumbnail_from_pdf(
                document_path,
                self.tempdir,
                self.logging_group,
            )
        elif self.is_image(mime_type):
            return self._make_thumbnail_from_image(document_path)
        else:
            # Fall back to PDF conversion for other types
            if not self.archive_path:
                # Convert to PDF and then create thumbnail
                self.archive_path = self._convert_to_pdf(document_path)

            return make_thumbnail_from_pdf(
                self.archive_path,
                self.tempdir,
                self.logging_group,
            )

    def get_ocr_images(self) -> list[str] | None:
        return self.ocr_images

    def is_image(self, mime_type) -> bool:
        """
        Check if the mime type is an image
        """
        return mime_type in [
            "image/png",
            "image/jpeg",
            "image/tiff",
            "image/bmp",
            "image/gif",
            "image/webp",
        ]

    def _make_thumbnail_from_image(self, image_path):
        """
        Create a thumbnail from an image file
        """
        out_path = self.tempdir / "thumb.webp"

        try:
            run_subprocess(
                [
                    settings.CONVERT_BINARY,
                    "-density",
                    "300",
                    "-scale",
                    "500x5000>",
                    "-alpha",
                    "remove",
                    "-strip",
                    "-auto-orient",
                    str(image_path),
                    str(out_path),
                ],
                logger=self.log,
            )
            return out_path
        except Exception as e:
            self.log.warning(f"Error creating thumbnail from image: {e}")
            return Path(self.tempdir) / "default.webp"

    def parse(self, document_path: Path, mime_type: str, file_name=None):
        """
        Parse the document using Mistral OCR API
        """
        self.log.info(f"Parsing {document_path} with Mistral OCR API")

        # Initialize empty ocr_image_paths list
        self.ocr_image_paths = []

        ocr_response = self._call_mistral_api(document_path, mime_type)

        # Extract text content from the OCR response
        self.text, self.ocr_images = self.get_combined_markdown(ocr_response)

        # If date wasn't found in metadata, try to extract it from text
        if self.text:
            from documents.parsers import parse_date

            self.date = parse_date(str(document_path), self.text)

        # If document is not a PDF, convert it to PDF for archiving
        if mime_type != "application/pdf":
            self.archive_path = self._convert_to_pdf(document_path)

    def _call_mistral_api(self, document_path: Path, mime_type: str) -> OCRResponse:
        """
        Call the Mistral OCR API to extract text and metadata from the document
        """

        api_key = self.settings.api_key
        if not api_key:
            raise ParseError(
                "Mistral API key not configured. Please set PAPERLESS_MISTRAL_API_KEY in environment."
            )

        model = self.settings.model

        # Check file size before uploading
        file_size = Path(document_path).stat().st_size
        if file_size > 50 * 1024 * 1024:  # 50MB limit
            raise ParseError(
                f"File size too large for Mistral API: {file_size / (1024 * 1024):.2f}MB (max 50MB)"
            )

        try:
            # Create Mistral client
            self.log.debug("Initializing Mistral client for OCR processing")
            client = Mistral(api_key=api_key)

            # Determine if the file is an image or PDF
            is_image = self.is_image(mime_type)

            # Process the document
            self.log.debug(f"Calling Mistral OCR API for {document_path}")

            # Read file and encode it as base64
            with Path(document_path).open("rb") as f:
                file_content = f.read()
                file_base64 = base64.b64encode(file_content).decode("utf-8")

            mime_prefix = (
                "data:image/jpeg;base64,"
                if is_image
                else "data:application/pdf;base64,"
            )

            # Call the appropriate OCR method based on the file type
            document = (
                ImageURLChunk(image_url=f"{mime_prefix}{file_base64}")
                if is_image
                else DocumentURLChunk(document_url=f"{mime_prefix}{file_base64}")
            )

            # Call OCR API with base64 encoded content
            ocr_response = client.ocr.process(
                model=model,
                document=document,
                include_image_base64=True,
            )

            return ocr_response

        except Exception as e:
            if isinstance(e, SDKError):
                raise ParseError(f"Mistral API error: {e!s}")
            raise ParseError(f"Error calling Mistral OCR API: {e!s}")

    def get_combined_markdown(self, ocr_response: OCRResponse) -> tuple[str, list[str]]:
        """
        Combine OCR text and images into a single markdown document.
        Save images as files instead of embedding them.

        Args:
            ocr_response: Response from OCR processing containing text and images

        Returns:
            Tuple of (combined markdown string, list of images in base64 format)
        """
        markdowns = []
        img_index = 0

        ocr_images = []

        # Extract images from each page
        for page in ocr_response.pages:
            markdown_str = page.markdown

            # Extract images from the page
            for img in page.images:
                if img.image_base64:
                    ocr_images.append(img.image_base64)
                    markdown_str = markdown_str.replace(
                        f"![{img.id}]({img.id})",
                        f"![{img.id}]([OCR_IMAGE:{img_index}])",
                    )
                    img_index += 1

            markdowns.append(markdown_str)

        return "\n\n".join(markdowns), ocr_images

    def _convert_to_pdf(self, document_path: Path) -> Path:
        """
        Convert the document to PDF format for archiving
        """
        from django.conf import settings

        pdf_path = Path(self.tempdir) / "convert.pdf"

        # If it's an image, use convert/ImageMagick
        if self.is_image(magic.from_file(document_path, mime=True)):
            self.log.info(f"Converting image {document_path} to PDF")
            try:
                run_subprocess(
                    [
                        settings.CONVERT_BINARY,
                        str(document_path),
                        str(pdf_path),
                    ],
                    logger=self.log,
                )
                return pdf_path
            except Exception as e:
                raise ParseError(f"Error converting image to PDF: {e}")

        # For other document types, try to use Gotenberg if available
        try:
            from django.conf import settings
            from gotenberg_client import GotenbergClient
            from gotenberg_client.options import PdfAFormat

            self.log.info(f"Converting {document_path} to PDF using Gotenberg")

            with (
                GotenbergClient(
                    host=settings.TIKA_GOTENBERG_ENDPOINT,
                    timeout=settings.CELERY_TASK_TIME_LIMIT,
                ) as client,
                client.libre_office.to_pdf() as route,
            ):
                # Set the output format of the resulting PDF
                if settings.OCR_OUTPUT_TYPE in {"pdfa", "pdfa-2"}:
                    route.pdf_format(PdfAFormat.A2b)
                elif settings.OCR_OUTPUT_TYPE == "pdfa-1":
                    route.pdf_format(PdfAFormat.A2b)  # Fallback
                elif settings.OCR_OUTPUT_TYPE == "pdfa-3":
                    route.pdf_format(PdfAFormat.A3b)

                route.convert(document_path)

                try:
                    response = route.run()
                    pdf_path.write_bytes(response.content)
                    return pdf_path
                except Exception as err:
                    raise ParseError(f"Error while converting document to PDF: {err}")

        except ImportError:
            self.log.warning("Gotenberg client not available for PDF conversion")
        except Exception as e:
            self.log.warning(f"Error using Gotenberg for conversion: {e}")

        # If we get here, we couldn't convert the document to PDF
        raise ParseError(f"Could not convert {document_path} to PDF format")

    def get_ocr_image_paths(self) -> list[str]:
        """
        Return the list of saved OCR image paths
        """
        return self.ocr_image_paths
