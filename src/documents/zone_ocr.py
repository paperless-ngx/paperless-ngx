from __future__ import annotations

import logging
import math
import re
import string
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from decimal import Decimal
from decimal import InvalidOperation
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING
from typing import NewType
from typing import TypeAlias
from typing import assert_never

from babel import Locale
from babel import UnknownLocaleError
from babel.numbers import NumberFormatError
from babel.numbers import get_decimal_symbol
from babel.numbers import get_group_symbol
from babel.numbers import is_currency
from babel.numbers import parse_decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.db.models import Field
from django.utils import timezone
from PIL import Image
from PIL import ImageOps

from documents.matching import matches
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import OcrTemplate
from documents.models import OcrTemplateZone
from documents.parsers import ParseError
from documents.parsers import rasterize_pdf_page_to_png
from documents.permissions import permitted_object_ids
from documents.regex import safe_regex_fullmatch
from documents.validators import monetary_validator
from documents.versioning import get_root_document
from paperless.parsers.utils import get_page_count_for_pdf
from paperless.utils import OCR_TO_DATEPARSER_LANGUAGES

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any

    from django.contrib.auth.models import User
    from django.db.models import QuerySet

logger = logging.getLogger("paperless.zone_ocr")

# Unicode general category for decimal digits in any script.
UNICODE_DECIMAL_DIGIT = "Nd"  # codespell:ignore

# Year-first dates (ISO and its slashed or dotted variants), never a slice of a
# longer digit run. They are unambiguous, so no date order is needed.
YEAR_FIRST_DATE_RE = re.compile(
    r"(?<!\d)(\d{4})([-/.])(\d{2})\2(\d{2})(?!\d)",
)

# Date-shaped tokens inside labelled text: a numeric day/month/year with a
# separator, or a day, a month name and a four-digit year. Only these tokens are
# handed to dateparser, so bare numbers around a label are never read as dates.
DATE_TOKEN_RE = re.compile(
    r"(?<!\d)\d{1,2}[./-]\d{1,2}[./-]\d{4}(?!\d)"
    r"|(?<!\d)\d{1,2}\.?\s+[^\W\d_]{3,}\.?\s+\d{4}(?!\d)",
)

# Literal text made only of whitespace and separator punctuation.
SEPARATOR_ONLY_RE = re.compile(r"[\s\-/.,;:|]*")

# Earlier dates are far more likely OCR noise than a real document date.
MIN_ZONE_DATE_YEAR = 1900

# Longest OCR text read as a number, amount or date. Longer numbers and amounts
# are not parsed, and dates are only searched for in the leading text, which
# bounds parsing time when a zone covers a large region.
MAX_PARSED_TEXT_LENGTH = 256


# A converted zone value, as stored on a document or custom field instance.
ZoneValue: TypeAlias = str | int | float | bool | date

# A key of OcrTemplate.combine_formats, naming the field a zone writes to.
FieldKey = NewType("FieldKey", str)


@dataclass(frozen=True, kw_only=True, slots=True)
class ZoneExtraction:
    raw_text: str | None = None
    value: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class FieldUpdate:
    field_name: str
    value: ZoneValue
    custom_field: CustomField | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class ZoneSourceFile:
    path: Path
    is_image: bool


def resolve_zone_source(document: Document) -> ZoneSourceFile | None:
    """
    Pick the stored file zone OCR reads: the archive PDF when it exists on disk,
    else the source file when it exists, else None.
    """
    if document.has_archive_version:
        archive_path = document.archive_path
        if archive_path is not None and archive_path.is_file():
            return ZoneSourceFile(path=archive_path, is_image=False)
    source_path = document.source_path
    if source_path.is_file():
        return ZoneSourceFile(
            path=source_path,
            is_image=document.mime_type.startswith("image/"),
        )
    return None


class ZoneOcrReason(StrEnum):
    """
    Why a zone produced no value for its target. SUPERSEDED means an earlier
    template already wrote the field.
    """

    MISSING_FILE = "missing_file"
    MISSING_PAGE = "missing_page"
    NO_VALUE = "no_value"
    TRANSFORM_FAILED = "transform_failed"
    REGEX_MISMATCH = "regex_mismatch"
    INCOMPLETE = "incomplete"
    DUPLICATE_ASN = "duplicate_asn"
    UNASSIGNED = "unassigned"
    INVALID_VALUE = "invalid_value"
    TEMPLATE_FAILED = "template_failed"
    SUPERSEDED = "superseded"


class ZoneOcrSkipReason(StrEnum):
    """Why a zone OCR run on one document was not queued."""

    NO_TEMPLATE = "no_template"


@dataclass(kw_only=True, slots=True)
class ZoneOcrResult:
    template: str
    zone: str
    custom_field: str
    value: ZoneValue | None = None
    reason: ZoneOcrReason | None = None


@dataclass(kw_only=True, slots=True)
class PlannedUpdate:
    """A field update and the accepted zone results it was combined from."""

    key: FieldKey
    update: FieldUpdate
    results: list[ZoneOcrResult]


