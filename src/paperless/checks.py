import os

from django.core.checks import Error, register, Warning


@register()
def paths_check(app_configs, **kwargs):

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
