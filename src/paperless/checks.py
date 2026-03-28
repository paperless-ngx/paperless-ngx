import grp
import os
import pwd
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.checks import Error
from django.core.checks import Tags
from django.core.checks import Warning
from django.core.checks import register
from django.db import connections

exists_message = "{} is set but doesn't exist."
exists_hint = "Create a directory at {}"
writeable_message = "{} is not writeable"
writeable_hint = (
    "Set the permissions of {} to be writeable by the user running the "
    "Paperless services"
)


def path_check(var: str, directory: Path) -> list[Error]:
    messages: list[Error] = []
    if directory:
        if not directory.is_dir():
            messages.append(
                Error(exists_message.format(var), exists_hint.format(directory)),
            )
        else:
            test_file: Path = directory / f"__paperless_write_test_{os.getpid()}__"
            try:
                with test_file.open("w"):
                    pass
            except PermissionError:
                dir_stat: os.stat_result = Path(directory).stat()
                dir_mode: str = stat.filemode(dir_stat.st_mode)
                dir_owner: str = pwd.getpwuid(dir_stat.st_uid).pw_name
                dir_group: str = grp.getgrgid(dir_stat.st_gid).gr_name
                messages.append(
                    Error(
                        writeable_message.format(var),
                        writeable_hint.format(
                            f"\n{dir_mode} {dir_owner} {dir_group} {directory}\n",
                        ),
                    ),
                )
            finally:
                try:
                    if test_file.is_file():
                        test_file.unlink()
                except (PermissionError, OSError):
                    # Skip cleanup if we can't access the file — expected in permission tests
                    pass

    return messages


@register()
def paths_check(app_configs: Any, **kwargs: Any) -> list[Error]:
    """
    Check the various paths for existence, readability and writeability
    """

    return (
        path_check("PAPERLESS_DATA_DIR", settings.DATA_DIR)
        + path_check("PAPERLESS_EMPTY_TRASH_DIR", settings.EMPTY_TRASH_DIR)
        + path_check("PAPERLESS_MEDIA_ROOT", settings.MEDIA_ROOT)
        + path_check("PAPERLESS_CONSUMPTION_DIR", settings.CONSUMPTION_DIR)
    )


@register()
def binaries_check(app_configs: Any, **kwargs: Any) -> list[Error]:
    """
    Paperless requires the existence of a few binaries, so we do some checks
    for those here.
    """

    error = "Paperless can't find {}. Without it, consumption is impossible."
    hint = "Either it's not in your ${PATH} or it's not installed."

    binaries = (settings.CONVERT_BINARY, "tesseract", "gs")

    check_messages = []
    for binary in binaries:
        if shutil.which(binary) is None:
            check_messages.append(Warning(error.format(binary), hint))

    return check_messages


@register()
def debug_mode_check(app_configs: Any, **kwargs: Any) -> list[Warning]:
    if settings.DEBUG:
        return [
            Warning(
                "DEBUG mode is enabled. Disable Debug mode. This is a serious "
                "security issue, since it puts security overrides in place "
                "which are meant to be only used during development. This "
                "also means that paperless will tell anyone various "
                "debugging information when something goes wrong.",
            ),
        ]
    else:
        return []