@dataclass(kw_only=True, slots=True)
class TemplatePlan:
    """A template's zone results and the field updates they produce, unwritten."""

    template: OcrTemplate
    zones: list[OcrTemplateZone]
    results: list[ZoneOcrResult]
    updates: list[PlannedUpdate]


# Result labels for zones that target a built-in field.
BUILTIN_TARGET_LABELS: dict[OcrTemplateZone.TargetType, str] = {
    OcrTemplateZone.TargetType.TITLE: "Title",
    OcrTemplateZone.TargetType.ASN: "ASN",
    OcrTemplateZone.TargetType.CREATED: "Created",
}


def _zone_result(
    template: OcrTemplate,
    zone: OcrTemplateZone,
    *,
    reason: ZoneOcrReason | None = None,
) -> ZoneOcrResult:
    target = OcrTemplateZone.TargetType(zone.target)
    if target == OcrTemplateZone.TargetType.CUSTOM_FIELD:
        custom_field = zone.custom_field
        label = custom_field.name if custom_field is not None else "(no field)"
    else:
        label = BUILTIN_TARGET_LABELS[target]
    return ZoneOcrResult(
        template=template.name,
        zone=zone.name,
        custom_field=label,
        reason=reason,
    )


def get_templates_for_document(
    document: Document,
    *,
    requester: User | None = None,
) -> list[OcrTemplate]:
    """
    The enabled templates that match the selected file's content and that the
    root document's owner can view. A document without an owner considers every
    template, as matching does for tags, correspondents and the like. For a
    manual run, the templates are further limited to those the requester can
    view, so a user editing someone else's document never runs or sees that
    owner's private templates.
    """
    templates = _visible_templates(get_root_document(document).owner, requester)
    match_document = document
    if document.root_document_id is None and templates:
        # The original file can be selected even when newer versions exist.
        annotated = (
            Document.objects.filter(pk=document.pk)
            .annotate(effective_content=F("content"))
            .first()
        )
        if annotated is None:
            return []
        match_document = annotated
    return [template for template in templates if matches(template, match_document)]


def get_templates_for_content(
    content: str,
    owner: User | None,
    *,
    title: str = "",
) -> list[OcrTemplate]:
    """
    The enabled templates that match the given text and that the owner can view,
    for a document that is not saved yet. A missing owner considers every
    template, as get_templates_for_document does. The title only labels the
    matching log messages.
    """
    templates = _visible_templates(owner, None)
    match_document = Document(title=title, content=content)
    return [template for template in templates if matches(template, match_document)]


def _visible_templates(
    owner: User | None,
    requester: User | None,
) -> QuerySet[OcrTemplate]:
    """The enabled templates both the owner and the requester can view, if given."""
    templates = OcrTemplate.objects.filter(enabled=True)
    if owner is not None:
        templates = templates.filter(
            id__in=permitted_object_ids(owner, OcrTemplate, "view_ocrtemplate"),
        )
    if requester is not None:
        templates = templates.filter(
            id__in=permitted_object_ids(requester, OcrTemplate, "view_ocrtemplate"),
        )
    return templates.order_by("name", "pk").prefetch_related(
        "zones",
        "zones__custom_field",
    )


def run_zone_extraction(
    document: Document,
    templates: list[OcrTemplate] | None = None,
) -> list[ZoneOcrResult]:
    """
    Extract zones from the selected file version and update its root document.
    Run all matching templates when no templates are given.

    The root document's modified time is bumped when any value was written.
    Callers finish the edit (index, signals) themselves; see zone_results_written.
    """
    if templates is None:
        templates = get_templates_for_document(document)
    if not templates:
        return []

    label = f"document {document.pk}"
    source = resolve_zone_source(document)
    plans = plan_zone_extraction(
        source.path if source else None,
        document.page_count,
        templates,
        label=label,
        is_image=source.is_image if source else False,
    )
    results = apply_zone_plans(get_root_document(document), plans, label=label)
    if zone_results_written(results):
        Document.objects.filter(pk=get_root_document(document).pk).update(
            modified=timezone.now(),
        )
    return results


def plan_zone_extraction(
    doc_path: Path | None,
    page_count: int | None,
    templates: list[OcrTemplate],
    *,
    label: str,
    is_image: bool,
) -> list[TemplatePlan]:
    """
    Render the zones' pages from doc_path and compute each template's field
    updates without writing anything. A template that fails yields only
    TEMPLATE_FAILED results, and a missing file yields MISSING_FILE results for
    every zone. The label names the document in log messages. is_image says
    doc_path is an image rather than a PDF.
    """
    template_zones = [(template, list(template.zones.all())) for template in templates]
    if doc_path is None:
        logger.warning("Zone OCR: no accessible file for %s", label)
        return [
            _failed_plan(template, zones, ZoneOcrReason.MISSING_FILE)
            for template, zones in template_zones
        ]

    if not any(zones for _, zones in template_zones):
        return []
    page_count = _effective_page_count(doc_path, page_count, is_image=is_image)
    pages = {
        page_idx
        for _, zones in template_zones
        for zone in zones
        if (page_idx := _resolve_page_idx(zone.page, page_count)) is not None
    }
    plans = []
    settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp_dir:
        tmp_path = Path(tmp_dir)
        page_images = _render_pages(
            doc_path,
            pages,
            tmp_path,
            page_count,
            is_image=is_image,
        )
        for template, zones in template_zones:
            try:
                plans.append(
                    _plan_template(page_count, page_images, template, zones, tmp_path),
                )
            except Exception:
                # One failed template must not prevent the remaining templates
                # from running.
                logger.exception(
                    "Zone OCR: error processing template '%s' for %s",
                    template.name,
                    label,
                )
                plans.append(
                    _failed_plan(template, zones, ZoneOcrReason.TEMPLATE_FAILED),
                )
    return plans


