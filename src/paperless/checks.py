import os
import shutil

from django.conf import settings
from django.core.checks import Error, Warning, register

exists_message = "{} is set but doesn't exist."
exists_hint = "Create a directory at {}"
writeable_message = "{} is not writeable"
writeable_hint = (
    "Set the permissions of {} to be writeable by the user running the "
    "Paperless services"
)


def path_check(env_var):
    messages = []
    directory = os.getenv(env_var)
    if directory:
        if not os.path.exists(directory):
            messages.append(Error(
                exists_message.format(env_var),
                exists_hint.format(directory)
            ))
        elif not os.access(directory, os.W_OK | os.X_OK):
            messages.append(Error(
                writeable_message.format(env_var),
                writeable_hint.format(directory)
            ))
    return messages


@register()
def paths_check(app_configs, **kwargs):
    """
    Check the various paths for existence, readability and writeability
    """

    check_messages = path_check("PAPERLESS_DATA_DIR") + \
        path_check("PAPERLESS_MEDIA_ROOT") + \
        path_check("PAPERLESS_CONSUMPTION_DIR") + \
        path_check("PAPERLESS_STATICDIR")

    return check_messages


@register()
def binaries_check(app_configs, **kwargs):
    """
    Paperless requires the existence of a few binaries, so we do some checks
    for those here.
    """

    error = "Paperless can't find {}. Without it, consumption is impossible."
    hint = "Either it's not in your ${PATH} or it's not installed."

    binaries = (
        settings.CONVERT_BINARY,
        settings.OPTIPNG_BINARY,
        "tesseract"
    )

    check_messages = []
    for binary in binaries:
        if shutil.which(binary) is None:
            check_messages.append(Warning(error.format(binary), hint))

    return check_messages


@register()
def debug_mode_check(app_configs, **kwargs):
    if settings.DEBUG:
        return [Warning(
            "DEBUG mode is enabled. Disable Debug mode. This is a serious "
            "security issue, since it puts security overides in place which "
            "are meant to be only used during development. This "
            "also means that paperless will tell anyone various "
            "debugging information when something goes wrong.")]
    else:
        return []
