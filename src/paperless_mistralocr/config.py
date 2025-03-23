import dataclasses
import os

from django.conf import settings

from paperless.config import OutputTypeConfig


@dataclasses.dataclass
class MistralOcrConfig(OutputTypeConfig):
    """
    Configuration for the Mistral OCR API
    """

    api_key: str = dataclasses.field(init=False)
    model: str = dataclasses.field(init=False)
    mode: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()

        app_config = self._get_config_instance()

        # Use environment variables or settings with defaults
        self.api_key = os.getenv("PAPERLESS_MISTRAL_API_KEY", "")
        self.model = os.getenv("PAPERLESS_MISTRAL_MODEL", "mistral-ocr-latest")
        self.mode = app_config.mode or settings.OCR_MODE  # Reuse OCR mode from settings