def apply_zone_plans(
    root_document: Document,
    plans: list[TemplatePlan],
    *,
    label: str,
    protected: frozenset[FieldKey] = frozenset(),
) -> list[ZoneOcrResult]:
    """
    Write each template's planned updates to the root document, each template
    in its own atomic block, and return the zone results. Fields whose key is in
    protected are not written, and the results of every zone targeting them are
    left out. A template whose writes fail gets TEMPLATE_FAILED results and the
    others still apply. A field an earlier template wrote is not written by a
    later one, and the zones targeting it get SUPERSEDED results.
    """
    results: list[ZoneOcrResult] = []
    written: set[FieldKey] = set()
    for plan in plans:
        for planned in plan.updates:
            if planned.key in protected:
                logger.info(
                    "Zone OCR: template '%s' kept the supplied %s of %s",
                    plan.template.name,
                    planned.update.field_name,
                    label,
                )
        superseded: set[FieldKey] = set()
        for planned in plan.updates:
            if planned.key in written:
                superseded.add(planned.key)
                logger.warning(
                    "Zone OCR: template '%s' did not write %s of %s, an earlier "
                    "template already did",
                    plan.template.name,
                    planned.update.field_name,
                    label,
                )
        updates = [
            planned
            for planned in plan.updates
            if planned.key not in protected and planned.key not in superseded
        ]
        try:
            if updates:
                _apply_template_updates(root_document, updates)
            plan_results = plan.results
            written.update(
                planned.key
                for planned in updates
                if all(result.reason is None for result in planned.results)
            )
        except Exception:
            logger.exception(
                "Zone OCR: error processing template '%s' for %s",
                plan.template.name,
                label,
            )
            plan_results = _failed_plan(
                plan.template,
                plan.zones,
                ZoneOcrReason.TEMPLATE_FAILED,
            ).results
            superseded = set()
        # Each zone has exactly one result, in zone order.
        for zone, result in zip(plan.zones, plan_results, strict=True):
            key = _zone_key(zone)
            if key in protected:
                continue
            if key in superseded:
                result.value = None
                result.reason = ZoneOcrReason.SUPERSEDED
            results.append(result)
    return results


def _zone_key(zone: OcrTemplateZone) -> FieldKey:
    """The combine_formats key of the field a zone fills."""
    return field_key(OcrTemplateZone.TargetType(zone.target), zone.custom_field_id)


def _failed_plan(
    template: OcrTemplate,
    zones: list[OcrTemplateZone],
    reason: ZoneOcrReason,
) -> TemplatePlan:
    return TemplatePlan(
        template=template,
        zones=zones,
        results=[_zone_result(template, zone, reason=reason) for zone in zones],
        updates=[],
    )


def zone_results_written(results: list[ZoneOcrResult]) -> bool:
    """Whether at least one zone's value was written to the root document."""
    return any(result.reason is None for result in results)


def _effective_page_count(
    doc_path: Path,
    page_count: int | None,
    *,
    is_image: bool,
) -> int | None:
    """The stored page count, else 1 for an image, else the pages in the PDF."""
    if page_count:
        return page_count
    if is_image:
        return 1
    return get_page_count_for_pdf(doc_path)


def _resolve_page_idx(page_value: int | None, page_count: int | None) -> int | None:
    """
    Resolve a zone's 1-based page or -1 (last page) to a 0-based index, defaulting
    to the first page. The last page without a known page count resolves to None,
    meaning the zone cannot be located.
    """
    if page_value == -1:
        if not page_count:
            return None
        return page_count - 1
    return max((page_value or 1) - 1, 0)


def _process_template(
    document: Document,
    page_images: dict[int, Path],
    template: OcrTemplate,
    zones: list[OcrTemplateZone],
    tmp_path: Path,
) -> list[ZoneOcrResult]:
    """Extract and combine zone values, then apply a template's updates."""
    plan = _plan_template(document.page_count, page_images, template, zones, tmp_path)
    if plan.updates:
        _apply_template_updates(get_root_document(document), plan.updates)
    return plan.results


