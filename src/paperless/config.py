import dataclasses
import json

from django.conf import settings

from paperless.models import ApplicationConfiguration


@dataclasses.dataclass
class BaseConfig:
    """
    Almost all parsers care about the chosen PDF output format
    """

    @staticmethod
    def _get_config_instance() -> ApplicationConfiguration:
        app_config = ApplicationConfiguration.objects.all().first()
        # Workaround for a test where the migration hasn't run to create the single model
        if app_config is None:
            ApplicationConfiguration.objects.create()
            app_config = ApplicationConfiguration.objects.all().first()
        return app_config


@dataclasses.dataclass
class OutputTypeConfig(BaseConfig):
    """
    Almost all parsers care about the chosen PDF output format
    """

    output_type: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        app_config = self._get_config_instance()

        self.output_type = app_config.output_type or settings.OCR_OUTPUT_TYPE


@dataclasses.dataclass
class OcrConfig(OutputTypeConfig):
    """
    Specific settings for the Tesseract based parser.  Options generally
    correspond almost directly to the OCRMyPDF options
    """

    pages: int | None = dataclasses.field(init=False)
    language: str = dataclasses.field(init=False)
    mode: str = dataclasses.field(init=False)
    skip_archive_file: str = dataclasses.field(init=False)
    image_dpi: int | None = dataclasses.field(init=False)
    clean: str = dataclasses.field(init=False)
    deskew: bool = dataclasses.field(init=False)
    rotate: bool = dataclasses.field(init=False)
    rotate_threshold: float = dataclasses.field(init=False)
    max_image_pixel: float | None = dataclasses.field(init=False)
    color_conversion_strategy: str = dataclasses.field(init=False)
    user_args: dict[str, str] | None = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()

        app_config = self._get_config_instance()

        self.pages = app_config.pages or settings.OCR_PAGES
        self.language = app_config.language or settings.OCR_LANGUAGE
        self.mode = app_config.mode or settings.OCR_MODE
        self.skip_archive_file = (
            app_config.skip_archive_file or settings.OCR_SKIP_ARCHIVE_FILE
        )
        self.image_dpi = app_config.image_dpi or settings.OCR_IMAGE_DPI
        self.clean = app_config.unpaper_clean or settings.OCR_CLEAN
        self.deskew = (
            app_config.deskew if app_config.deskew is not None else settings.OCR_DESKEW
        )
        self.rotate = (
            app_config.rotate_pages
            if app_config.rotate_pages is not None
            else settings.OCR_ROTATE_PAGES
        )
        self.rotate_threshold = (
            app_config.rotate_pages_threshold or settings.OCR_ROTATE_PAGES_THRESHOLD
        )
        self.max_image_pixel = (
            app_config.max_image_pixels or settings.OCR_MAX_IMAGE_PIXELS
        )
        self.color_conversion_strategy = (
            app_config.color_conversion_strategy
            or settings.OCR_COLOR_CONVERSION_STRATEGY
        )

        user_args = None
        if app_config.user_args:
            user_args = app_config.user_args
        elif settings.OCR_USER_ARGS is not None:  # pragma: no cover
            try:
                user_args = json.loads(settings.OCR_USER_ARGS)
            except json.JSONDecodeError:
                user_args = {}
        self.user_args = user_args


@dataclasses.dataclass
class BarcodeConfig(BaseConfig):
    """
    Barcodes settings
    """

    barcodes_enabled: bool = dataclasses.field(init=False)
    barcode_enable_tiff_support: bool = dataclasses.field(init=False)
    barcode_string: str = dataclasses.field(init=False)
    barcode_retain_split_pages: bool = dataclasses.field(init=False)
    barcode_enable_asn: bool = dataclasses.field(init=False)
    barcode_asn_prefix: str = dataclasses.field(init=False)
    barcode_upscale: float = dataclasses.field(init=False)
    barcode_dpi: int = dataclasses.field(init=False)
    barcode_max_pages: int = dataclasses.field(init=False)
    barcode_enable_tag: bool = dataclasses.field(init=False)
    barcode_tag_mapping: dict[str, str] = dataclasses.field(init=False)
    barcode_tag_split: bool = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        app_config = self._get_config_instance()

        self.barcodes_enabled = (
            app_config.barcodes_enabled or settings.CONSUMER_ENABLE_BARCODES
        )
        self.barcode_enable_tiff_support = (
            app_config.barcode_enable_tiff_support
            or settings.CONSUMER_BARCODE_TIFF_SUPPORT
        )
        self.barcode_string = (
            app_config.barcode_string or settings.CONSUMER_BARCODE_STRING
        )
        self.barcode_retain_split_pages = (
            app_config.barcode_retain_split_pages
            or settings.CONSUMER_BARCODE_RETAIN_SPLIT_PAGES
        )
        self.barcode_enable_asn = (
            app_config.barcode_enable_asn or settings.CONSUMER_ENABLE_ASN_BARCODE
        )
        self.barcode_asn_prefix = (
            app_config.barcode_asn_prefix or settings.CONSUMER_ASN_BARCODE_PREFIX
        )
        self.barcode_upscale = (
            app_config.barcode_upscale or settings.CONSUMER_BARCODE_UPSCALE
        )
        self.barcode_dpi = app_config.barcode_dpi or settings.CONSUMER_BARCODE_DPI
        self.barcode_max_pages = (
            app_config.barcode_max_pages or settings.CONSUMER_BARCODE_MAX_PAGES
        )
        self.barcode_enable_tag = (
            app_config.barcode_enable_tag or settings.CONSUMER_ENABLE_TAG_BARCODE
        )
        self.barcode_tag_mapping = (
            app_config.barcode_tag_mapping or settings.CONSUMER_TAG_BARCODE_MAPPING
        )
        self.barcode_tag_split = (
            app_config.barcode_tag_split or settings.CONSUMER_TAG_BARCODE_SPLIT
        )


@dataclasses.dataclass
class GeneralConfig(BaseConfig):
    """
    General application settings that require global scope
    """

    app_title: str = dataclasses.field(init=False)
    app_logo: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        app_config = self._get_config_instance()

        self.app_title = app_config.app_title or None
        self.app_logo = app_config.app_logo.url if app_config.app_logo else None


@dataclasses.dataclass
class AIConfig(BaseConfig):
    """
    AI related settings that require global scope
    """

    ai_enabled: bool = dataclasses.field(init=False)
    llm_embedding_backend: str = dataclasses.field(init=False)
    llm_embedding_model: str = dataclasses.field(init=False)
    llm_backend: str = dataclasses.field(init=False)
    llm_model: str = dataclasses.field(init=False)
    llm_api_key: str = dataclasses.field(init=False)
    llm_endpoint: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        app_config = self._get_config_instance()

        self.ai_enabled = app_config.ai_enabled or settings.AI_ENABLED
        self.llm_embedding_backend = (
            app_config.llm_embedding_backend or settings.LLM_EMBEDDING_BACKEND
        )
        self.llm_embedding_model = (
            app_config.llm_embedding_model or settings.LLM_EMBEDDING_MODEL
        )
        self.llm_backend = app_config.llm_backend or settings.LLM_BACKEND
        self.llm_model = app_config.llm_model or settings.LLM_MODEL
        self.llm_api_key = app_config.llm_api_key or settings.LLM_API_KEY
        self.llm_endpoint = app_config.llm_endpoint or settings.LLM_ENDPOINT

    @property
    def llm_index_enabled(self) -> bool:
        return bool(self.ai_enabled and self.llm_embedding_backend)
