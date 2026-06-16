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
import string
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
from documents.models import OcrTemplate
from documents.models import OcrTemplateZone

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


def _resolve_page_idx(page_value, page_count) -> int:
    """Resolve a 1-indexed page (1 = first, -1 = last) to a 0-indexed image
    index. A blank page_value defaults to the first page."""
    if page_value is None:
        return 0
    if page_value == -1:
        return (page_count - 1) if page_count else 0
    if page_value >= 1:
        return page_value - 1
    return 0


def _process_template(
    document: Document,
    doc_path: Path,
    template: OcrTemplate,
    zones: list[OcrTemplateZone],
) -> None:
    """Process all zones in a template against a document."""
    pages_needed: set[int] = {
        _resolve_page_idx(zone.page, document.page_count) for zone in zones
    }

    with tempfile.TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp_dir:
        tmp_path = Path(tmp_dir)

        page_images = _render_pages(
            doc_path, pages_needed, tmp_path, document.page_count,
        )

        for zone in zones:
            page_idx = _resolve_page_idx(zone.page, document.page_count)

            if page_idx not in page_images:
                logger.warning(
                    "Zone OCR: page %d not available for zone '%s'",
                    page_idx,
                    zone.name,
                )
                continue

            # Use per-zone source dimensions if set, otherwise template default
            src_w = zone.zone_source_width or template.source_width
            src_h = zone.zone_source_height or template.source_height

            extracted = _extract_zone(
                page_images[page_idx],
                zone,
                src_w,
                src_h,
                tmp_path,
            )

            if extracted is not None:
                # Validate against regex if configured
                if zone.validation_regex:
                    if not re.fullmatch(zone.validation_regex, extracted):
                        logger.info(
                            "Zone OCR: '%s' value %r rejected by regex '%s'",
                            zone.name,
                            extracted[:100],
                            zone.validation_regex,
                        )
                        continue

                _write_zone_value(document, zone, extracted)
                logger.info(
                    "Zone OCR: '%s' → %s = %r",
                    zone.name,
                    _zone_target_label(zone),
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


def _crop_zone(
    page_img: Path,
    zone: OcrTemplateZone,
    source_width: int,
    source_height: int,
    tmp_dir: Path,
) -> "Image.Image | None":
    """Crop a zone from the page image and return the PIL Image."""
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

            return img.crop((crop_left, crop_top, crop_right, crop_bottom)).copy()
    except Exception:
        logger.exception("Zone OCR: crop failed for zone '%s'", zone.name)
        return None


def _read_barcode(cropped: "Image.Image", zone_name: str) -> str | None:
    """Read QR/barcode from a cropped image using zxingcpp."""
    try:
        import zxingcpp

        results = zxingcpp.read_barcodes(cropped)
        if results:
            text = results[0].text
            logger.debug("Zone OCR: barcode found in zone '%s': %s", zone_name, text[:100])
            return text
        logger.debug("Zone OCR: no barcode found in zone '%s'", zone_name)
        return None
    except ImportError:
        logger.error("Zone OCR: zxingcpp not available — install zxing-cpp")
        return None
    except Exception:
        logger.exception("Zone OCR: barcode read failed for zone '%s'", zone_name)
        return None


def _ocr_text(cropped: "Image.Image", zone: OcrTemplateZone, tmp_dir: Path) -> str | None:
    """OCR a cropped image with Tesseract."""
    crop_path = tmp_dir / f"zone_{zone.pk}.png"
    cropped.save(crop_path)

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
        return proc.stdout.strip() or None
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


def _extract_zone(
    page_img: Path,
    zone: OcrTemplateZone,
    source_width: int,
    source_height: int,
    tmp_dir: Path,
) -> str | None:
    """Crop a zone from the page image and extract text via OCR or barcode reader."""
    cropped = _crop_zone(page_img, zone, source_width, source_height, tmp_dir)
    if cropped is None:
        return None

    # QR/barcode zones skip Tesseract entirely
    if zone.transform == "qr_code":
        text = _read_barcode(cropped, zone.name)
        if not text:
            return None
        return _apply_transform(text, zone.transform, getattr(zone, "date_format", "") or "")

    # Standard OCR path
    text = _ocr_text(cropped, zone, tmp_dir)
    if not text:
        return None

    return _apply_transform(text, zone.transform, getattr(zone, "date_format", "") or "")


def extract_zone_preview(
    doc_path: Path,
    zone: OcrTemplateZone,
    source_width: int,
    source_height: int,
    page_count: int | None,
) -> dict:
    """Non-destructive single-zone extraction for the editor's per-zone test.

    Renders the zone's page, crops it, runs OCR (or the barcode reader) and
    applies the transform — WITHOUT writing any custom field. Returns the raw
    OCR text and the transformed value so the user can see what the zone yields
    (and tune the validation regex) before saving.
    """
    page_idx = zone.page if zone.page is not None else 0
    with tempfile.TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp_dir:
        tmp_path = Path(tmp_dir)
        page_images = _render_pages(doc_path, {page_idx}, tmp_path, page_count)
        if page_idx not in page_images:
            return {"raw_text": None, "value": None}

        if not source_width or not source_height:
            from PIL import Image

            with Image.open(page_images[page_idx]) as im:
                source_width, source_height = im.size

        cropped = _crop_zone(
            page_images[page_idx],
            zone,
            source_width,
            source_height,
            tmp_path,
        )
        if cropped is None:
            return {"raw_text": None, "value": None}

        if zone.transform == "qr_code":
            raw_text = _read_barcode(cropped, zone.name)
        else:
            raw_text = _ocr_text(cropped, zone, tmp_path)

        value = (
            _apply_transform(
                raw_text,
                zone.transform,
                getattr(zone, "date_format", "") or "",
            )
            if raw_text
            else None
        )
        return {"raw_text": raw_text, "value": value}


def _parse_date(text: str, fmt: str) -> str:
    """Parse a date from OCR text. With a Python strptime `fmt`, try that first;
    otherwise (or on failure) fall back to dateparser auto-detection. Returns an
    ISO date string, or the original text if nothing parses."""
    text = text.strip()
    if not text:
        return text
    if fmt:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        import dateparser

        parsed = dateparser.parse(
            text,
            settings={
                "PREFER_DAY_OF_MONTH": "first",
                "RETURN_AS_TIMEZONE_AWARE": False,
            },
        )
        if parsed:
            return parsed.date().isoformat()
    except Exception:
        logger.debug("Zone OCR: dateparser failed for %r", text[:50])
    return text


def _apply_transform(text: str, transform: str, date_format: str = "") -> str:
    """Apply post-processing transform to extracted text."""
    text = text.strip()
    if not text:
        return text

    if transform in ("strip", "none"):
        return text
    elif transform == "date":
        return _parse_date(text, date_format)
    elif transform == "uppercase":
        return text.upper()
    elif transform == "lowercase":
        return text.lower()
    elif transform == "numeric":
        result = re.sub(r"[^\d.,\-]", "", text)
        return result if result else text
    elif transform == "strip_punctuation":
        return text.strip(string.punctuation + " \t\r\n")
    elif transform == "qr_code":
        # Barcode/QR content as read by _read_barcode.
        return text
    return text


def _zone_target_label(zone: OcrTemplateZone) -> str:
    """Human label of a zone's write target (for logging)."""
    target = getattr(zone, "target", None) or "custom_field"
    if target == "custom_field":
        return zone.custom_field.name if zone.custom_field_id else "(no field)"
    return {"title": "Title", "asn": "ASN", "created": "Created"}.get(target, target)


def _parse_created_datetime(value: str):
    """Parse an extracted value into a tz-aware datetime for document.created.

    Prefers an ISO date (the zone should use a date transform); falls back to
    dateparser. Returns None if no date can be parsed.
    """
    from django.utils import timezone as djtz

    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        try:
            dt = datetime(int(m[1]), int(m[2]), int(m[3]))
            return djtz.make_aware(dt) if djtz.is_naive(dt) else dt
        except ValueError:
            pass
    try:
        import dateparser

        parsed = dateparser.parse(
            value,
            settings={"RETURN_AS_TIMEZONE_AWARE": False},
        )
        if parsed:
            return djtz.make_aware(parsed) if djtz.is_naive(parsed) else parsed
    except Exception:
        logger.debug("Zone OCR: dateparser failed for created value %r", value[:50])
    return None


def _write_zone_value(
    document: Document,
    zone: OcrTemplateZone,
    value: str,
) -> None:
    """Write an extracted value to the zone's target — a custom field, or a
    built-in document field (title / archive_serial_number / created)."""
    target = getattr(zone, "target", None) or "custom_field"

    if target == "custom_field":
        if zone.custom_field_id:
            _write_custom_field(document, zone.custom_field, value)
        else:
            logger.debug("Zone OCR: zone '%s' has no custom field set", zone.name)
        return

    if target == "title":
        document.title = value[:128]
        document.save(update_fields=["title"])
    elif target == "asn":
        digits = re.sub(r"[^\d]", "", value)
        if not digits:
            logger.debug(
                "Zone OCR: ASN zone '%s' produced no digits (%r)", zone.name, value[:50],
            )
            return
        document.archive_serial_number = int(digits)
        document.save(update_fields=["archive_serial_number"])
    elif target == "created":
        parsed = _parse_created_datetime(value)
        if parsed is None:
            logger.debug(
                "Zone OCR: created zone '%s' could not parse a date (%r)",
                zone.name,
                value[:50],
            )
            return
        document.created = parsed
        document.save(update_fields=["created"])


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
