# this is here so that django finds the checks.
from paperless_remote.checks import check_remote_parser_configured

__all__ = ["check_remote_parser_configured"]