def _plan_template(
    page_count: int | None,
    page_images: dict[int, Path],
    template: OcrTemplate,
    zones: list[OcrTemplateZone],
    tmp_path: Path,
) -> TemplatePlan:
    """Extract and combine zone values into a template's updates, unwritten."""
    # Each zone's result and its accepted text, by target field.
    grouped: dict[
        FieldKey,
        list[tuple[OcrTemplateZone, ZoneOcrResult, str | None]],
    ] = {}
    results = []
    for zone in zones:
        page_idx = _resolve_page_idx(zone.page, page_count)
        extracted = None
        reason: ZoneOcrReason | None = ZoneOcrReason.MISSING_PAGE
        if page_idx is not None and page_idx in page_images:
            extraction = _extract_zone(
                page_images[page_idx],
                zone,
                zone.zone_source_width or template.source_width,
                zone.zone_source_height or template.source_height,
                tmp_path,
            )
            extracted = extraction.value
            if extracted:
                reason = None
            elif extraction.raw_text:
                # Text was read but the transform found nothing usable in it.
                reason = ZoneOcrReason.TRANSFORM_FAILED
            else:
                reason = ZoneOcrReason.NO_VALUE
        if (
            extracted is not None
            and zone.validation_regex
            and not safe_regex_fullmatch(zone.validation_regex, extracted)
        ):
            reason = ZoneOcrReason.REGEX_MISMATCH
        result = _zone_result(template, zone, reason=reason)
        results.append(result)
        key = _zone_key(zone)
        grouped.setdefault(key, []).append(
            (zone, result, extracted if reason is None else None),
        )

    updates = []
    combine_formats: dict[FieldKey, str] = template.combine_formats or {}
    for key, field_zones in grouped.items():
        accepted = [result for _, result, _ in field_zones if result.reason is None]
        if not accepted:
            continue
        # An empty zone is an optional token; any other failure blocks the group.
        if any(
            result.reason not in (None, ZoneOcrReason.NO_VALUE)
            for _, result, _ in field_zones
        ):
            for result in accepted:
                result.value = None
                result.reason = ZoneOcrReason.INCOMPLETE
            continue
        value = _combine_field_value(
            combine_formats.get(key, ""),
            [(zone.name, text) for zone, _, text in field_zones],
        )
        target_zone = field_zones[0][0]
        update = _prepare_field_update(target_zone, value) if value else None
        if update is not None:
            updates.append(PlannedUpdate(key=key, update=update, results=accepted))
        for result in accepted:
            result.value = update.value if update else None
            if update is None:
                result.reason = (
                    ZoneOcrReason.UNASSIGNED
                    if key == UNASSIGNED_FIELD_KEY
                    else ZoneOcrReason.INVALID_VALUE
                )
    return TemplatePlan(
        template=template,
        zones=zones,
        results=results,
        updates=updates,
    )


def _apply_template_updates(
    root_document: Document,
    updates: list[PlannedUpdate],
) -> None:
    """Write one template's updates to the root document in one atomic block.

    The ASN duplicate check and the custom field existence check run here, at
    write time, so they see the database as it is when the values are saved.
    """
    field_ids = {
        planned.update.custom_field.pk
        for planned in updates
        if planned.update.custom_field is not None
    }
    with transaction.atomic():
        existing_field_ids = (
            set(
                CustomField.objects.filter(pk__in=field_ids).values_list(
                    "pk",
                    flat=True,
                ),
            )
            if field_ids
            else set()
        )
        writable = []
        for planned in updates:
            custom_field = planned.update.custom_field
            if custom_field is not None and custom_field.pk not in existing_field_ids:
                # The field was deleted after the values were planned.
                for result in planned.results:
                    result.value = None
                    result.reason = ZoneOcrReason.UNASSIGNED
                continue
            if _asn_in_use(planned.update, root_document):
                # Saving would violate the unique ASN and roll back every other
                # write of this template, so only this field is dropped.
                for result in planned.results:
                    result.value = None
                    result.reason = ZoneOcrReason.DUPLICATE_ASN
                continue
            writable.append(planned.update)
        _apply_field_updates(root_document, writable)


def _asn_in_use(update: FieldUpdate, root_document: Document) -> bool:
    """Whether an ASN update collides with another document's ASN.

    Trashed documents count, matching the database constraint.
    """
    return (
        update.field_name == "archive_serial_number"
        and isinstance(update.value, int)
        and Document.global_objects.filter(archive_serial_number=update.value)
        .exclude(pk=root_document.pk)
        .exists()
    )


def field_key(
    target: OcrTemplateZone.TargetType,
    custom_field_id: int | None,
) -> FieldKey:
    """The combine_formats key of a zone: its custom field id or its target."""
    if target == OcrTemplateZone.TargetType.CUSTOM_FIELD and custom_field_id:
        return FieldKey(str(custom_field_id))
    return FieldKey(target)


# The key shared by custom field zones without a custom field.
UNASSIGNED_FIELD_KEY = field_key(OcrTemplateZone.TargetType.CUSTOM_FIELD, None)


