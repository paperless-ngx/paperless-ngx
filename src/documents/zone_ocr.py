from __future__ import annotations

import logging
import math
import re
import string
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from decimal import Decimal
from decimal import InvalidOperation
from pathlib import Path

import dateparser
import magic
import zxingcpp
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from PIL import Image

from documents.matching import matches
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import OcrTemplate
from documents.models import OcrTemplateZone
from documents.permissions import permitted_object_ids
from documents.regex import safe_regex_fullmatch
from documents.versioning import get_root_document

logger = logging.getLogger("paperless.zone_ocr")


@dataclass(frozen=True)
class ZoneExtraction:
    raw_text: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class FieldUpdate:
    field_name: str
    value: object
    custom_field: CustomField | None = None


@dataclass
class ZoneOcrResult:
    template: str
    zone: str
    custom_field: str
    value: object = None
    reason: str | None = None


def _zone_result(
    template: OcrTemplate,
    zone: OcrTemplateZone,
    *,
    value: object = None,
    reason: str | None = None,
) -> ZoneOcrResult:
    if zone.target == OcrTemplateZone.TargetType.CUSTOM_FIELD:
        label = zone.custom_field.name if zone.custom_field_id else "(no field)"
    else:
        label = {"title": "Title", "asn": "ASN", "created": "Created"}[zone.target]
    return ZoneOcrResult(template.name, zone.name, label, value, reason)


def get_templates_for_document(document: Document) -> list[OcrTemplate]:
    """
    The enabled templates that match the document's content and that its owner
    can view, the same rule as matching. A version is owned through its root
    document.
    """
    owner = get_root_document(document).owner
    templates = (
        OcrTemplate.objects.filter(
            enabled=True,
            id__in=permitted_object_ids(owner, OcrTemplate, "view_ocrtemplate"),
        )
        .order_by("name", "pk")
        .prefetch_related("zones", "zones__custom_field")
    )
    return [template for template in templates if matches(template, document)]


def run_zone_extraction(
    document: Document,
    original_file: Path | None,
    templates: list[OcrTemplate] | None = None,
) -> list[ZoneOcrResult]:
    """
    Run zone-based OCR extraction for the given templates, or for every
    template that matches the document when none are given.
    """
    if templates is None:
        templates = get_templates_for_document(document)
    if not templates:
        return []

    doc_path = _resolve_doc_path(document, original_file)
    if doc_path is None:
        logger.warning(
            "Zone OCR: no accessible file for document %d",
            document.pk,
        )
        return [
            _zone_result(template, zone, reason="missing_file")
            for template in templates
            for zone in template.zones.all()
        ]

    template_zones = [(template, list(template.zones.all())) for template in templates]
    pages = {
        _resolve_page_idx(zone.page, document.page_count)
        for _, zones in template_zones
        for zone in zones
    }
    if not pages:
        return []
    results = []
    with tempfile.TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp_dir:
        tmp_path = Path(tmp_dir)
        page_images = _render_pages(doc_path, pages, tmp_path, document.page_count)
        for template, zones in template_zones:
            try:
                results.extend(
                    _process_template(document, page_images, template, zones, tmp_path),
                )
            except Exception:
                # One failed template must not prevent the remaining templates from running.
                logger.exception(
                    "Zone OCR: error processing template '%s' for document %d",
                    template.name,
                    document.pk,
                )
                results.extend(
                    _zone_result(template, zone, reason="template_failed")
                    for zone in zones
                )
    return results


def _resolve_doc_path(
    document: Document,
    original_file: Path | None,
) -> Path | None:
    """Prefer the archive, then the source, then the ingestion signal's file."""
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


def _resolve_page_idx(page_value: int | None, page_count: int | None) -> int:
    """Resolve a 1-based page or -1 (last page), defaulting to the first page."""
    if page_value == -1:
        return max((page_count or 1) - 1, 0)
    return max((page_value or 1) - 1, 0)


