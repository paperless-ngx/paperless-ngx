from django.conf import settings
from django.core.checks import Error
from django.core.checks import register


@register()
def check_remote_parser_configured(app_configs, **kwargs):
    if settings.REMOTE_OCR_ENGINE == "azureai" and not settings.REMOTE_OCR_ENDPOINT:
        return [
            Error(
                "Azure AI remote parser requires endpoint to be configured.",
            ),
        ]

    return []