def _combine_field_value(
    fmt: str,
    field_zones: list[tuple[str, str | None]],
) -> str:
    """Combine the OCR values of all zones targeting one field.

    With a format string, `{Zone Name}` tokens are replaced by that zone's value
    and literal text is kept. Values are inserted verbatim (only surrounding
    whitespace is removed), so punctuation inside an OCR value is never altered.
    Unknown token names count as empty. Tidying only touches the format's own
    literal text: a separator-only literal following an empty token is dropped
    (for a trailing empty token, the nearest preceding kept separator is
    dropped instead), as is a leading separator-only literal in front of an
    empty first token. Other literal text, such as brackets around an empty
    token ("{A}, {B} ({C})" gives "a, b ()"), is kept as long as at least one
    token has a value; when every token is empty the result is an empty
    string. Without a format, the non-empty zone values are joined in order by
    a space.
    """
    if not fmt:
        return " ".join(value for _, value in field_zones if value).strip()

    values = {name.strip(): (value or "").strip() for name, value in field_zones}

    # Pairs of (is_token, text); tokens carry their value.
    parts: list[tuple[bool, str]] = []
    for index, piece in enumerate(re.split(r"(\{[^{}]+\})", fmt)):
        if not piece:
            continue
        if index % 2:
            parts.append((True, values.get(piece[1:-1].strip(), "")))
        else:
            parts.append((False, piece))

    if not any(is_token and text for is_token, text in parts):
        return ""

    def _is_separator(part: tuple[bool, str]) -> bool:
        return not part[0] and SEPARATOR_ONLY_RE.fullmatch(part[1]) is not None

    kept: list[tuple[bool, str]] = []
    drop_next_separator = False
    for position, part in enumerate(parts):
        if drop_next_separator:
            drop_next_separator = False
            continue
        is_token, text = part
        if not is_token or text:
            kept.append(part)
            continue
        following = parts[position + 1] if position + 1 < len(parts) else None
        if following is not None:
            drop_next_separator = _is_separator(following)
        elif kept and _is_separator(kept[-1]):
            kept.pop()
        # A leading separator left in front of an empty first token.
        if len(kept) == 1 and _is_separator(kept[0]):
            kept.pop()
    return "".join(text for _, text in kept).strip()


def _render_pages(
    doc_path: Path,
    pages: set[int],
    tmp_dir: Path,
    page_count: int | None,
    *,
    is_image: bool,
) -> dict[int, Path]:
    """
    Render specific PDF pages as PNG images using pdftoppm (poppler-utils).
    An image file is used as-is for page 0 only.
    """
    result: dict[int, Path] = {}

    if is_image:
        if 0 in pages:
            result[0] = doc_path
        return result

    for actual_page in sorted(pages):
        if actual_page < 0 or (page_count and actual_page >= page_count):
            continue

        rendered = tmp_dir / f"page_{actual_page}.png"
        try:
            rasterize_pdf_page_to_png(
                doc_path,
                rendered,
                dpi=300,
                page=actual_page + 1,  # pdftoppm is 1-indexed
                timeout=60,
            )
        except ParseError as e:
            logger.exception(
                "Zone OCR: pdftoppm failed for page %d: %s",
                actual_page,
                e,
            )
            continue

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
        with Image.open(page_img) as opened, ImageOps.exif_transpose(opened) as img:
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
    import zxingcpp

    try:
        results = zxingcpp.read_barcodes(cropped)
        return results[0].text if results else None
    except (RuntimeError, ValueError, TypeError):
        logger.exception("Zone OCR: barcode read failed for zone '%s'", zone_name)
        return None


def _ocr_text(cropped: Image.Image, zone: OcrTemplateZone, tmp_dir: Path) -> str | None:
    """OCR a cropped image with Tesseract."""
    crop_path = tmp_dir / f"zone_{zone.pk}.png"
    # PNG cannot store every mode (e.g. CMYK from a CMYK JPEG or TIFF), so convert the others to RGB.
    if cropped.mode not in ("1", "L", "LA", "P", "RGB", "RGBA", "I;16", "I;16B"):
        cropped = cropped.convert("RGB")
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
        logger.exception(
            "Zone OCR: Tesseract failed for zone '%s': %s",
            zone.name,
            e.stderr[:200] if e.stderr else str(e),
        )
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
        value=_apply_transform(
            raw_text or "",
            OcrTemplateZone.TransformType(zone.transform),
            _date_rules(zone.ocr_language, zone.date_format),
        )
        or None,
    )


def extract_zone_preview(
    doc_path: Path,
    zone: OcrTemplateZone,
    source_width: int,
    source_height: int,
    page_count: int | None,
    *,
    is_image: bool,
) -> ZoneExtraction:
    """Extract a zone without writing its value to the document."""
    page_count = _effective_page_count(doc_path, page_count, is_image=is_image)
    page_idx = _resolve_page_idx(zone.page, page_count)
    settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp_dir:
        tmp_path = Path(tmp_dir)
        page_images = _render_pages(
            doc_path,
            set() if page_idx is None else {page_idx},
            tmp_path,
            page_count,
            is_image=is_image,
        )
        if page_idx is None or page_idx not in page_images:
            return ZoneExtraction()

        return _extract_zone(
            page_images[page_idx],
            zone,
            source_width,
            source_height,
            tmp_path,
        )