def _process_template(
    document: Document,
    page_images: dict[int, Path],
    template: OcrTemplate,
    zones: list[OcrTemplateZone],
    tmp_path: Path,
) -> list[ZoneOcrResult]:
    """Extract and combine zone values before applying a template's updates."""
    grouped: dict[str, list[tuple[OcrTemplateZone, ZoneOcrResult]]] = {}
    results = []
    for zone in zones:
        page_idx = _resolve_page_idx(zone.page, document.page_count)
        extracted = None
        reason = "missing_page"
        if page_idx in page_images:
            extraction = _extract_zone(
                page_images[page_idx],
                zone,
                zone.zone_source_width or template.source_width,
                zone.zone_source_height or template.source_height,
                tmp_path,
            )
            extracted = extraction.value
            reason = None if extracted else "no_value"
        if (
            extracted is not None
            and zone.validation_regex
            and not safe_regex_fullmatch(zone.validation_regex, extracted)
        ):
            reason = "regex_mismatch"
        result = _zone_result(
            template,
            zone,
            value=extracted if reason is None else None,
            reason=reason,
        )
        results.append(result)
        grouped.setdefault(_field_key(zone), []).append((zone, result))

    updates = []
    combine_formats = template.combine_formats or {}
    for key, field_zones in grouped.items():
        accepted = [result for _, result in field_zones if result.reason is None]
        if not accepted:
            continue
        value = _combine_field_value(
            combine_formats.get(key, ""),
            [(zone.name, result.value) for zone, result in field_zones],
        )
        target_zone = field_zones[0][0]
        update = _prepare_field_update(target_zone, value) if value else None
        if update is not None:
            updates.append(update)
        for result in accepted:
            result.value = update.value if update else None
            if update is None:
                result.reason = (
                    "unassigned" if key == "custom_field" else "invalid_value"
                )
    _apply_field_updates(document, updates)
    return results


def _field_key(zone: OcrTemplateZone) -> str:
    """Use the same target keys as the editor's combination formats."""
    target = zone.target
    if target == OcrTemplateZone.TargetType.CUSTOM_FIELD and zone.custom_field_id:
        return str(zone.custom_field_id)
    return target


def _combine_field_value(
    fmt: str,
    field_zones: list[tuple[str, str | None]],
) -> str:
    """Combine the OCR values of all zones targeting one field.

    With a format string, `{Zone Name}` tokens are replaced by that zone's value
    and literal text is kept; separators left dangling by an empty token are
    cleaned up. Without a format, the zone values are joined in order by a space.
    """
    values = {name: value or "" for name, value in field_zones}

    if not fmt:
        return " ".join(value for _, value in field_zones if value).strip()

    def _replace(match: re.Match) -> str:
        return values.get(match.group(1).strip(), "")

    combined = re.sub(r"\{([^{}]+)\}", _replace, fmt)
    # Tidy up separators an empty token may have left behind.
    combined = re.sub(r"\s{2,}", " ", combined)
    combined = re.sub(r"([^\w\s])\s*\1+", r"\1", combined)
    return combined.strip().strip("-/.,;:| \t")


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
        if 0 in pages:
            result[0] = doc_path
        return result

    for actual_page in sorted(pages):
        if actual_page < 0 or (page_count and actual_page >= page_count):
            continue

        output_prefix = tmp_dir / f"page_{actual_page}"
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-png",
                    "-singlefile",
                    "-r",
                    "300",
                    "-f",
                    str(actual_page + 1),  # pdftoppm is 1-indexed
                    "-l",
                    str(actual_page + 1),
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
            logger.error("Zone OCR: pdftoppm not found")
            return result

        rendered = output_prefix.with_suffix(".png")
        if rendered.is_file():
            result[actual_page] = rendered

    return result


