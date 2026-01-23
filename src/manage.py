#!/usr/bin/env python3
import os
import sys

if __name__ == "__main__":
    try:
        from paperless_migration.detect import choose_settings_module

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", choose_settings_module())
    except Exception:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