@dataclass(frozen=True)
class DateRules:
    """How a zone reads dates: its language and optional strptime format."""

    language: str | None = None
    date_format: str = ""


def _date_rules(ocr_language: str, date_format: str = "") -> DateRules:
    return DateRules(_zone_language(ocr_language), date_format)


def _dateparser_date(text: str, rules: DateRules) -> date | None:
    """Read a whole-text absolute date with dateparser in the zone's language."""
    import dateparser

    # Only absolute dates: dateparser would also read "now" or "yesterday"
    date_settings: dict[str, Any] = {
        "PARSERS": ["custom-formats", "absolute-time"],
        "REQUIRE_PARTS": ["day", "month", "year"],
        "RETURN_AS_TIMEZONE_AWARE": False,
    }
    if rules.language is None:
        date_settings["DATE_ORDER"] = settings.DATE_ORDER
    try:
        parsed = dateparser.parse(
            text,
            languages=None if rules.language is None else [rules.language],
            settings=date_settings,
        )
    except (ValueError, OverflowError):
        logger.debug("Zone OCR: date parsing failed")
        return None
    return parsed.date() if parsed else None


def _candidate_dates(text: str, rules: DateRules) -> Iterator[date]:
    """Yield the dates the text may hold, most specific reading first."""
    if rules.date_format:
        try:
            yield datetime.strptime(text, rules.date_format).date()
        except ValueError:
            pass
    for match in YEAR_FIRST_DATE_RE.finditer(text):
        year, _, month, day = match.groups()
        try:
            yield date(int(year), int(month), int(day))
        except ValueError:
            continue
    whole_text = _dateparser_date(text, rules)
    if whole_text is not None:
        yield whole_text
    # Labelled text such as "Datum: 13.04.2026": try each date-shaped token in order
    for token in DATE_TOKEN_RE.finditer(text):
        labelled = _dateparser_date(token.group(), rules)
        if labelled is not None:
            yield labelled


def _parse_date(text: str, rules: DateRules) -> date | None:
    """Read a calendar date from OCR text.

    Tries the zone's date format, year-first dates, then dateparser in the zone's
    language (or the configured date order when the language is unknown) on the
    whole text. As a last resort, labelled text such as "Datum: 13.04.2026" is
    searched for date-shaped tokens with a four-digit year (numeric, or day,
    month name and year), and the first token dateparser accepts is used. Bare
    numbers and two-digit years in surrounding text are never read as dates, so
    version or article numbers like "1.2.34" are ignored. Dates before
    MIN_ZONE_DATE_YEAR are treated as OCR noise. Only the first
    MAX_PARSED_TEXT_LENGTH characters are read, without a word the cut splits.
    """
    if len(text) > MAX_PARSED_TEXT_LENGTH:
        head = text[:MAX_PARSED_TEXT_LENGTH]
        if not text[MAX_PARSED_TEXT_LENGTH].isspace():
            # Drop the word split by the cut, so a truncated token cannot match
            # as a different date.
            kept = re.match(r".*\s", head, re.DOTALL)
            head = kept.group() if kept else ""
        text = head
        if not text.strip():
            return None
    return next(
        (
            candidate
            for candidate in _candidate_dates(text, rules)
            if candidate.year >= MIN_ZONE_DATE_YEAR
        ),
        None,
    )


def _apply_transform(
    text: str,
    transform: OcrTemplateZone.TransformType,
    dates: DateRules,
) -> str:
    """Apply post-processing transform to extracted text.

    A date or numeric transform that finds no date or digit returns an empty
    string instead of passing the raw text on.
    """
    text = text.strip()
    if not text:
        return text

    match transform:
        case (
            OcrTemplateZone.TransformType.NONE
            | OcrTemplateZone.TransformType.STRIP
            | OcrTemplateZone.TransformType.QR_CODE
        ):
            return text
        case OcrTemplateZone.TransformType.DATE:
            parsed = _parse_date(text, dates)
            return parsed.isoformat() if parsed else ""
        case OcrTemplateZone.TransformType.UPPERCASE:
            return text.upper()
        case OcrTemplateZone.TransformType.LOWERCASE:
            return text.lower()
        case OcrTemplateZone.TransformType.NUMERIC:
            numeric = re.sub(r"[^\d.,\-]", "", text)
            return numeric if re.search(r"\d", numeric) else ""
        case OcrTemplateZone.TransformType.STRIP_PUNCTUATION:
            return text.strip(string.punctuation + " \t\r\n")
        case unreachable:
            assert_never(unreachable)