@register()
def settings_values_check(app_configs: Any, **kwargs: Any) -> list[Error | Warning]:
    """
    Validates at least some of the user provided settings
    """

    def _ocrmypdf_settings_check():
        """
        Validates some of the arguments which will be provided to ocrmypdf
        against the valid options.  Use "ocrmypdf --help" to see the valid
        inputs
        """
        msgs = []
        if settings.OCR_OUTPUT_TYPE not in {
            "pdfa",
            "pdf",
            "pdfa-1",
            "pdfa-2",
            "pdfa-3",
        }:
            msgs.append(
                Error(f'OCR output type "{settings.OCR_OUTPUT_TYPE}" is not valid'),
            )

        if settings.OCR_MODE not in {"auto", "force", "redo", "off"}:
            msgs.append(Error(f'OCR output mode "{settings.OCR_MODE}" is not valid'))

        if settings.ARCHIVE_FILE_GENERATION not in {"auto", "always", "never"}:
            msgs.append(
                Error(
                    "PAPERLESS_ARCHIVE_FILE_GENERATION setting "
                    f'"{settings.ARCHIVE_FILE_GENERATION}" is not valid',
                ),
            )

        if settings.OCR_CLEAN not in {"clean", "clean-final", "none"}:
            msgs.append(Error(f'OCR clean mode "{settings.OCR_CLEAN}" is not valid'))
        return msgs

    def _timezone_validate():
        """
        Validates the user provided timezone is a valid timezone
        """
        import zoneinfo

        msgs = []
        if settings.TIME_ZONE not in zoneinfo.available_timezones():
            msgs.append(
                Error(f'Timezone "{settings.TIME_ZONE}" is not a valid timezone'),
            )
        return msgs

    def _email_certificate_validate():
        msgs = []
        # Existence checks
        if (
            settings.EMAIL_CERTIFICATE_FILE is not None
            and not settings.EMAIL_CERTIFICATE_FILE.is_file()
        ):
            msgs.append(
                Error(
                    f"Email cert {settings.EMAIL_CERTIFICATE_FILE} is not a file",
                ),
            )
        return msgs

    return (
        _ocrmypdf_settings_check()
        + _timezone_validate()
        + _email_certificate_validate()
    )


@register()
def audit_log_check(app_configs: Any, **kwargs: Any) -> list[Error]:
    db_conn = connections["default"]
    all_tables = db_conn.introspection.table_names()
    result = []

    if ("auditlog_logentry" in all_tables) and not settings.AUDIT_LOG_ENABLED:
        result.append(
            Warning(
                ("auditlog table was found but audit log is disabled."),
            ),
        )

    return result


@register(Tags.compatibility)
def check_v3_minimum_upgrade_version(
    app_configs: object,
    **kwargs: object,
) -> list[Error]:
    """
    Enforce that upgrades to v3 must start from v2.20.10.

    v3 squashes all prior migrations into 0001_squashed and 0002_squashed.
    If a user skips v2.20.10, the data migration in 1075_workflowaction_order
    never runs and the squash may apply schema changes against an incomplete
    database state.
    """
    from django.db import DatabaseError
    from django.db import OperationalError

    try:
        all_tables = connections["default"].introspection.table_names()

        if "django_migrations" not in all_tables:
            return []

        with connections["default"].cursor() as cursor:
            cursor.execute(
                "SELECT name FROM django_migrations WHERE app = %s",
                ["documents"],
            )
            applied: set[str] = {row[0] for row in cursor.fetchall()}

        if not applied:
            return []

        # Already in a valid v3 state
        if {"0001_squashed", "0002_squashed"} & applied:
            return []

        # On v2.20.10 exactly — squash will pick up cleanly from here
        if "1075_workflowaction_order" in applied:
            return []

    except (DatabaseError, OperationalError):
        return []

    return [
        Error(
            "Cannot upgrade to Paperless-ngx v3 from this version.",
            hint=(
                "Upgrading to v3 can only be performed from v2.20.10."
                "Please upgrade to v2.20.10, run migrations, then upgrade to v3."
                "See https://docs.paperless-ngx.com/setup/#upgrading for details."
            ),
            id="paperless.E002",
        ),
    ]


