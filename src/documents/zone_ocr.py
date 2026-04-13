"""
Zone-based OCR extraction engine.

After a document is consumed, this module checks if the document's type has
an active OCR template. If so, it renders the relevant pages as images,
crops each zone, runs Tesseract OCR on the crop, applies transforms,
and writes the results to the mapped custom fields.
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models_ocr_templates import OcrTemplate
from documents.models_ocr_templates import OcrTemplateZone

if TYPE_CHECKING:
    pass

logger = logging.getLogger("paperless.zone_ocr")


def run_zone_extraction(
    document: Document,
    original_file: Path | None,
) -> None:
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

    # Resolve the document file: prefer archive (PDF/A), then source, then signal arg
    doc_path = _resolve_doc_path(document, original_file)
    if doc_path is None:
        logger.warning(
            "Zone OCR: no accessible file for document %d",
            document.pk,
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


def _resolve_doc_path(
    document: Document,
    original_file: Path | None,
) -> Path | None:
    """Find an accessible file for the document."""
    candidates = []
    if document.has_archive_version:
        candidates.append(document.archive_path)
    candidates.append(document.source_path)
    if original_file is not None:
        candidates.append(original_file)

    for path in candidates:
        if path is not None and Path(path).is_file():
            return Path(path)
    return None


def _process_template(
    document: Document,
    doc_path: Path,
    template: OcrTemplate,
    zones: list[OcrTemplateZone],
) -> None:
    """Process all zones in a template against a document."""
    pages_needed: set[int] = set()
    for zone in zones:
        page = zone.page if zone.page is not None else template.default_page
        pages_needed.add(page)

    with tempfile.TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp_dir:
        tmp_path = Path(tmp_dir)

        page_images = _render_pages(
            doc_path, pages_needed, tmp_path, document.page_count,
        )

        for zone in zones:
            page_idx = zone.page if zone.page is not None else template.default_page

            # Resolve negative page indices
            if page_idx < 0 and document.page_count:
                page_idx = document.page_count + page_idx

            if page_idx not in page_images:
                logger.warning(
                    "Zone OCR: page %d not available for zone '%s'",
                    page_idx,
                    zone.name,
                )
                continue

            extracted = _extract_zone(
                page_images[page_idx],
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
    """Render specific PDF pages as PNG images using pdftoppm (poppler-utils)."""
    result: dict[int, Path] = {}
    mime = _detect_mime(doc_path)

    if mime and mime.startswith("image/"):
        # Document is already an image — use directly for page 0
        result[0] = doc_path
        return result

    for page_idx in pages:
        actual_page = page_idx
        if actual_page < 0 and page_count:
            actual_page = page_count + actual_page

        if actual_page < 0:
            logger.warning("Zone OCR: invalid page index %d", page_idx)
            continue

        output_prefix = tmp_dir / f"page_{actual_page}"
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-png",
                    "-r", "300",
                    "-f", str(actual_page + 1),  # pdftoppm is 1-indexed
                    "-l", str(actual_page + 1),
                    str(doc_path),
                    str(output_prefix),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            logger.error("Zone OCR: pdftoppm timed out for page %d", actual_page)
            continue
        except subprocess.CalledProcessError as e:
            logger.error(
                "Zone OCR: pdftoppm failed for page %d: %s",
                actual_page,
                e.stderr.decode(errors="replace") if e.stderr else str(e),
            )
            continue
        except FileNotFoundError:
            logger.error("Zone OCR: pdftoppm not found — is poppler-utils installed?")
            return result  # No point trying other pages

        # pdftoppm names output as prefix-NNNN.png
        rendered = sorted(tmp_dir.glob(f"page_{actual_page}-*.png"))
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
    from PIL import Image

    try:
        with Image.open(page_img) as img:
            img_width, img_height = img.size

            # Scale zone coordinates from template dimensions to actual image
            scale_x = img_width / source_width
            scale_y = img_height / source_height

            crop_left = int(zone.x * scale_x)
            crop_top = int(zone.y * scale_y)
            crop_right = int((zone.x + zone.width) * scale_x)
            crop_bottom = int((zone.y + zone.height) * scale_y)

            # Clamp to image bounds
            crop_left = max(0, min(crop_left, img_width))
            crop_top = max(0, min(crop_top, img_height))
            crop_right = max(crop_left + 1, min(crop_right, img_width))
            crop_bottom = max(crop_top + 1, min(crop_bottom, img_height))

            if crop_right - crop_left < 2 or crop_bottom - crop_top < 2:
                logger.warning("Zone OCR: crop too small for zone '%s'", zone.name)
                return None

            cropped = img.crop((crop_left, crop_top, crop_right, crop_bottom))
            crop_path = tmp_dir / f"zone_{zone.pk}.png"
            cropped.save(crop_path)
    except Exception:
        logger.exception("Zone OCR: crop failed for zone '%s'", zone.name)
        return None

    # OCR the cropped image with Tesseract
    try:
        proc = subprocess.run(
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
            check=True,
        )
        text = proc.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error("Zone OCR: Tesseract timed out for zone '%s'", zone.name)
        return None
    except subprocess.CalledProcessError as e:
        logger.error(
            "Zone OCR: Tesseract failed for zone '%s': %s",
            zone.name,
            e.stderr[:200] if e.stderr else str(e),
        )
        return None
    except FileNotFoundError:
        logger.error("Zone OCR: Tesseract not found — is tesseract-ocr installed?")
        return None

    if not text:
        return None

    return _apply_transform(text, zone.transform)


def _apply_transform(text: str, transform: str) -> str:
    """Apply post-processing transform to extracted text."""
    text = text.strip()
    if not text:
        return text

    if transform in ("strip", "none"):
        return text
    elif transform == "uppercase":
        return text.upper()
    elif transform == "lowercase":
        return text.lower()
    elif transform == "numeric":
        result = re.sub(r"[^\d.,\-]", "", text)
        return result if result else text
    elif transform == "date_dmy":
        match = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", text)
        if match:
            d, m, y = match.groups()
            if len(y) == 2:
                y = "20" + y
            try:
                return date(int(y), int(m), int(d)).isoformat()
            except ValueError:
                pass
        return text
    elif transform == "date_ymd":
        match = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
        if match:
            y, m, d = match.groups()
            try:
                return date(int(y), int(m), int(d)).isoformat()
            except ValueError:
                pass
        return text
    return text


def _write_custom_field(
    document: Document,
    custom_field: CustomField,
    value: str,
) -> None:
    """Write an extracted value to a document's custom field."""
    typed_value = _convert_value(value, custom_field.data_type)
    if typed_value is None:
        logger.debug(
            "Zone OCR: skipping custom field '%s' — value conversion returned None",
            custom_field.name,
        )
        return

    value_field_name = CustomFieldInstance.get_value_field_name(custom_field.data_type)

    CustomFieldInstance.objects.update_or_create(
        document=document,
        field=custom_field,
        defaults={value_field_name: typed_value},
    )


