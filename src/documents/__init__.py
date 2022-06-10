# this is here so that django finds the checks.
from .checks import changed_password_check
from .checks import parser_check
from .checks import png_thumbnail_check

__all__ = ["changed_password_check", "parser_check", "png_thumbnail_check"]
