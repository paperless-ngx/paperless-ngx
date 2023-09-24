# this is here so that django finds the checks.
from documents.checks import changed_password_check
from documents.checks import parser_check

__all__ = ["changed_password_check", "parser_check"]
