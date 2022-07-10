# this is here so that django finds the checks.
from .checks import changed_password_check
from .checks import parser_check

__all__ = ["changed_password_check", "parser_check"]