@register()
def check_deprecated_db_settings(
    app_configs: object,
    **kwargs: object,
) -> list[Warning]:
    """Check for deprecated database environment variables.

    Detects legacy advanced options that should be migrated to
    PAPERLESS_DB_OPTIONS. Returns one Warning per deprecated variable found.
    """
    deprecated_vars: dict[str, str] = {
        "PAPERLESS_DB_TIMEOUT": "timeout",
        "PAPERLESS_DB_POOLSIZE": "pool.min_size / pool.max_size",
        "PAPERLESS_DBSSLMODE": "sslmode",
        "PAPERLESS_DBSSLROOTCERT": "sslrootcert",
        "PAPERLESS_DBSSLCERT": "sslcert",
        "PAPERLESS_DBSSLKEY": "sslkey",
    }

    warnings: list[Warning] = []

    for var_name, db_option_key in deprecated_vars.items():
        if not os.getenv(var_name):
            continue
        warnings.append(
            Warning(
                f"Deprecated environment variable: {var_name}",
                hint=(
                    f"{var_name} is no longer supported and will be removed in v3.2. "
                    f"Set the equivalent option via PAPERLESS_DB_OPTIONS instead. "
                    f'Example: PAPERLESS_DB_OPTIONS=\'{{"{db_option_key}": "<value>"}}\'. '
                    "See https://docs.paperless-ngx.com/migration/ for the full reference."
                ),
                id="paperless.W001",
            ),
        )

    return warnings


@register()
def check_deprecated_v2_ocr_env_vars(
    app_configs: object,
    **kwargs: object,
) -> list[Warning]:
    """Warn when deprecated v2 OCR environment variables are set.

    Users upgrading from v2 may still have these in their environment or
    config files, where they are now silently ignored.
    """
    warnings: list[Warning] = []

    if os.environ.get("PAPERLESS_OCR_SKIP_ARCHIVE_FILE"):
        warnings.append(
            Warning(
                "PAPERLESS_OCR_SKIP_ARCHIVE_FILE is set but has no effect. "
                "Use PAPERLESS_ARCHIVE_FILE_GENERATION=never/always/auto instead.",
                id="paperless.W002",
            ),
        )

    ocr_mode = os.environ.get("PAPERLESS_OCR_MODE", "")
    if ocr_mode in {"skip", "skip_noarchive"}:
        warnings.append(
            Warning(
                f"PAPERLESS_OCR_MODE={ocr_mode!r} is not a valid value. "
                f"Use PAPERLESS_OCR_MODE=auto (and PAPERLESS_ARCHIVE_FILE_GENERATION=never "
                f"if you used skip_noarchive) instead.",
                id="paperless.W003",
            ),
        )

    return warnings


@register()
def check_remote_parser_configured(app_configs: Any, **kwargs: Any) -> list[Error]:
    if settings.REMOTE_OCR_ENGINE == "azureai" and not (
        settings.REMOTE_OCR_ENDPOINT and settings.REMOTE_OCR_API_KEY
    ):
        return [
            Error(
                "Azure AI remote parser requires endpoint and API key to be configured.",
            ),
        ]

    return []


def get_tesseract_langs():
    proc = subprocess.run(
        [shutil.which("tesseract"), "--list-langs"],
        capture_output=True,
    )

    # Decode bytes to string, split on newlines, trim out the header
    proc_lines = proc.stdout.decode("utf8", errors="ignore").strip().split("\n")[1:]

    return [x.strip() for x in proc_lines]


@register()
def check_default_language_available(app_configs: Any, **kwargs: Any) -> list[Error]:
    errs = []

    if not settings.OCR_LANGUAGE:
        errs.append(
            Warning(
                "No OCR language has been specified with PAPERLESS_OCR_LANGUAGE. "
                "This means that tesseract will fallback to english.",
            ),
        )
        return errs

    # binaries_check in paperless will check and report if this doesn't exist
    # So skip trying to do anything here and let that handle missing binaries
    if shutil.which("tesseract") is not None:
        installed_langs = get_tesseract_langs()

        specified_langs = [x.strip() for x in settings.OCR_LANGUAGE.split("+")]

        for lang in specified_langs:
            if lang not in installed_langs:
                errs.append(
                    Error(
                        f"The selected ocr language {lang} is "
                        f"not installed. Paperless cannot OCR your documents "
                        f"without it. Please fix PAPERLESS_OCR_LANGUAGE.",
                    ),
                )

    return errs