def _prepare_field_update(
    zone: OcrTemplateZone,
    value: str,
) -> FieldUpdate | None:
    """Convert extracted text and enforce the destination field's constraints."""
    custom_field = None
    typed_value: ZoneValue | None
    model: type[Document | CustomFieldInstance]
    target = OcrTemplateZone.TargetType(zone.target)
    match target:
        case OcrTemplateZone.TargetType.CUSTOM_FIELD:
            custom_field = zone.custom_field
            if custom_field is None:
                return None
            data_type = CustomField.FieldDataType(custom_field.data_type)
            field_name = CustomFieldInstance.get_value_field_name(data_type)
            typed_value = _convert_value(
                value,
                data_type,
                _number_locale(zone.ocr_language),
                _date_rules(zone.ocr_language, zone.date_format),
            )
            model = CustomFieldInstance
        case OcrTemplateZone.TargetType.TITLE:
            field_name, typed_value = "title", value[:128]
            model = Document
        case OcrTemplateZone.TargetType.ASN:
            digits = re.sub(r"[^\d]", "", value)
            field_name = "archive_serial_number"
            typed_value = int(digits) if digits else None
            model = Document
        case OcrTemplateZone.TargetType.CREATED:
            field_name, typed_value = (
                "created",
                _parse_date(
                    value,
                    _date_rules(zone.ocr_language, zone.date_format),
                ),
            )
            model = Document
        case unreachable:
            assert_never(unreachable)
    if typed_value is None:
        return None
    field = model._meta.get_field(field_name)
    assert isinstance(field, Field)
    try:
        cleaned: ZoneValue = field.clean(typed_value, None)
    except ValidationError:
        logger.info("Zone OCR: invalid value for zone '%s'", zone.name)
        return None
    return FieldUpdate(field_name=field_name, value=cleaned, custom_field=custom_field)


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


def _zone_language(ocr_language: str) -> str | None:
    """Map the first tesseract language of a zone to a dateparser/Babel code.

    Only the first language counts, so "deu+eng" is German. Returns None when
    the language is not mapped.
    """
    tesseract_code = ocr_language.split("+", maxsplit=1)[0].split("_", maxsplit=1)[0]
    return OCR_TO_DATEPARSER_LANGUAGES.get(tesseract_code)


def _number_locale(ocr_language: str) -> Locale:
    """Derive the locale used to read numbers from a tesseract language code.

    Languages Babel does not know fall back to English.
    """
    code = _zone_language(ocr_language)
    if code is not None:
        try:
            return Locale.parse(code)
        except (UnknownLocaleError, ValueError):
            pass
    return Locale.parse("en")


def _parse_number(value: str, locale: Locale) -> Decimal | None:
    """Parse OCR text as a decimal number using the locale's number format.

    Digits of any script are read as their ASCII equivalents, and characters
    that are not part of a number, such as letters or currency symbols, are
    dropped. A dash (also a unicode minus or en dash) makes the number negative
    when it comes before the first digit and does not directly follow a letter
    or digit, so "-5", "EUR -5" and "$-5" are negative while "INV-123" is
    just 123. Any other dash makes the text invalid. Returns None when the
    text is not a well-formed number in the locale or is longer than
    MAX_PARSED_TEXT_LENGTH.
    """
    if len(value) > MAX_PARSED_TEXT_LENGTH:
        return None
    text = "".join(
        str(unicodedata.digit(char))
        if unicodedata.category(char) == UNICODE_DECIMAL_DIGIT
        else char
        for char in value.strip()
    )
    text = (
        text.replace("\N{MINUS SIGN}", "-")
        .replace("\N{EN DASH}", "-")
        .replace("\N{ARABIC DECIMAL SEPARATOR}", ".")
        .replace("\N{ARABIC THOUSANDS SEPARATOR}", ",")
    )
    # Only a dash before the first digit can be a sign. Searching that prefix
    # (instead of a lookahead for a later digit) keeps this linear.
    first_digit = re.search(r"\d", text)
    sign = (
        re.search(r"(?<!\w)-", text[: first_digit.start()])
        if first_digit is not None
        else None
    )
    negative = sign is not None
    if sign is not None:
        text = text[: sign.start()] + text[sign.end() :]
    if re.search(r"\d\D*-|(?<!\w)-", text):
        return None
    decimal_symbol = get_decimal_symbol(locale)
    group_symbol = get_group_symbol(locale)
    if group_symbol.isspace():
        text = re.sub(r"(?<=\d)[ \u00a0\u202f]+(?=\d)", group_symbol, text)
    allowed = {*string.digits, ".", ",", decimal_symbol, group_symbol}
    body = "".join(char for char in text if char in allowed)
    if not body:
        return None
    try:
        number = parse_decimal(body, locale=locale, strict=True)
    except NumberFormatError:
        return None
    return number.copy_negate() if negative else number


@lru_cache(maxsize=32)
def _currency_symbol_codes(locale: Locale) -> dict[str, str]:
    """Map the unambiguous currency symbols of a locale to their currency code.

    Symbols shared by several currencies, and symbols made only of letters or
    digits (which includes plain three letter codes), are left out.
    """
    codes_by_symbol: dict[str, set[str]] = {}
    for code, symbol in locale.currency_symbols.items():
        if not symbol.isalnum():
            codes_by_symbol.setdefault(symbol, set()).add(code)
    return {
        symbol: next(iter(codes))
        for symbol, codes in codes_by_symbol.items()
        if len(codes) == 1
    }


