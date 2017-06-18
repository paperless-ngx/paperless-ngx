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

    directory = os.getenv("PAPERLESS_STATICDIR")
    if directory:
        if not os.path.exists(directory):
            check_messages.append(Error(
                exists_message.format("PAPERLESS_STATICDIR"),
                exists_hint.format(directory)
            ))
        if not check_messages:
            if not os.access(directory, os.W_OK | os.X_OK):
                check_messages.append(Error(
                    writeable_message.format("PAPERLESS_STATICDIR"),
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


@register()
def config_check(app_configs, **kwargs):
    warning = (
        "It looks like you have PAPERLESS_SHARED_SECRET defined.  Note that "
        "in the \npast, this variable was used for both API authentication "
        "and as the mail \nkeyword.  As the API no no longer uses it, this "
        "variable has been renamed to \nPAPERLESS_EMAIL_SECRET, so if you're "
        "using the mail feature, you'd best update \nyour variable name.\n\n"
        "The old variable will stop working in a few months."
    )

    if os.getenv("PAPERLESS_SHARED_SECRET"):
        return [Warning(warning)]

    return []
