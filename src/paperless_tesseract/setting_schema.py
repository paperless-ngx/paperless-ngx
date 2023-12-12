import dataclasses
import json
from typing import Optional

from django.conf import settings

from paperless_tesseract.models import OcrSettings as OcrSettingModel


@dataclasses.dataclass(frozen=True)
class OcrSetting:
    pages: Optional[int]
    language: str
    output_type: str
    mode: str
    skip_archive_file: str
    image_dpi: Optional[int]
    clean: str
    deskew: bool
    rotate: bool
    rotate_threshold: float
    max_image_pixel: Optional[float]
    color_conversion_strategy: str
    user_args: Optional[dict[str, str]]


def get_ocr_settings() -> OcrSetting:
    db_settings = OcrSettingModel.objects.all().first()
    # assert db_settings is not None

    user_args = None
    if db_settings is not None and db_settings.user_args:
        user_args = db_settings.user_args
    elif settings.OCR_USER_ARGS is not None:
        user_args = json.loads(settings.OCR_USER_ARGS)

    return OcrSetting(
        pages=db_settings.pages if db_settings is not None else settings.OCR_PAGES,
        language=db_settings.language
        if db_settings is not None and db_settings.language is not None
        else settings.OCR_LANGUAGE,
        output_type=db_settings.output_type
        if db_settings is not None
        else settings.OCR_OUTPUT_TYPE,
        mode=db_settings.mode if db_settings is not None else settings.OCR_MODE,
        skip_archive_file=(
            db_settings.skip_archive_file
            if db_settings is not None
            else settings.OCR_SKIP_ARCHIVE_FILE
        ),
        image_dpi=db_settings.image_dpi
        if db_settings is not None
        else settings.OCR_IMAGE_DPI,
        clean=db_settings.unpaper_clean
        if db_settings is not None
        else settings.OCR_CLEAN,
        deskew=db_settings.deskew if db_settings is not None else settings.OCR_DESKEW,
        rotate=db_settings.rotate_pages
        if db_settings is not None
        else settings.OCR_ROTATE_PAGES,
        rotate_threshold=(
            db_settings.rotate_pages_threshold
            if db_settings is not None
            else settings.OCR_ROTATE_PAGES_THRESHOLD
        ),
        max_image_pixel=db_settings.max_image_pixels
        if db_settings is not None
        else settings.OCR_MAX_IMAGE_PIXELS,
        color_conversion_strategy=(
            db_settings.color_conversion_strategy
            if db_settings is not None
            else settings.OCR_COLOR_CONVERSION_STRATEGY
        ),
        user_args=user_args,
    )
