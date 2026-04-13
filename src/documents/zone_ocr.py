"""
Zone-based OCR extraction engine.

After a document is consumed, this module checks if the document's type has
an active OCR template. If so, it renders the relevant pages as images,
crops each zone, runs Tesseract OCR on the crop, applies transforms,
and writes the results to the mapped custom fields.
"""

import logging
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models_ocr_templates import OcrTemplate
from documents.models_ocr_templates import OcrTemplateZone

logger = logging.getLogger("paperless.zone_ocr")


def run_zone_extraction(document: Document, original_file: Path) -> None:
    """
    Run zone-based OCR extraction for a document if its type has an active template.
    Called from the document_consumption_finished signal handler.
    """
    if not document.document_type_id:
        return

    templates = OcrTemplate.objects.filter(
        document_type_id=document.document_type_id,
        enabled=True,
    ).prefetch_related("zones", "zones__custom_field")

    if not templates.exists():
        return

    # Use the archive path (PDF/A) if available, otherwise source
    doc_path = document.archive_path or document.source_path
    if not doc_path or not Path(doc_path).exists():
        # Fallback to original file passed by the signal
        doc_path = original_file

    if not Path(doc_path).exists():
        logger.warning(
            "Zone OCR: document file not found for doc %d: %s",
            document.pk,
            doc_path,
        )
        return

    for template in templates:
        zones = list(template.zones.all())
        if not zones:
            continue

        logger.info(
            "Zone OCR: processing template '%s' for document %d (%d zones)",
            template.name,
            document.pk,
            len(zones),
        )

        try:
            _process_template(document, doc_path, template, zones)
        except Exception:
            logger.exception(
                "Zone OCR: error processing template '%s' for document %d",
                template.name,
                document.pk,
            )


def _process_template(
    document: Document,
    doc_path: Path,
    template: OcrTemplate,
    zones: list[OcrTemplateZone],
) -> None:
    """Process all zones in a template against a document."""
    # Determine which pages we need
    pages_needed = set()
    for zone in zones:
        page = zone.page if zone.page is not None else template.default_page
        pages_needed.add(page)

    with tempfile.TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Render needed pages as images
        page_images = _render_pages(doc_path, pages_needed, tmp_path, document.page_count)

        for zone in zones:
            page_idx = zone.page if zone.page is not None else template.default_page
            if page_idx < 0 and document.page_count:
                page_idx = document.page_count + page_idx

            if page_idx not in page_images:
                logger.warning(
                    "Zone OCR: page %d not available for zone '%s'",
                    page_idx,
                    zone.name,
                )
                continue

            page_img = page_images[page_idx]
            extracted = _extract_zone(
                page_img,
                zone,
                template.source_width,
                template.source_height,
                tmp_path,
            )

            if extracted is not None:
                _write_custom_field(document, zone.custom_field, extracted)
                logger.info(
                    "Zone OCR: '%s' → %s = %r",
                    zone.name,
                    zone.custom_field.name,
                    extracted[:100] if len(extracted) > 100 else extracted,
                )


def _render_pages(
    doc_path: Path,
    pages: set[int],
    tmp_dir: Path,
    page_count: int | None,
) -> dict[int, Path]:
    """Render specific PDF pages as PNG images using Ghostscript or ImageMagick."""
    result = {}
    mime = _detect_mime(doc_path)

    if mime and mime.startswith("image/"):
        # Document is already an image — use directly for page 0
        result[0] = doc_path
        return result

    # Use pdftoppm (from poppler-utils) for PDF rendering — fast and reliable
    for page_idx in pages:
        actual_page = page_idx
        if actual_page < 0 and page_count:
            actual_page = page_count + actual_page

        output_prefix = tmp_dir / f"page_{actual_page}"
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-png",
                    "-r", "300",  # 300 DPI for good OCR quality
                    "-f", str(actual_page + 1),  # pdftoppm is 1-indexed
                    "-l", str(actual_page + 1),
                    str(doc_path),
                    str(output_prefix),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.exception("Zone OCR: pdftoppm failed for page %d", actual_page)
            continue

        # pdftoppm names output as prefix-NNNN.png
        rendered = list(tmp_dir.glob(f"page_{actual_page}-*.png"))
        if rendered:
            result[page_idx] = rendered[0]

    return result