def _crop_zone(
    page_img: Path,
    zone: OcrTemplateZone,
    source_width: int,
    source_height: int,
) -> Image.Image | None:
    """Crop a zone from the page image and return the PIL Image."""
    try:
        with Image.open(page_img) as img:
            img_width, img_height = img.size
            if not source_width or not source_height:
                source_width, source_height = img.size

            scale_x = img_width / source_width
            scale_y = img_height / source_height

            crop_left = int(zone.x * scale_x)
            crop_top = int(zone.y * scale_y)
            crop_right = int((zone.x + zone.width) * scale_x)
            crop_bottom = int((zone.y + zone.height) * scale_y)

            # Clamp to the image so an oversized zone can't crop out of bounds.
            crop_left = max(0, min(crop_left, img_width))
            crop_top = max(0, min(crop_top, img_height))
            crop_right = min(crop_right, img_width)
            crop_bottom = min(crop_bottom, img_height)

            if crop_right - crop_left < 2 or crop_bottom - crop_top < 2:
                logger.warning("Zone OCR: crop too small for zone '%s'", zone.name)
                return None

            return img.crop((crop_left, crop_top, crop_right, crop_bottom))
    except (OSError, ValueError, Image.DecompressionBombError):
        logger.exception("Zone OCR: crop failed for zone '%s'", zone.name)
        return None


def _read_barcode(cropped: Image.Image, zone_name: str) -> str | None:
    """Read QR/barcode from a cropped image using zxingcpp."""
    try:
        results = zxingcpp.read_barcodes(cropped)
        return results[0].text if results else None
    except (RuntimeError, ValueError, TypeError):
        logger.exception("Zone OCR: barcode read failed for zone '%s'", zone_name)
        return None