def _convert_value(value: str, data_type: str) -> object | None:
    """Convert an extracted OCR string to the appropriate type for the custom field."""
    if not value:
        return None

    try:
        if data_type in (
            CustomField.FieldDataType.STRING,
            CustomField.FieldDataType.URL,
        ):
            return value[:128]

        elif data_type == CustomField.FieldDataType.LONG_TEXT:
            return value

        elif data_type == CustomField.FieldDataType.INT:
            digits = re.sub(r"[^\d\-]", "", value)
            # Handle edge case: only dashes or empty
            digits = digits.lstrip("-") or ""
            if not digits:
                return None
            # Restore leading minus if original had one
            if value.strip().startswith("-"):
                digits = "-" + digits
            return int(digits)

        elif data_type == CustomField.FieldDataType.FLOAT:
            # Handle European format: 1.234,56 → 1234.56
            cleaned = re.sub(r"[^\d.,\-]", "", value)
            if not cleaned or cleaned in (".", ",", "-"):
                return None
            # If both . and , present, the last one is the decimal separator
            if "," in cleaned and "." in cleaned:
                if cleaned.rindex(",") > cleaned.rindex("."):
                    # European: 1.234,56
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                else:
                    # US: 1,234.56
                    cleaned = cleaned.replace(",", "")
            elif "," in cleaned:
                # Only comma — treat as decimal separator
                cleaned = cleaned.replace(",", ".")
            return float(cleaned)

        elif data_type == CustomField.FieldDataType.DATE:
            match = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
            if match:
                y, m, d = match.groups()
                # Validate the date
                date(int(y), int(m), int(d))
                return f"{y}-{m}-{d}"
            return None

        elif data_type == CustomField.FieldDataType.MONETARY:
            cleaned = re.sub(r"[^\d.,\-]", "", value)
            if not cleaned or cleaned in (".", ",", "-"):
                return None
            if "," in cleaned and "." in cleaned:
                if cleaned.rindex(",") > cleaned.rindex("."):
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            elif "," in cleaned:
                cleaned = cleaned.replace(",", ".")
            # Validate it parses as a number
            float(cleaned)
            return cleaned

        elif data_type == CustomField.FieldDataType.BOOL:
            lower = value.lower().strip()
            if lower in ("true", "yes", "1", "ja", "oui", "si", "x"):
                return True
            elif lower in ("false", "no", "0", "nein", "non"):
                return False
            return None

        else:
            # Unsupported types (DOCUMENTLINK, SELECT) — can't OCR into these
            logger.debug(
                "Zone OCR: unsupported custom field type %s for OCR extraction",
                data_type,
            )
            return None

    except (ValueError, TypeError) as e:
        logger.warning("Zone OCR: could not convert %r to %s: %s", value, data_type, e)
        return None


def _detect_mime(path: Path) -> str | None:
    """Detect MIME type of a file."""
    try:
        import magic

        return magic.from_file(str(path), mime=True)
    except ImportError:
        pass
    except Exception:
        logger.debug("Zone OCR: magic failed for %s, falling back to extension", path)

    suffix = path.suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
    }.get(suffix)
