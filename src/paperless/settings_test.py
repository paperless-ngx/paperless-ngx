from paperless.settings import *  # noqa: F403
from paperless.settings import INSTALLED_APPS

INSTALLED_APPS.extend(
    [
        "allauth.socialaccount.providers.openid_connect",
    ],
)