def _ocr_text(cropped: Image.Image, zone: OcrTemplateZone, tmp_dir: Path) -> str | None:
    """OCR a cropped image with Tesseract."""
    crop_path = tmp_dir / f"zone_{zone.pk}.png"
    cropped.save(crop_path)

    try:
        proc = subprocess.run(
            [
                "tesseract",
                str(crop_path),
                "stdout",
                "-l",
                zone.ocr_language,
                "--psm",
                "6",  # Assume uniform block of text
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
        logger.error("Zone OCR: Tesseract not found")
        return None


def _extract_zone(
    page_img: Path,
    zone: OcrTemplateZone,
    source_width: int,
    source_height: int,
    tmp_dir: Path,
) -> ZoneExtraction:
    """Read and transform a zone, retaining the text for the editor's preview."""
    cropped = _crop_zone(page_img, zone, source_width, source_height)
    if cropped is None:
        return ZoneExtraction()

    try:
        raw_text = (
            _read_barcode(cropped, zone.name)
            if zone.transform == OcrTemplateZone.TransformType.QR_CODE
            else _ocr_text(cropped, zone, tmp_dir)
        )
    finally:
        cropped.close()
    return ZoneExtraction(
        raw_text=raw_text,
        value=_apply_transform(raw_text, zone.transform, zone.date_format)
        if raw_text
        else None,
    )


def extract_zone_preview(
    doc_path: Path,
    zone: OcrTemplateZone,
    source_width: int,
    source_height: int,
    page_count: int | None,
) -> dict:
    """Extract a zone without writing its value to the document."""
    page_idx = _resolve_page_idx(zone.page, page_count)
    with tempfile.TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp_dir:
        tmp_path = Path(tmp_dir)
        page_images = _render_pages(doc_path, {page_idx}, tmp_path, page_count)
        if page_idx not in page_images:
            return {"raw_text": None, "value": None}

        result = _extract_zone(
            page_images[page_idx],
            zone,
            source_width,
            source_height,
            tmp_path,
        )
        return {"raw_text": result.raw_text, "value": result.value}


def _parse_iso_date(text: str) -> date | None:
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return date.fromisoformat(match[0]) if match else None


def _parse_date(text: str, fmt: str = "") -> date | None:
    """Try the zone's date format, ISO dates, then automatic date detection."""
    if fmt:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        iso_date = _parse_iso_date(text)
    except ValueError:
        iso_date = None
    if iso_date is not None:
        return iso_date
    try:
        parsed = dateparser.parse(
            text,
            settings={
                "PREFER_DAY_OF_MONTH": "first",
                "RETURN_AS_TIMEZONE_AWARE": False,
            },
        )
        if parsed:
            return parsed.date()
    except (ValueError, OverflowError):
        logger.debug("Zone OCR: date parsing failed")
    return None


def _apply_transform(text: str, transform: str, date_format: str = "") -> str:
    """Apply post-processing transform to extracted text."""
    text = text.strip()
    if not text:
        return text

    if transform in ("strip", "none"):
        return text
    elif transform == "date":
        parsed = _parse_date(text, date_format)
        return parsed.isoformat() if parsed else text
    elif transform == "uppercase":
        return text.upper()
    elif transform == "lowercase":
        return text.lower()
    elif transform == "numeric":
        result = re.sub(r"[^\d.,\-]", "", text)
        return result if result else text
    elif transform == "strip_punctuation":
        return text.strip(string.punctuation + " \t\r\n")
    return text


def _prepare_field_update(
    zone: OcrTemplateZone,
    value: str,
) -> FieldUpdate | None:
    """Convert extracted text and enforce the destination field's constraints."""
    custom_field = None
    if zone.target == OcrTemplateZone.TargetType.CUSTOM_FIELD:
        if not zone.custom_field_id:
            return None
        custom_field = zone.custom_field
        field_name = CustomFieldInstance.get_value_field_name(custom_field.data_type)
        typed_value = _convert_value(value, custom_field.data_type)
        model = CustomFieldInstance
    elif zone.target == OcrTemplateZone.TargetType.TITLE:
        field_name, typed_value = "title", value[:128]
        model = Document
    elif zone.target == OcrTemplateZone.TargetType.ASN:
        digits = re.sub(r"[^\d]", "", value)
        field_name = "archive_serial_number"
        typed_value = int(digits) if digits else None
        model = Document
    elif zone.target == OcrTemplateZone.TargetType.CREATED:
        field_name, typed_value = "created", _parse_date(value)
        model = Document
    else:
        return None
    if typed_value is None:
        return None
    try:
        typed_value = model._meta.get_field(field_name).clean(typed_value, None)
    except ValidationError:
        logger.info("Zone OCR: invalid value for zone '%s'", zone.name)
        return None
    return FieldUpdate(field_name, typed_value, custom_field)


def _apply_field_updates(document: Document, updates: list[FieldUpdate]) -> None:
    builtin_values = {
        update.field_name: update.value
        for update in updates
        if update.custom_field is None
    }
    original_values = {name: getattr(document, name) for name in builtin_values}
    try:
        with transaction.atomic():
            for update in updates:
                if update.custom_field is not None:
                    CustomFieldInstance.objects.update_or_create(
                        document=document,
                        field=update.custom_field,
                        defaults={update.field_name: update.value},
                    )
            if builtin_values:
                for name, value in builtin_values.items():
                    setattr(document, name, value)
                document.save(update_fields=list(builtin_values))
    except Exception:
        # Database rollback does not restore attributes on the model instance.
        for name, value in original_values.items():
            setattr(document, name, value)
        raise


def _normalize_number(value: str) -> str:
    cleaned = re.sub(r"[^\d.,\-]", "", value)
    # When both separators occur, the rightmost one is the decimal separator.
    if "," in cleaned and "." in cleaned:
        if cleaned.rindex(",") > cleaned.rindex("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    Decimal(cleaned)
    return cleaned


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
            digits = digits.lstrip("-")
            if not digits:
                return None
            if value.strip().startswith("-"):
                digits = "-" + digits
            return int(digits)

        elif data_type == CustomField.FieldDataType.FLOAT:
            number = float(_normalize_number(value))
            return number if math.isfinite(number) else None

        elif data_type == CustomField.FieldDataType.DATE:
            parsed = _parse_iso_date(value)
            return parsed.isoformat() if parsed else None

        elif data_type == CustomField.FieldDataType.MONETARY:
            return _normalize_number(value)

        elif data_type == CustomField.FieldDataType.BOOL:
            lower = value.lower().strip()
            if lower in ("true", "yes", "1", "ja", "oui", "si", "x"):
                return True
            elif lower in ("false", "no", "0", "nein", "non"):
                return False
            return None

        else:
            logger.debug(
                "Zone OCR: unsupported custom field type %s for OCR extraction",
                data_type,
            )
            return None

    except (ValueError, InvalidOperation):
        logger.info("Zone OCR: could not convert value to %s", data_type)
        return None


def _detect_mime(path: Path) -> str | None:
    """Detect MIME type of a file."""
    try:
        return magic.from_file(str(path), mime=True)
    except (OSError, magic.MagicException):
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
