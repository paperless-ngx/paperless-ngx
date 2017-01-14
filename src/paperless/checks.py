import os
import shutil

from django.conf import settings
from django.core.checks import Error, register, Warning


@register()
def paths_check(app_configs, **kwargs):
    """
    Check the various paths for existence, readability and writeability
    """

    check_messages = []

    exists_message = "{} is set but doesn't exist."
    exists_hint = "Create a directory at {}"
    writeable_message = "{} is not writeable"
    writeable_hint = (
        "Set the permissions of {} to be writeable by the user running the "
        "Paperless services"
    )

    directory = os.getenv("PAPERLESS_DBDIR")
    if directory:
        if not os.path.exists(directory):
            check_messages.append(Error(
                exists_message.format("PAPERLESS_DBDIR"),
                exists_hint.format(directory)
            ))
        if not check_messages:
            if not os.access(directory, os.W_OK | os.X_OK):
                check_messages.append(Error(
                    writeable_message.format("PAPERLESS_DBDIR"),
                    writeable_hint.format(directory)
                ))

    directory = os.getenv("PAPERLESS_MEDIADIR")
    if directory:
        if not os.path.exists(directory):
            check_messages.append(Error(
                exists_message.format("PAPERLESS_MEDIADIR"),
                exists_hint.format(directory)
            ))
        if not check_messages:
            if not os.access(directory, os.W_OK | os.X_OK):
                check_messages.append(Error(
                    writeable_message.format("PAPERLESS_MEDIADIR"),
                    writeable_hint.format(directory)
                ))

    return check_messages


@register()
def binaries_check(app_configs, **kwargs):
    """
    Paperless requires the existence of a few binaries, so we do some checks
    for those here.
    """

    error = "Paperless can't find {}. Without it, consumption is impossible."
    hint = "Either it's not in your ${PATH} or it's not installed."

    binaries = (settings.CONVERT_BINARY, settings.UNPAPER_BINARY, "tesseract")

    check_messages = []
    for binary in binaries:
        if shutil.which(binary) is None:
            check_messages.append(Warning(error.format(binary), hint))

    return check_messages
