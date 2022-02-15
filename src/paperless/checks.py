import os
import shutil
import stat

from django.conf import settings
from django.core.checks import Error, Warning, register

exists_message = "{} is set but doesn't exist."
exists_hint = "Create a directory at {}"
writeable_message = "{} is not writeable"
writeable_hint = (
    "Set the permissions of {} to be writeable by the user running the "
    "Paperless services"
)


def path_check(var, directory):
    messages = []
    if directory:
        if not os.path.isdir(directory):
            messages.append(Error(
                exists_message.format(var),
                exists_hint.format(directory)
            ))
        else:
            test_file = os.path.join(
                directory, f'__paperless_write_test_{os.getpid()}__'
            )
            try:
                with open(test_file, 'w'):
                    pass
            except PermissionError:
                messages.append(Error(
                    writeable_message.format(var),
                    writeable_hint.format(
                        f'\n{stat.filemode(os.stat(directory).st_mode)} '
                        f'{directory}\n')
                ))
            finally:
                if os.path.isfile(test_file):
                    os.remove(test_file)

    return messages


@register()
def paths_check(app_configs, **kwargs):
    """
    Check the various paths for existence, readability and writeability
    """

    return path_check("PAPERLESS_DATA_DIR", settings.DATA_DIR) + \
        path_check("PAPERLESS_MEDIA_ROOT", settings.MEDIA_ROOT) + \
        path_check("PAPERLESS_CONSUMPTION_DIR", settings.CONSUMPTION_DIR)


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