def _find_currency(text: str, locale: Locale) -> set[str]:
    """Find the currency codes mentioned in OCR text.

    Three letter uppercase tokens that are ISO 4217 codes win. Only when there
    are none are the locale's currency symbols looked for, longest first so
    "A$" is not also read as "$".
    """
    codes = {
        code
        for code in re.findall(r"(?<![A-Za-z])[A-Z]{3}(?![A-Za-z])", text)
        if is_currency(code)
    }
    if codes:
        return codes
    for symbol, code in sorted(
        _currency_symbol_codes(locale).items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if symbol in text:
            codes.add(code)
            text = text.replace(symbol, " ")
    return codes


def _parse_monetary(value: str, locale: Locale) -> str | None:
    """Parse OCR text as a monetary value in the stored custom field format.

    The result is the amount with exactly two decimals, prefixed by the
    currency code when the text names one ("USD12.50", "-12.50"). The rules are:

    - The currency is an ISO 4217 code written as an uppercase word, or else a
      currency symbol of the locale that belongs to a single currency. Text
      naming two different currencies is rejected, and text naming none gives
      an amount without a code. Any uppercase word that is an ISO code
      (e.g. "ALL" or "TOP") is read as a currency.
    - A number enclosed in parentheses is negative, "(12.50)". Digits outside
      the parentheses, as in "100 (19% VAT)", or a minus sign combined with
      them are rejected.
    - The amount is read like any other number of the locale, must not need
      more than two decimals ("12.500" is fine, "12.345" is not) and has at
      most 12 digits, with or without a currency code.
    - The result must pass the same validation as values sent through the API.

    Returns None when the text is not a valid monetary value or is longer than
    MAX_PARSED_TEXT_LENGTH.
    """
    if len(value) > MAX_PARSED_TEXT_LENGTH:
        return None
    group = next(
        (
            match
            for match in re.finditer(r"\([^()]*\)", value)
            if re.search(r"\d", match.group())
        ),
        None,
    )
    parenthesised = group is not None
    text = value
    if group is not None:
        outside = value[: group.start()] + value[group.end() :]
        if re.search(r"\d", outside) or re.search(
            "[-\N{MINUS SIGN}\N{EN DASH}]",
            value,
        ):
            return None
        text = value.replace("(", " ").replace(")", " ")

    currencies = _find_currency(text, locale)
    if len(currencies) > 1:
        return None

    amount = _parse_number(text, locale)
    if amount is None:
        return None
    if parenthesised:
        amount = amount.copy_negate()
    try:
        rounded = amount.quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    if rounded != amount or len(rounded.as_tuple().digits) > 12:
        return None
    if rounded.is_zero():
        rounded = abs(rounded)

    result = f"{next(iter(currencies), '')}{rounded:f}"
    try:
        monetary_validator(result)
    except ValidationError:
        return None
    return result


def _convert_value(
    value: str,
    data_type: CustomField.FieldDataType,
    locale: Locale,
    dates: DateRules,
) -> ZoneValue | None:
    """Convert an extracted OCR string to the appropriate type for the custom field.

    Numeric types are read with the number format of the given locale and
    dates with the given date rules.
    """
    if not value:
        return None

    try:
        match data_type:
            case (
                CustomField.FieldDataType.STRING
                | CustomField.FieldDataType.URL
                | CustomField.FieldDataType.LONG_TEXT
            ):
                # Returned whole; _prepare_field_update validates length and URL
                # format, so a value is rejected rather than truncated.
                return value

            case CustomField.FieldDataType.INT:
                integer = _parse_number(value, locale)
                if integer is None or integer != integer.to_integral_value():
                    return None
                return int(integer)

            case CustomField.FieldDataType.FLOAT:
                decimal = _parse_number(value, locale)
                if decimal is None:
                    return None
                number = float(decimal)
                return number if math.isfinite(number) else None

            case CustomField.FieldDataType.DATE:
                parsed = _parse_date(value, dates)
                return parsed.isoformat() if parsed else None

            case CustomField.FieldDataType.MONETARY:
                return _parse_monetary(value, locale)

            case CustomField.FieldDataType.BOOL:
                lower = value.lower().strip()
                if lower in ("true", "yes", "1", "ja", "oui", "si", "x"):
                    return True
                elif lower in ("false", "no", "0", "nein", "non"):
                    return False
                return None

            case (
                CustomField.FieldDataType.SELECT
                | CustomField.FieldDataType.DOCUMENTLINK
            ):
                logger.debug(
                    "Zone OCR: unsupported custom field type %s for OCR extraction",
                    data_type,
                )
                return None

            case unreachable:
                assert_never(unreachable)

    except (ValueError, InvalidOperation):
        logger.info("Zone OCR: could not convert value to %s", data_type)
        return None
