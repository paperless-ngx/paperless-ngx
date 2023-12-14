import dataclasses
import json
from typing import Optional

from django.conf import settings

from paperless.models import CommonSettings
from paperless.models import OcrSettings as OcrSettingModel


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
    ocr_db_settings = OcrSettingModel.objects.all().first()
    # Workaround for a test where the migration hasn't run to create the single model
    if ocr_db_settings is None:
        OcrSettingModel.objects.create()
        ocr_db_settings = OcrSettingModel.objects.all().first()

    cmn_db_settings = CommonSettings.objects.all().first()
    if cmn_db_settings is None:
        CommonSettings.objects.create()
        cmn_db_settings = CommonSettings.objects.all().first()

    user_args = None
    if ocr_db_settings.user_args:
        user_args = ocr_db_settings.user_args
    elif settings.OCR_USER_ARGS is not None:
        try:
            user_args = json.loads(settings.OCR_USER_ARGS)
        except json.JSONDecodeError:
            user_args = {}

    return OcrSetting(
        pages=ocr_db_settings.pages or settings.OCR_PAGES,
        language=ocr_db_settings.language or settings.OCR_LANGUAGE,
        output_type=cmn_db_settings.output_type or settings.OCR_OUTPUT_TYPE,
        mode=ocr_db_settings.mode or settings.OCR_MODE,
        skip_archive_file=(
            ocr_db_settings.skip_archive_file or settings.OCR_SKIP_ARCHIVE_FILE
        ),
        image_dpi=ocr_db_settings.image_dpi or settings.OCR_IMAGE_DPI,
        clean=ocr_db_settings.unpaper_clean or settings.OCR_CLEAN,
        deskew=ocr_db_settings.deskew or settings.OCR_DESKEW,
        rotate=ocr_db_settings.rotate_pages or settings.OCR_ROTATE_PAGES,
        rotate_threshold=(
            ocr_db_settings.rotate_pages_threshold
            or settings.OCR_ROTATE_PAGES_THRESHOLD
        ),
        max_image_pixel=ocr_db_settings.max_image_pixels
        or settings.OCR_MAX_IMAGE_PIXELS,
        color_conversion_strategy=(
            ocr_db_settings.color_conversion_strategy
            or settings.OCR_COLOR_CONVERSION_STRATEGY
        ),
        user_args=user_args,
    )