def _extract_zone(
    page_img: Path,
    zone: OcrTemplateZone,
    source_width: int,
    source_height: int,
    tmp_dir: Path,
) -> str | None:
    """Crop a zone from the page image and OCR it."""
    # Get actual image dimensions for coordinate scaling
    try:
        from PIL import Image

        with Image.open(page_img) as img:
            img_width, img_height = img.size

            # Scale zone coordinates from source (template) dimensions to actual image
            scale_x = img_width / source_width
            scale_y = img_height / source_height

            crop_x = int(zone.x * scale_x)
            crop_y = int(zone.y * scale_y)
            crop_w = int(zone.width * scale_x)
            crop_h = int(zone.height * scale_y)

            # Clamp to image bounds
            crop_x = max(0, min(crop_x, img_width - 1))
            crop_y = max(0, min(crop_y, img_height - 1))
            crop_w = min(crop_w, img_width - crop_x)
            crop_h = min(crop_h, img_height - crop_y)

            if crop_w <= 0 or crop_h <= 0:
                logger.warning("Zone OCR: zero-size crop for zone '%s'", zone.name)
                return None

            cropped = img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
            crop_path = tmp_dir / f"zone_{zone.pk}.png"
            cropped.save(crop_path)
    except Exception:
        logger.exception("Zone OCR: crop failed for zone '%s'", zone.name)
        return None

    # OCR the cropped image with Tesseract
    try:
        result = subprocess.run(
            [
                "tesseract",
                str(crop_path),
                "stdout",
                "-l", zone.ocr_language,
                "--psm", "6",  # Assume uniform block of text
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.exception("Zone OCR: Tesseract failed for zone '%s'", zone.name)
        return None

    if not text:
        return None

    return _apply_transform(text, zone.transform)


def _apply_transform(text: str, transform: str) -> str:
    """Apply post-processing transform to extracted text."""
    if transform == "strip" or transform == "none":
        return text.strip()
    elif transform == "uppercase":
        return text.strip().upper()
    elif transform == "lowercase":
        return text.strip().lower()
    elif transform == "numeric":
        return re.sub(r"[^\d.,\-]", "", text)
    elif transform == "date_dmy":
        # Try to parse DD.MM.YYYY or DD/MM/YYYY
        match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", text)
        if match:
            d, m, y = match.groups()
            if len(y) == 2:
                y = "20" + y
            try:
                return datetime(int(y), int(m), int(d)).strftime("%Y-%m-%d")
            except ValueError:
                pass
        return text.strip()
    elif transform == "date_ymd":
        match = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
        if match:
            y, m, d = match.groups()
            try:
                return datetime(int(y), int(m), int(d)).strftime("%Y-%m-%d")
            except ValueError:
                pass
        return text.strip()
    return text.strip()


def _write_custom_field(
    document: Document,
    custom_field: CustomField,
    value: str,
) -> None:
    """Write an extracted value to a document's custom field."""
    value_field_name = CustomFieldInstance.get_value_field_name(custom_field.data_type)

    # Convert value to the right type
    typed_value = _convert_value(value, custom_field.data_type)
    if typed_value is None:
        return

    CustomFieldInstance.objects.update_or_create(
        document=document,
        field=custom_field,
        defaults={value_field_name: typed_value},
    )


def _convert_value(value: str, data_type: str) -> object | None:
    """Convert extracted string to the appropriate type for the custom field."""
    try:
        if data_type in (CustomField.FieldDataType.STRING, CustomField.FieldDataType.URL):
            return value[:128]
        elif data_type == CustomField.FieldDataType.LONG_TEXT:
            return value
        elif data_type == CustomField.FieldDataType.INT:
            return int(re.sub(r"[^\d\-]", "", value))
        elif data_type == CustomField.FieldDataType.FLOAT:
            cleaned = re.sub(r"[^\d.,\-]", "", value)
            cleaned = cleaned.replace(",", ".")
            return float(cleaned)
        elif data_type == CustomField.FieldDataType.DATE:
            # Try ISO format first
            match = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
            if match:
                return value
            return None
        elif data_type == CustomField.FieldDataType.MONETARY:
            cleaned = re.sub(r"[^\d.,\-]", "", value).replace(",", ".")
            return cleaned
        else:
            return value[:128]
    except (ValueError, TypeError):
        logger.warning("Zone OCR: could not convert %r to %s", value, data_type)
        return None


def _detect_mime(path: Path) -> str | None:
    """Quick MIME detection."""
    try:
        import magic

        return magic.from_file(str(path), mime=True)
    except Exception:
        suffix = path.suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
        }
        return mime_map.get(suffix)
